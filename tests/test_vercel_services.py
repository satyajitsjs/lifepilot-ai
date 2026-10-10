"""Vercel Services topology and server-side approval/credential checks."""
from __future__ import annotations
import json
from pathlib import Path
from app import db
from app.security import issue_token
from test_workflows import client  # Shared isolated SQLite TestClient fixture.

REPO = Path(__file__).resolve().parents[1]


def test_three_services_and_private_bindings():
    cfg = json.loads((REPO / "vercel.json").read_text())
    assert set(cfg["services"]) == {"web", "api", "mcp"}
    assert cfg["services"]["web"]["bindings"] == [
        {"type":"service", "service":"api", "format":"url", "env":"API_SERVICE_URL"}
    ]
    assert cfg["services"]["api"]["bindings"] == [
        {"type":"service", "service":"mcp", "format":"url", "env":"MCP_SERVICE_URL"}
    ]
    assert cfg["services"]["mcp"]["bindings"] == [
        {"type":"service", "service":"api", "format":"url", "env":"API_INTERNAL_URL"}
    ]
    assert [r["destination"]["service"] for r in cfg["rewrites"]] == ["web"]


def test_postgres_placeholder_translation():
    assert db.postgres_sql("SELECT * FROM users WHERE id=?") == "SELECT * FROM users WHERE id=%s"
    assert db.postgres_sql("INSERT OR IGNORE INTO notifications VALUES (?,?)") == (
        "INSERT INTO notifications VALUES (%s,%s) ON CONFLICT DO NOTHING"
    )


def test_private_mcp_requires_approval(client, monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_SECRET", "a-different-long-test-secret-of-at-least-32-characters")
    header = {"X-MCP-Service-Secret":"a-different-long-test-secret-of-at-least-32-characters"}
    token = issue_token("alex")
    draft = client.post("/api/assistant/plan", json={
        "circle_id":"studio", "prompt":"Assign Rahul the backend API task by Friday"
    }, headers={"Authorization":"Bearer " + token})
    assert draft.status_code == 200, draft.text
    proposal_id = draft.json()["id"]
    payload = {"tool":"assign_task","proposal_id":proposal_id,"action_index":0,"auth_token":token}
    url = "/internal/mcp/execute"

    assert client.post(url,json=payload).status_code == 403
    assert client.post(url,headers=header,json=payload).status_code == 403
    with db.connect() as c:
        # Simulate the API's atomic approval transition without invoking MCP.
        c.execute("UPDATE proposals SET status='executing' WHERE id=?", (proposal_id,))
    assert client.post(url,headers=header,json={**payload,"auth_token":issue_token("rahul")}).status_code == 403
    assert client.post(url,headers=header,json={**payload,"tool":"send_message"}).status_code == 403

    executed = client.post(url,headers=header,json=payload)
    assert executed.status_code == 200, executed.text
    assert executed.json()["ok"] is True
    retry = client.post(url,headers=header,json=payload)
    assert retry.status_code == 200 and retry.json()["duplicate"] is True
    with db.connect() as c:
        tasks = db.rows(c,"SELECT id FROM tasks WHERE idempotency_key=?",(proposal_id + ":0",))
    assert len(tasks) == 1


def test_scheduler_requires_cron_secret(client, monkeypatch):
    path = "/api/cron/reminders"
    assert client.get(path).status_code == 403
    monkeypatch.setenv("CRON_SECRET","test-cron-secret")
    assert client.get(path,headers={"Authorization":"Bearer wrong"}).status_code == 403
    result = client.get(path,headers={"Authorization":"Bearer test-cron-secret"})
    assert result.status_code == 200 and result.json()["delivered"] >= 0


def test_vercel_without_database_fails_closed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL",raising=False)
    monkeypatch.setenv("VERCEL","1")
    try:
        with db.connect():
            pass
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("Vercel must not use SQLite /tmp")
