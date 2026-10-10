"""LifePilot Circles API. OpenAPI: /docs. Real changes require explicit approval."""
from __future__ import annotations
import asyncio
import json
import os
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import db
from .actions import execute as local_execute, fire_due_reminders
from .agent import make_plan
from .approval_graph import pause, resume
from .config import API_SECRET, DEMO_MODE, FRONTEND_ORIGIN, MCP_MODE
from .mcp_client import execute as execute_mcp
from .security import issue_token, require_demo, require_membership, verify_token

async def reminder_loop():
    while True:
        try: fire_due_reminders()
        except Exception as ex: print("reminder polling error:",type(ex).__name__)
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("VERCEL"):
        if len(API_SECRET) < 32 or API_SECRET in ("development-only-change-me", "replace-with-a-long-random-secret-before-deploying"):
            raise RuntimeError("Set a strong random API_SECRET on Vercel")
        if len(os.getenv("MCP_SERVICE_SECRET", "")) < 32:
            raise RuntimeError("Set a distinct strong MCP_SERVICE_SECRET on Vercel")
    elif not DEMO_MODE and API_SECRET in ("development-only-change-me", "replace-with-a-long-random-secret-before-deploying"):
        raise RuntimeError("Set a strong API_SECRET before disabling DEMO_MODE")
    db.initialize()
    # In-process recurring tasks cannot run reliably inside serverless functions.
    task = None if os.getenv("VERCEL") else asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass

app=FastAPI(title="LifePilot Circles API",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[origin.strip() for origin in FRONTEND_ORIGIN.split(",")],allow_credentials=True,allow_methods=["GET","POST","PATCH"],allow_headers=["Authorization","Content-Type"])

class LoginRequest(BaseModel):
    user_id: str

class PlanRequest(BaseModel):
    circle_id: str
    prompt: str = Field(min_length=5,max_length=1200)

class TaskRequest(BaseModel):
    circle_id: str
    title: str = Field(min_length=2,max_length=160)
    assignee_id: str
    priority: Literal["low","medium","high"]="medium"
    due_at: str|None=None

class StatusRequest(BaseModel):
    status: Literal["todo","in_progress","done"]

class EventRequest(BaseModel):
    circle_id: str
    title: str
    starts_at: str
    ends_at: str
    attendees: list[str]
    location: str=""

class ReminderRequest(BaseModel):
    circle_id: str
    user_id: str
    title: str
    due_at: str

class MessageRequest(BaseModel):
    circle_id: str
    user_id: str
    body: str

class CircleRequest(BaseModel):
    name: str = Field(min_length=3,max_length=60)
    description: str = Field(default="",max_length=150)
    icon: Literal["layers","home"]="layers"
    member_ids: list[str]=Field(default_factory=list,max_length=20)

class CircleInviteRequest(BaseModel):
    user_id: str


def actor(authorization: str|None=Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Sign in first")
    user_id=verify_token(authorization[7:])
    with db.connect() as c:
        if not db.one(c,"SELECT id FROM users WHERE id=?",(user_id,)):
            raise HTTPException(401,"Account no longer exists")
    return user_id

def self_token(user_id: str): return issue_token(user_id)

@app.get("/healthz")
def health(): return {"ok":True,"service":"lifepilot-api"}

@app.get("/api/auth/demo-users")
def demo_users():
    require_demo()
    with db.connect() as c:
        return db.rows(c,"SELECT id,name,avatar,color FROM users ORDER BY CASE WHEN id='alex' THEN 0 ELSE 1 END,name")

@app.post("/api/auth/demo")
def login(data:LoginRequest):
    require_demo()
    with db.connect() as c:
        user=db.one(c,"SELECT id,name,avatar,color,email FROM users WHERE id=?",(data.user_id,))
        if not user: raise HTTPException(404,"Demo user not found")
    return {"token":self_token(user["id"]),"user":user,"demo":True}

@app.get("/api/bootstrap")
def bootstrap(user_id:str=Depends(actor)):
    with db.connect() as c:
        user=db.one(c,"SELECT id,name,email,avatar,color,role FROM users WHERE id=?",(user_id,))
        circles=db.rows(c,"SELECT c.*,m.role AS membership_role FROM circles c JOIN memberships m ON m.circle_id=c.id WHERE m.user_id=? ORDER BY c.name",(user_id,))
        circle_ids=[x["id"] for x in circles]
        if not circles: return {"user":user,"circles":[],"members":[],"tasks":[],"events":[],"reminders":[],"notifications":[],"activity":[],"proposals":[],"connections":{}}
        marks=",".join("?" for _ in circle_ids)
        members=db.rows(c,f"SELECT DISTINCT u.id,u.name,u.email,u.avatar,u.color FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.circle_id IN ({marks}) ORDER BY u.name",circle_ids)
        tasks=db.rows(c,f"SELECT t.*,u.name AS assignee_name,u.avatar AS assignee_avatar,u.color AS assignee_color FROM tasks t JOIN users u ON t.assignee_id=u.id WHERE t.circle_id IN ({marks}) ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'todo' THEN 1 ELSE 2 END, t.created_at DESC",circle_ids)
        events=db.rows(c,f"SELECT * FROM events WHERE circle_id IN ({marks}) ORDER BY starts_at ASC",circle_ids)
        reminders=db.rows(c,"SELECT * FROM reminders WHERE user_id=? ORDER BY due_at ASC",(user_id,))
        notifications=db.rows(c,"SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20",(user_id,))
        activity=db.rows(c,f"SELECT a.*,u.name AS actor_name,u.avatar AS actor_avatar,u.color AS actor_color FROM activity a JOIN users u ON a.actor_id=u.id WHERE a.circle_id IN ({marks}) ORDER BY a.created_at DESC LIMIT 30",circle_ids)
        proposals=db.rows(c,"SELECT * FROM proposals WHERE actor_id=? ORDER BY created_at DESC LIMIT 20",(user_id,))
    for e in events: e["attendees"]=json.loads(e["attendees"])
    for p in proposals:
        p["actions"]=json.loads(p["actions"])
        p["outcomes"]=json.loads(p["outcomes"])
    return {"user":user,"circles":circles,"members":members,"tasks":tasks,"events":events,"reminders":reminders,"notifications":notifications,"activity":activity,"proposals":proposals,
            "connections":{"mcp":MCP_MODE,"ai":"nvidia" if os.getenv("NVIDIA_API_KEY") else "demo planner","calendar":"local + ICS","slack":"connected" if os.getenv("SLACK_WEBHOOK_URL") else "not connected","email":"connected" if os.getenv("SMTP_HOST") else "not connected"},"demo":DEMO_MODE}

@app.post("/api/assistant/plan")
def propose(payload:PlanRequest,user_id:str=Depends(actor)):
    with db.connect() as c: require_membership(c,user_id,payload.circle_id)
    try: plan=make_plan(payload.prompt,payload.circle_id,user_id)
    except ValueError as ex: raise HTTPException(422,str(ex)) from ex
    except RuntimeError as ex: raise HTTPException(503,str(ex)) from ex
    proposal_id=db.uid()
    with db.connect() as c:
        c.execute("INSERT INTO proposals(id,actor_id,circle_id,prompt,summary,actions,mode,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (proposal_id,user_id,payload.circle_id,payload.prompt,plan["summary"],json.dumps(plan["actions"]),plan["mode"],db.now()))
        db.event(c,user_id,"proposal","Prepared a plan for review",payload.circle_id)
    graph_mode=pause(proposal_id,plan["summary"])
    return {"id":proposal_id,"circle_id":payload.circle_id,"prompt":payload.prompt,"status":"pending","graph":graph_mode,**plan}

@app.post("/api/proposals/{proposal_id}/reject")
def reject(proposal_id:str,user_id:str=Depends(actor)):
    with db.connect() as c:
        p=db.one(c,"SELECT * FROM proposals WHERE id=? AND actor_id=?",(proposal_id,user_id))
        if not p: raise HTTPException(404,"Proposal not found")
        if p["status"]!="pending": raise HTTPException(409,"Proposal was already decided")
    resume(proposal_id,p["summary"],False)
    with db.connect() as c:
        updated=c.execute("UPDATE proposals SET status='rejected', decided_at=? WHERE id=? AND status='pending'",(db.now(),proposal_id)).rowcount
        if not updated: raise HTTPException(409,"Proposal was already decided")
        db.event(c,user_id,"rejection","Rejected a proposed action plan",p["circle_id"])
    return {"id":proposal_id,"status":"rejected","executed":0}

@app.post("/api/proposals/{proposal_id}/approve")
async def approve(proposal_id:str,user_id:str=Depends(actor)):
    with db.connect() as c:
        p=db.one(c,"SELECT * FROM proposals WHERE id=? AND actor_id=?",(proposal_id,user_id))
        if not p: raise HTTPException(404,"Proposal not found")
        require_membership(c,user_id,p["circle_id"])
        if p["status"]!="pending": raise HTTPException(409,"Proposal was already decided")
    if not resume(proposal_id,p["summary"],True): raise HTTPException(409,"Approval workflow rejected")
    with db.connect() as c:
        updated=c.execute("UPDATE proposals SET status='executing', decided_at=? WHERE id=? AND status='pending'",(db.now(),proposal_id)).rowcount
        if not updated: raise HTTPException(409,"Proposal was already decided")
    actions=json.loads(p["actions"])
    outcomes=[]
    token=self_token(user_id)
    for index,action in enumerate(actions):
        try:
            response=await execute_mcp(action,token,f"{proposal_id}:{index}")
            outcomes.append({"action":action["type"],"label":action["label"],"ok":True,"result":response})
        except Exception as ex:
            # Explicit per-action failure; never claim a false success.
            outcomes.append({"action":action["type"],"label":action["label"],"ok":False,"error":str(ex)[:260]})
    successes=sum(1 for x in outcomes if x["ok"])
    status="executed" if successes==len(outcomes) else "partial" if successes else "failed"
    with db.connect() as c:
        c.execute("UPDATE proposals SET status=?,outcomes=? WHERE id=?",(status,json.dumps(outcomes),proposal_id))
        db.event(c,user_id,"execution",f"{successes}/{len(outcomes)} actions completed",p["circle_id"])
    return {"id":proposal_id,"status":status,"executed":successes,"total":len(outcomes),"outcomes":outcomes}

class InternalActionRequest(BaseModel):
    tool: Literal["assign_task", "create_event", "create_reminder", "send_message"]
    proposal_id: str
    action_index: int = Field(ge=0, le=3)
    auth_token: str


@app.post("/internal/mcp/execute", include_in_schema=False)
def execute_approved_mcp_action(
    body: InternalActionRequest,
    x_mcp_service_secret: str | None = Header(None),
):
    """MCP may only execute the exact approved action stored in PostgreSQL."""
    expected = os.environ.get("MCP_SERVICE_SECRET", "")
    if not expected or not x_mcp_service_secret or not hmac.compare_digest(expected, x_mcp_service_secret):
        raise HTTPException(403, "Internal MCP service authorization failed")
    user_id = verify_token(body.auth_token)
    with db.connect() as c:
        proposal = db.one(c, "SELECT * FROM proposals WHERE id=?", (body.proposal_id,))
        if not proposal or proposal["actor_id"] != user_id or proposal["status"] not in ("executing", "partial"):
            raise HTTPException(403, "An approved executing proposal is required")
        actions = json.loads(proposal["actions"])
        if body.action_index >= len(actions):
            raise HTTPException(422, "Unknown action index")
        selected = actions[body.action_index]
        if selected["type"] != body.tool or selected["args"].get("circle_id") != proposal["circle_id"]:
            raise HTTPException(403, "Tool does not match approved plan")
        require_membership(c, user_id, proposal["circle_id"])
    return local_execute(body.tool, selected["args"], body.auth_token, f"{body.proposal_id}:{body.action_index}")


@app.get("/api/cron/reminders", include_in_schema=False)
def scheduled_reminders(authorization: str | None = Header(None)):
    """Invocation endpoint for a scheduler; no paid recurring cron enabled."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret or not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(403, "Scheduler authorization failed")
    return {"delivered": fire_due_reminders()}


@app.post("/api/circles",status_code=201)
def create_circle(payload:CircleRequest,user_id:str=Depends(actor)):
    circle_id=db.uid()
    with db.connect() as c:
        for target in payload.member_ids:
            if not db.one(c,"SELECT id FROM users WHERE id=?",(target,)):
                raise HTTPException(404,f"Member {target} not found")
        c.execute("INSERT INTO circles(id,name,icon,color,description) VALUES(?,?,?,?,?)",
                  (circle_id,payload.name.strip(),payload.icon,"coral" if payload.icon=="home" else "violet",payload.description))
        members=set([user_id]+payload.member_ids)
        for member in members:
            c.execute("INSERT INTO memberships(user_id,circle_id,role) VALUES(?,?,?)",
                      (member,circle_id,"owner" if member==user_id else "member"))
            if member!=user_id:
                c.execute("INSERT INTO notifications(id,user_id,title,body,created_at) VALUES(?,?,?,?,?)",
                          (db.uid(),member,"Circle invitation",f"You've joined {payload.name}",db.now()))
        db.event(c,user_id,"workspace",f"Created circle: {payload.name}",circle_id)
    return {"id":circle_id,"name":payload.name,"members":len(members)}

@app.post("/api/circles/{circle_id}/members",status_code=201)
def invite_member(circle_id:str,payload:CircleInviteRequest,user_id:str=Depends(actor)):
    with db.connect() as c:
        role=require_membership(c,user_id,circle_id)
        if role["role"]!="owner":raise HTTPException(403,"Only circle owner can invite members")
        target=db.one(c,"SELECT id,name FROM users WHERE id=?",(payload.user_id,))
        if not target:raise HTTPException(404,"User does not exist")
        if db.one(c,"SELECT 1 FROM memberships WHERE user_id=? AND circle_id=?",(payload.user_id,circle_id)):
            raise HTTPException(409,"Already a member")
        c.execute("INSERT INTO memberships(user_id,circle_id,role) VALUES(?,?,?)",(payload.user_id,circle_id,"member"))
        circle=db.one(c,"SELECT name FROM circles WHERE id=?",(circle_id,))
        c.execute("INSERT INTO notifications(id,user_id,title,body,created_at) VALUES(?,?,?,?,?)",
                  (db.uid(),payload.user_id,"Circle invitation",f"You've joined {circle['name']}",db.now()))
        db.event(c,user_id,"workspace",f"Invited {target['name']} to circle",circle_id)
    return {"ok":True,"circle_id":circle_id,"user_id":payload.user_id}

@app.post("/api/tasks",status_code=201)
def new_task(payload:TaskRequest,user_id:str=Depends(actor)):
    from .actions import execute
    return execute("assign_task",payload.model_dump(exclude_none=True),self_token(user_id),"manual-"+db.uid())

@app.patch("/api/tasks/{task_id}")
def change_task(task_id:str,payload:StatusRequest,user_id:str=Depends(actor)):
    with db.connect() as c:
        task=db.one(c,"SELECT * FROM tasks WHERE id=?",(task_id,))
        if not task: raise HTTPException(404,"Task not found")
        member=require_membership(c,user_id,task["circle_id"])
        if user_id not in (task["assignee_id"],task["created_by"]) and member["role"]!="owner":
            raise HTTPException(403,"Only assignee, creator or circle owner can update")
        c.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?",(payload.status,db.now(),task_id))
        db.event(c,user_id,"task",f"Updated ‘{task['title']}’ to {payload.status.replace('_',' ')}",task["circle_id"])
    return {"id":task_id,"status":payload.status}

@app.post("/api/events",status_code=201)
def new_event(payload:EventRequest,user_id:str=Depends(actor)):
    return local_execute("create_event",payload.model_dump(),self_token(user_id),"manual-"+db.uid())

@app.post("/api/reminders",status_code=201)
def new_reminder(payload:ReminderRequest,user_id:str=Depends(actor)):
    return local_execute("create_reminder",payload.model_dump(),self_token(user_id),"manual-"+db.uid())

@app.post("/api/messages",status_code=201)
def message(payload:MessageRequest,user_id:str=Depends(actor)):
    return local_execute("send_message",payload.model_dump(),self_token(user_id),"manual-"+db.uid())

@app.post("/api/reminders/check")
def reminders_check(user_id:str=Depends(actor)):
    return {"delivered":fire_due_reminders()}

@app.post("/api/notifications/{notification_id}/read")
def mark_read(notification_id:str,user_id:str=Depends(actor)):
    with db.connect() as c:
        updated=c.execute("UPDATE notifications SET read_at=? WHERE id=? AND user_id=?",(db.now(),notification_id,user_id)).rowcount
        if not updated: raise HTTPException(404,"Notification not found")
    return {"ok":True}

@app.get("/api/events/{event_id}/ics")
def download_ics(event_id:str,user_id:str=Depends(actor)):
    with db.connect() as c:
        e=db.one(c,"SELECT * FROM events WHERE id=?",(event_id,))
        if not e: raise HTTPException(404,"Event not found")
        require_membership(c,user_id,e["circle_id"])
    def ics_dt(iso):
        dt=datetime.fromisoformat(iso.replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    def esc(v):return str(v).replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")
    content="\r\n".join(["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//LifePilot Circles//EN","BEGIN:VEVENT",f"UID:{e['id']}@lifepilot.local",f"DTSTAMP:{ics_dt(db.now())}",f"DTSTART:{ics_dt(e['starts_at'])}",f"DTEND:{ics_dt(e['ends_at'])}",f"SUMMARY:{esc(e['title'])}",f"LOCATION:{esc(e['location'])}","END:VEVENT","END:VCALENDAR",""])
    return Response(content=content,media_type="text/calendar",headers={"Content-Disposition":f"attachment; filename=lifepilot-{event_id[:8]}.ics"})
