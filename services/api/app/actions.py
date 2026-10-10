"""Actual tool-side effects. Called by MCP server; local mode is test-only."""
from __future__ import annotations
import json
import os
import smtplib
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from fastapi import HTTPException
from . import db
from .security import require_membership, verify_token

ALLOWED_TYPES = {"assign_task", "create_event", "create_reminder", "send_message"}


def _validate_user(conn, actor: str, target: str, circle_id: str):
    db.one(conn, "SELECT id FROM users WHERE id=?", (actor,)) or _error(401, "Unknown actor")
    require_membership(conn, actor, circle_id)
    target_user = db.one(conn, "SELECT * FROM users WHERE id=?", (target,))
    if not target_user:
        _error(404, "Recipient not found")
    require_membership(conn, target, circle_id)
    return target_user


def _error(status: int, reason: str):
    raise HTTPException(status_code=status, detail=reason)


def execute(action_type: str, args: dict, auth_token: str, idempotency_key: str) -> dict:
    """Never take actor identity from model-generated args; derive it from the signed token."""
    if action_type not in ALLOWED_TYPES:
        _error(400, "Unknown tool")
    actor = verify_token(auth_token)
    circle_id = str(args.get("circle_id", ""))
    if not circle_id:
        _error(422, "circle_id is required")
    with db.connect() as c:
        require_membership(c, actor, circle_id)
        if action_type == "assign_task":
            assignee = str(args.get("assignee_id", ""))
            _validate_user(c, actor, assignee, circle_id)
            title = str(args.get("title", "")).strip()
            if not (2 <= len(title) <= 160):
                _error(422, "Task title must contain 2-160 characters")
            old = db.one(c, "SELECT * FROM tasks WHERE idempotency_key=?", (idempotency_key,))
            if old:
                return {"ok": True, "duplicate": True, "task": old}
            priority = args.get("priority", "medium")
            if priority not in ("low", "medium", "high"):
                _error(422, "Invalid priority")
            due_at = args.get("due_at") or None
            if due_at:
                try: datetime.fromisoformat(str(due_at))
                except ValueError: _error(422, "Invalid due_at")
            task_id=db.uid()
            c.execute("INSERT INTO tasks(id,circle_id,title,description,assignee_id,created_by,priority,due_at,status,created_at,updated_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (task_id,circle_id,title,str(args.get("description", ""))[:500],assignee,actor,priority,due_at,"todo",db.now(),db.now(),idempotency_key))
            c.execute("INSERT INTO notifications(id,user_id,title,body,created_at,idempotency_key) VALUES(?,?,?,?,?,?)",
                      (db.uid(),assignee,"New assignment",title,db.now(),"notice:"+idempotency_key))
            db.event(c,actor,"task",f"Assigned ‘{title}’ to {assignee}",circle_id)
            return {"ok":True,"task_id":task_id,"type":"assign_task","channel":"database + in-app"}

        if action_type == "create_reminder":
            who=str(args.get("user_id") or actor)
            _validate_user(c,actor,who,circle_id)
            title=str(args.get("title", "")).strip()
            if not title or len(title)>160: _error(422,"Invalid reminder title")
            due_at=str(args.get("due_at", ""))
            try: datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            except ValueError: _error(422,"Invalid reminder date")
            old=db.one(c,"SELECT id FROM reminders WHERE idempotency_key=?",(idempotency_key,))
            if old: return {"ok":True,"duplicate":True,"reminder_id":old["id"]}
            reminder_id=db.uid()
            c.execute("INSERT INTO reminders(id,circle_id,user_id,title,due_at,created_at,idempotency_key) VALUES(?,?,?,?,?,?,?)",
                      (reminder_id,circle_id,who,title,due_at,db.now(),idempotency_key))
            db.event(c,actor,"reminder",f"Scheduled reminder: {title}",circle_id)
            return {"ok":True,"reminder_id":reminder_id,"channel":"in-app scheduler"}

        if action_type == "create_event":
            title=str(args.get("title", "")).strip()
            start=str(args.get("starts_at", ""))
            end=str(args.get("ends_at", ""))
            if not (2 <= len(title) <= 160): _error(422,"Invalid event title")
            try:
                s=datetime.fromisoformat(start.replace("Z", "+00:00"))
                e=datetime.fromisoformat(end.replace("Z", "+00:00"))
                if s>=e: raise ValueError()
            except ValueError: _error(422,"Invalid event time range")
            attendees=args.get("attendees", [actor])
            if not isinstance(attendees,list) or len(attendees)>30: _error(422,"Invalid attendees")
            for attendee in attendees: _validate_user(c,actor,str(attendee),circle_id)
            old=db.one(c,"SELECT id FROM events WHERE idempotency_key=?",(idempotency_key,))
            if old: return {"ok":True,"duplicate":True,"event_id":old["id"]}
            event_id=db.uid()
            c.execute("INSERT INTO events(id,circle_id,title,starts_at,ends_at,created_by,location,attendees,created_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (event_id,circle_id,title,start,end,actor,str(args.get("location", ""))[:160],json.dumps(attendees),db.now(),idempotency_key))
            for attendee in set(attendees):
                if attendee != actor:
                    c.execute("INSERT INTO notifications(id,user_id,title,body,created_at,idempotency_key) VALUES(?,?,?,?,?,?)",
                              (db.uid(),attendee,"New calendar event",title,db.now(),"event-notice:"+idempotency_key+attendee))
            db.event(c,actor,"calendar",f"Scheduled {title}",circle_id)
            return {"ok":True,"event_id":event_id,"channel":"in-app calendar / ICS export"}

        if action_type == "send_message":
            user=str(args.get("user_id", ""))
            target=_validate_user(c,actor,user,circle_id)
            body=str(args.get("body", "")).strip()
            if not (1 <= len(body) <= 1000): _error(422,"Message must have 1-1000 characters")
            old=db.one(c,"SELECT id FROM notifications WHERE idempotency_key=?",(idempotency_key,))
            if old: return {"ok":True,"duplicate":True,"message_id":old["id"],"channel":"in-app"}
            message_id=db.uid()
            c.execute("INSERT INTO notifications(id,user_id,title,body,created_at,idempotency_key) VALUES(?,?,?,?,?,?)",
                      (message_id,user,"Message from LifePilot",body,db.now(),idempotency_key))
            db.event(c,actor,"message",f"Sent an in-app message to {target['name']}",circle_id)
    # Optional external delivery is explicitly reported separately; no fake success.
    delivery = {"channel":"in-app","external":"not-configured"}
    if os.environ.get("SLACK_WEBHOOK_URL"):
        try:
            req=urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"], data=json.dumps({"text":f"LifePilot → {target['name']}: {body}"}).encode(),headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=7) as res:
                delivery["external"]="slack-delivered" if res.status==200 else f"slack-http-{res.status}"
        except Exception as ex:
            delivery["external"]="slack-failed: " + type(ex).__name__
    elif os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"):
        try:
            msg=EmailMessage()
            msg["From"]=os.environ["SMTP_FROM"]
            msg["To"]=target["email"]
            msg["Subject"]="LifePilot message"
            msg.set_content(body)
            with smtplib.SMTP(os.environ["SMTP_HOST"],int(os.environ.get("SMTP_PORT","587")),timeout=10) as smtp:
                smtp.starttls()
                if os.environ.get("SMTP_USER"):
                    smtp.login(os.environ["SMTP_USER"],os.environ.get("SMTP_PASSWORD",""))
                smtp.send_message(msg)
            delivery["external"]="smtp-delivered"
        except Exception as ex:
            delivery["external"]="smtp-failed: " + type(ex).__name__
    return {"ok":True,"message_id":message_id,"type":"send_message",**delivery}


def fire_due_reminders() -> int:
    """Bounded polling. Exactly-once notification insert and completion in one transaction."""
    count=0
    with db.connect() as c:
        upcoming=db.rows(c,"SELECT * FROM reminders WHERE completed=0 AND due_at<=? LIMIT 100",(db.now(),))
        for reminder in upcoming:
            c.execute("INSERT OR IGNORE INTO notifications(id,user_id,title,body,created_at,idempotency_key) VALUES(?,?,?,?,?,?)",
                      (db.uid(),reminder["user_id"],"Reminder",reminder["title"],db.now(),"fired:"+reminder["id"]))
            c.execute("UPDATE reminders SET completed=1 WHERE id=?",(reminder["id"],))
            count+=1
    return count
