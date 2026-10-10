"""Run only approved MCP tools, over private HTTP on Vercel or stdio locally."""
from __future__ import annotations
import json
import os
import sys
from .config import ROOT, MCP_MODE

TOOL_NAMES = frozenset({"assign_task", "create_event", "create_reminder", "send_message"})


async def execute(action: dict, auth_token: str, idempotency_key: str) -> dict:
    kind = action["type"]
    if kind not in TOOL_NAMES:
        raise ValueError("Unknown MCP tool")
    proposal_id, index = idempotency_key.rsplit(":", 1)
    if not proposal_id or not index.isdigit():
        raise ValueError("MCP calls must identify a persisted approval proposal")

    if MCP_MODE == "local":
        if os.getenv("VERCEL"):
            raise RuntimeError("MCP_MODE=local is forbidden on Vercel; use MCP_SERVICE_URL")
        # Explicit local unit test adapter only; not MCP.
        from .actions import execute as local_execute
        return local_execute(kind, action["args"], auth_token, idempotency_key)

    from mcp import Client, StdioServerParameters
    if MCP_MODE == "http":
        base = os.getenv("MCP_SERVICE_URL", "").rstrip("/")
        if not base:
            raise RuntimeError("MCP_SERVICE_URL service binding missing")
        client_args = base + "/mcp"
    elif MCP_MODE == "stdio":
        server_path = ROOT / "services/mcp-server/server.py"
        if not server_path.is_file():
            raise RuntimeError("Local MCP server script is missing")
        client_args = StdioServerParameters(command=sys.executable, args=[str(server_path)])
    else:
        raise RuntimeError("Unknown MCP_MODE")

    # The MCP tool receives no AI-generated action data. The API reads the
    # exact persisted approved action based on proposal_id + action_index.
    async with Client(client_args) as client:
        result = await client.call_tool(kind, {
            "auth_token": auth_token,
            "proposal_id": proposal_id,
            "action_index": int(index),
        })
        if result.is_error:
            raise RuntimeError("MCP tool error: " + str(result.content)[:350])
        payload = result.structured_content
        if payload is None and result.content:
            payload = json.loads(result.content[0].text)
        if isinstance(payload, dict) and set(payload) == {"result"}:
            payload = payload["result"]
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise RuntimeError("Invalid MCP tool response: " + str(payload)[:300])
        return payload
