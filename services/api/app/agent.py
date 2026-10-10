"""Goal -> strictly validated proposed actions. No side effects in this module."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timedelta, timezone
from . import db


def _date_from_text(text: str, *, hour: int = 15) -> datetime:
    current=datetime.now(timezone.utc)
    lower=text.lower()
    if "tomorrow" in lower: day=current+timedelta(days=1)
    elif "today" in lower: day=current
    else:
        weekdays={"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
        matched=next((day for day in weekdays if day in lower),None)
        if matched:
            days=(weekdays[matched]-current.weekday())%7
            day=current+timedelta(days=days or 7)
        else: day=current+timedelta(days=2)
    time_match=re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(am|pm)\b",lower)
    if time_match:
        hour=int(time_match.group(1))%12 + (12 if time_match.group(3)=="pm" else 0)
        minute=int(time_match.group(2) or 0)
    else: minute=0
    return day.replace(hour=hour,minute=minute,second=0,microsecond=0)


def _known_users(conn,circle_id):
    return db.rows(conn,"SELECT users.id,users.name FROM users JOIN memberships m ON m.user_id=users.id WHERE m.circle_id=?",(circle_id,))


def _fallback_plan(text: str,circle_id: str,actor_id: str,people: list[dict]) -> dict:
    """Explicit deterministic demo mode; never call this AI-generated."""
    lower=text.lower()
    named=[u for u in people if u["id"]!=actor_id and (u["id"] in lower or u["name"].split()[0].lower() in lower)]
    recipient=named[0]["id"] if named else actor_id
    other=[u["id"] for u in named] or [actor_id]
    stamp=_date_from_text(text)
    task_due_match=re.search(r"\b(?:by|due(?:\s+on)?)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)",lower)
    task_stamp=_date_from_text(task_due_match.group(1)) if task_due_match else stamp
    reminder_fragment=lower[lower.index("remind"):] if "remind" in lower else lower
    reminder_stamp=_date_from_text(reminder_fragment,hour=9) if "remind" in lower else stamp
    actions=[]
    meeting=any(term in lower for term in ["meeting","calendar","schedule","sync","review call","appointment"])
    sending=any(term in lower for term in ["message","notify","tell ","send ","email","communicate"])
    reminder=any(term in lower for term in ["remind","reminder","follow up","follow-up"])
    assignment=any(term in lower for term in ["task","assign","complete","finish","build","prepare","organize"])
    if assignment or not (meeting or reminder or sending):
        title=re.sub(r"^(hey |alexa,? |please |can you |could you )+", "",text,flags=re.I)
        title=re.sub(r"^(assign |create a task to |make a task to )", "",title,flags=re.I)
        title=title.strip(" .")[:125] or "New shared task"
        actions.append({"type":"assign_task","label":f"Assign a task to {recipient.title()}","args":{"circle_id":circle_id,"assignee_id":recipient,"title":title,"priority":"high" if "urgent" in lower else "medium","due_at":task_stamp.date().isoformat()}})
    if meeting:
        title="Team coordination meeting" if not any(t in lower for t in ["design","sprint","review","birthday","dinner"]) else "Team " + next((term for term in ["design","sprint","review","birthday","dinner"] if term in lower),"sync").title()
        actions.append({"type":"create_event","label":"Schedule a shared calendar event","args":{"circle_id":circle_id,"title":title,"starts_at":stamp.isoformat(),"ends_at":(stamp+timedelta(hours=1)).isoformat(),"attendees":list(set([actor_id]+other))}})
    if reminder:
        actions.append({"type":"create_reminder","label":f"Create a reminder for {recipient.title()}","args":{"circle_id":circle_id,"user_id":recipient,"title":"Follow up: " + text[:95],"due_at":reminder_stamp.isoformat()}})
    if sending:
        actions.append({"type":"send_message","label":f"Notify {recipient.title()} (in-app; external if configured)","args":{"circle_id":circle_id,"user_id":recipient,"body":text[:600]}})
    return {"summary":f"I prepared {len(actions)} action{'s' if len(actions)!=1 else ''} for your circle. Review before anything runs.","actions":actions,"mode":"demo-rule-based"}


SYSTEM = """You are LifePilot Circles, an action planning assistant. Return ONLY a valid JSON object:
{{"summary":"...", "actions":[{{"type":"assign_task|create_event|create_reminder|send_message", "label":"short UI label", "args":{{...}}}}]}}.
All actions must be within the supplied circle_id. Only reference provided member IDs. Never invent people.
assign_task args: circle_id, assignee_id, title, priority ('low'|'medium'|'high'), due_at (ISO date or '').
create_event args: circle_id, title, starts_at and ends_at (ISO-8601 with timezone), attendees (member IDs array).
create_reminder args: circle_id, user_id, title, due_at (ISO-8601 with timezone).
send_message args: circle_id, user_id, body. User approval required; do NOT execute anything.
If user requests multiple actions, produce multiple actions (max 4). No payment, destructive action or purchasing.
Current UTC datetime: {utc}. Circle: {circle_id}. Requester ID: {actor_id}. Available members: {people}.
"""


def validate_actions(result:dict,circle_id:str,people:list[dict]) -> dict:
    if not isinstance(result,dict) or not isinstance(result.get("actions"),list):
        raise ValueError("Expected actions list")
    members={u["id"] for u in people}
    valid=[]
    for act in result["actions"][:4]:
        if not isinstance(act,dict) or act.get("type") not in ("assign_task","create_event","create_reminder","send_message"):
            raise ValueError("Unknown action")
        args=act.get("args")
        if not isinstance(args,dict): raise ValueError("Missing tool args")
        if args.get("circle_id")!=circle_id: raise ValueError("Wrong circle")
        target=args.get("assignee_id",args.get("user_id"))
        if target is not None and target not in members: raise ValueError("Invalid recipient")
        if "attendees" in args and (not isinstance(args["attendees"],list) or any(u not in members for u in args["attendees"])):
            raise ValueError("Invalid attendees")
        if act["type"]=="assign_task" and not str(args.get("title", "")).strip(): raise ValueError("Empty task")
        if act["type"]=="create_reminder" and not args.get("due_at"): raise ValueError("Missing due_at")
        if act["type"]=="create_event" and (not args.get("starts_at") or not args.get("ends_at")): raise ValueError("Missing event dates")
        if act["type"]=="send_message" and not str(args.get("body", "")).strip(): raise ValueError("Missing message")
        valid.append({"type":act["type"],"label":str(act.get("label") or act["type"])[:140],"args":args})
    if not valid: raise ValueError("No actions")
    return {"summary":str(result.get("summary", "Here's a plan to review."))[:300],"actions":valid}


def make_plan(prompt:str,circle_id:str,actor_id:str) -> dict:
    with db.connect() as c: people=_known_users(c,circle_id)
    if not 5<=len(prompt)<=1200:
        raise ValueError("Please describe your request in 5–1200 characters")
    key=os.environ.get("NVIDIA_API_KEY")
    if key:
        try:
            from langchain_openai import ChatOpenAI
            llm=ChatOpenAI(model=os.getenv("NVIDIA_MODEL","nvidia/nemotron-3-ultra-550b-a55b"),api_key=key,base_url="https://integrate.api.nvidia.com/v1",use_responses_api=False,max_tokens=850,temperature=0)
            system=SYSTEM.format(utc=db.now(),circle_id=circle_id,actor_id=actor_id,people=json.dumps(people))
            response=llm.invoke([("system",system),("human",prompt)])
            raw=response.content if isinstance(response.content,str) else str(response.content)
            raw=re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip())
            validated=validate_actions(json.loads(raw),circle_id,people)
            return {**validated,"mode":"nvidia-nemotron"}
        except Exception as ex:
            # Never claim an AI-generated plan when the provider fails.
            raise RuntimeError(f"AI provider failed ({type(ex).__name__}); check key/model and retry, or disable it for demo mode") from ex
    fallback=_fallback_plan(prompt,circle_id,actor_id,people)
    validated=validate_actions(fallback,circle_id,people)
    return {**validated,"mode":"demo-rule-based"}
