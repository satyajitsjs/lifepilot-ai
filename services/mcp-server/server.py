"""Actual MCP 2.x server. Use `--http` only behind a real auth proxy for public access."""
from __future__ import annotations
import os
import sys
from pathlib import Path

API_PARENT = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_PARENT))

from mcp.server.mcpserver import MCPServer
from app.actions import execute
from app.db import initialize

mcp = MCPServer("LifePilot Circles")


@mcp.tool()
def assign_task(auth_token: str, circle_id: str, assignee_id: str, title: str,
                idempotency_key: str, priority: str = "medium", due_at: str = "") -> dict:
    """Assign a task to a verified member of the selected circle. Requires signed actor token and user approval."""
    return execute("assign_task", dict(circle_id=circle_id,assignee_id=assignee_id,title=title,priority=priority,due_at=due_at), auth_token,idempotency_key)


@mcp.tool()
def create_reminder(auth_token: str, circle_id: str, user_id: str, title: str,
                    due_at: str, idempotency_key: str) -> dict:
    """Schedule a real persisted in-app reminder for a circle member after approval."""
    return execute("create_reminder",dict(circle_id=circle_id,user_id=user_id,title=title,due_at=due_at),auth_token,idempotency_key)


@mcp.tool()
def create_event(auth_token: str, circle_id: str, title: str, starts_at: str, ends_at: str,
                 attendees: list[str], idempotency_key: str, location: str = "") -> dict:
    """Create a circle calendar event, notify attendees and allow ICS export. Requires approval."""
    return execute("create_event",dict(circle_id=circle_id,title=title,starts_at=starts_at,ends_at=ends_at,attendees=attendees,location=location),auth_token,idempotency_key)


@mcp.tool()
def send_message(auth_token: str, circle_id: str, user_id: str, body: str,
                 idempotency_key: str) -> dict:
    """Send persisted in-app notification and optionally Slack/SMTP if configured and authorized."""
    return execute("send_message",dict(circle_id=circle_id,user_id=user_id,body=body),auth_token,idempotency_key)


if __name__ == "__main__":
    initialize()
    if "--http" in sys.argv:
        # Loopback only by default. Add standards-compliant OAuth before public exposure.
        mcp.run(transport="streamable-http",stateless_http=True,json_response=True,
                host=os.environ.get("MCP_HTTP_HOST","127.0.0.1"),port=int(os.environ.get("MCP_HTTP_PORT","8010")))
    else:
        mcp.run()
