"""Development stdio MCP server; Vercel uses main.py Streamable HTTP."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

API_PATH = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_PATH))

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from app import db
from app.actions import execute
from app.security import verify_token, require_membership

mcp = MCPServer("LifePilot Circles Local")


def approved(tool: str, auth_token: str, proposal_id: str, action_index: int) -> dict:
    actor = verify_token(auth_token)
    with db.connect() as c:
        p = db.one(c, "SELECT * FROM proposals WHERE id=?", (proposal_id,))
        if not p or p["actor_id"] != actor or p["status"] != "executing":
            raise HTTPException(403, "Proposal not approved")
        actions = json.loads(p["actions"])
        if not 0 <= action_index < len(actions):
            raise HTTPException(422, "Unknown action index")
        action = actions[action_index]
        if action["type"] != tool or action["args"].get("circle_id") != p["circle_id"]:
            raise HTTPException(403, "Tool mismatch or unauthorized circle")
        require_membership(c, actor, p["circle_id"])
    return execute(tool, action["args"], auth_token, f"{proposal_id}:{action_index}")


@mcp.tool()
def assign_task(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute an approved circle task assignment."""
    return approved("assign_task", auth_token, proposal_id, action_index)


@mcp.tool()
def create_event(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute an approved circle event."""
    return approved("create_event", auth_token, proposal_id, action_index)


@mcp.tool()
def create_reminder(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute an approved circle reminder."""
    return approved("create_reminder", auth_token, proposal_id, action_index)


@mcp.tool()
def send_message(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Send an approved circle notification."""
    return approved("send_message", auth_token, proposal_id, action_index)


if __name__ == "__main__":
    db.initialize()
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http", stateless_http=True, json_response=True,
                host=os.environ.get("MCP_HTTP_HOST", "127.0.0.1"),
                port=int(os.environ.get("MCP_HTTP_PORT", "8010")))
    else:
        mcp.run()
