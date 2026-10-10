import json
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from app import db
from app import mcp_client
from app.main import app
from app.security import issue_token

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"DATABASE_PATH",tmp_path/"test.db")
    monkeypatch.setattr(mcp_client,"MCP_MODE","local")  # Direct adapter in unit tests; real MCP tested separately.
    with TestClient(app) as c:
        yield c

def auth(client,user="alex"):
    r=client.post("/api/auth/demo",json={"user_id":user})
    assert r.status_code==200,r.text
    return {"Authorization":"Bearer "+r.json()["token"]}

def plan(client,header,prompt="Assign Rahul the backend API task by Friday"):
    res=client.post("/api/assistant/plan",headers=header,json={"circle_id":"studio","prompt":prompt})
    assert res.status_code==200,res.text
    return res.json()

def test_health_and_bootstrap(client):
    assert client.get("/healthz").json()["ok"]
    assert client.get("/api/bootstrap").status_code==401
    r=client.get("/api/bootstrap",headers=auth(client))
    assert r.status_code==200
    payload=r.json()
    assert len(payload["circles"])==2
    assert len(payload["tasks"])>=5
    assert payload["demo"] is True

def test_no_mutation_before_approval_and_reject(client):
    headers=auth(client)
    original=len(client.get("/api/bootstrap",headers=headers).json()["tasks"])
    draft=plan(client,headers)
    assert draft["status"]=="pending"
    assert len(client.get("/api/bootstrap",headers=headers).json()["tasks"])==original
    rejected=client.post(f"/api/proposals/{draft['id']}/reject",headers=headers)
    assert rejected.status_code==200
    assert rejected.json()["executed"]==0
    assert len(client.get("/api/bootstrap",headers=headers).json()["tasks"])==original
    assert client.post(f"/api/proposals/{draft['id']}/approve",headers=headers).status_code==409

def test_approve_assigns_real_task_and_blocks_repeat(client):
    headers=auth(client)
    draft=plan(client,headers)
    assert draft["mode"]=="demo-rule-based"
    response=client.post(f"/api/proposals/{draft['id']}/approve",headers=headers)
    assert response.status_code==200,response.text
    assert response.json()["status"]=="executed"
    assert response.json()["executed"]==1
    assert client.post(f"/api/proposals/{draft['id']}/approve",headers=headers).status_code==409
    tasks=client.get("/api/bootstrap",headers=headers).json()["tasks"]
    newly=[t for t in tasks if t["assignee_id"]=="rahul" and "backend api" in t["title"].lower()]
    assert newly
    assert any("New assignment"==n["title"] for n in client.get("/api/bootstrap",headers=auth(client,"rahul")).json()["notifications"])

def test_scope_and_task_updates(client):
    alex=auth(client)
    rahul=auth(client,"rahul")
    task=client.get("/api/bootstrap",headers=alex).json()["tasks"][0]
    assert client.patch(f"/api/tasks/{task['id']}",headers=alex,json={"status":"done"}).status_code==200
    # Rahul isn't a member of home; he cannot create a task there.
    forbidden=client.post("/api/tasks",headers=rahul,json={"circle_id":"home","assignee_id":"alex","title":"Family-only task"})
    assert forbidden.status_code==403
    # And he cannot propose actions for home.
    forbidden=client.post("/api/assistant/plan",headers=rahul,json={"circle_id":"home","prompt":"Assign Alex a task"})
    assert forbidden.status_code==403

def test_calendar_ics_and_reminder(client):
    headers=auth(client)
    beginning=(datetime.now(timezone.utc)+timedelta(days=3)).replace(microsecond=0)
    result=client.post("/api/events",headers=headers,json={"circle_id":"studio","title":"Project kick-off","starts_at":beginning.isoformat(),"ends_at":(beginning+timedelta(hours=1)).isoformat(),"attendees":["alex","priya"]})
    assert result.status_code==201,result.text
    event_id=result.json()["event_id"]
    ics=client.get(f"/api/events/{event_id}/ics",headers=headers)
    assert ics.status_code==200
    assert "BEGIN:VCALENDAR" in ics.text
    past=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
    reminder=client.post("/api/reminders",headers=headers,json={"circle_id":"studio","title":"Do a thing","user_id":"alex","due_at":past})
    assert reminder.status_code==201
    delivered=client.post("/api/reminders/check",headers=headers)
    assert delivered.json()["delivered"]==1
    assert client.post("/api/reminders/check",headers=headers).json()["delivered"]==0
    notifications=client.get("/api/bootstrap",headers=headers).json()["notifications"]
    assert any(n["title"]=="Reminder" and n["body"]=="Do a thing" for n in notifications)

def test_safe_message_and_idempotency(client):
    from app.actions import execute
    token=auth(client)["Authorization"].split(" ",1)[1]
    args={"circle_id":"studio","user_id":"priya","body":"Please review the API demo"}
    first=execute("send_message",args,token,"once-only-23")
    second=execute("send_message",args,token,"once-only-23")
    assert first["ok"]
    assert second["duplicate"]
    with db.connect() as c:
        matches=db.rows(c,"SELECT id FROM notifications WHERE idempotency_key=?",("once-only-23",))
        assert len(matches)==1

def test_create_circle_invite_and_access(client):
    alex=auth(client)
    maya=auth(client,"maya")
    created=client.post("/api/circles",headers=alex,json={"name":"Weekend Adventure","description":"Plans with friends","member_ids":["priya"]})
    assert created.status_code==201,created.text
    circle_id=created.json()["id"]
    assert created.json()["members"]==2
    deny=client.post("/api/tasks",headers=maya,json={"circle_id":circle_id,"title":"Book hiking tickets","assignee_id":"maya"})
    assert deny.status_code==403
    invite=client.post(f"/api/circles/{circle_id}/members",headers=alex,json={"user_id":"maya"})
    assert invite.status_code==201,invite.text
    created_task=client.post("/api/tasks",headers=alex,json={"circle_id":circle_id,"title":"Book hiking tickets","assignee_id":"maya"})
    assert created_task.status_code==201,created_task.text
    visible=client.get("/api/bootstrap",headers=maya).json()["tasks"]
    assert any(t["title"]=="Book hiking tickets" for t in visible)
    # Member may not invite other members into a circle they don't own.
    forbid=client.post(f"/api/circles/{circle_id}/members",headers=maya,json={"user_id":"rahul"})
    assert forbid.status_code==403
