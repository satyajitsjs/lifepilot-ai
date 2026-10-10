"""Calls MCP 2.x tools over the actual stdio protocol. Local mode only for isolated tests."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from .config import ROOT, MCP_MODE

TOOL_NAMES={"assign_task":"assign_task", "create_event":"create_event","create_reminder":"create_reminder","send_message":"send_message"}

async def execute(action:dict,auth_token:str,idempotency_key:str) -> dict:
    kind=action["type"]
    if kind not in TOOL_NAMES: raise ValueError("Unknown tool")
    args={**action["args"],"auth_token":auth_token,"idempotency_key":idempotency_key}
    if MCP_MODE == "local":
        from .actions import execute as local_exec
        return local_exec(kind,action["args"],auth_token,idempotency_key)
    from mcp import Client, StdioServerParameters
    server_path=ROOT / "services" / "mcp-server" / "server.py"
    if not server_path.is_file():
        raise RuntimeError(
            "MCP server is not packaged inside this Vercel API service. "
            "Deploy a reviewed MCP transport, or explicitly set MCP_MODE=local "
            "for an in-process non-MCP preview only."
        )
    parameters=StdioServerParameters(command=sys.executable,args=[str(server_path)])
    async with Client(parameters) as client:
        result=await client.call_tool(TOOL_NAMES[kind],args)
        if result.is_error:
            raise RuntimeError("MCP tool returned an error: " + str(result.content)[:400])
        content=result.structured_content
        if content is None and result.content:
            content=json.loads(result.content[0].text)
        if isinstance(content,dict) and "result" in content and len(content)==1:
            content=content["result"]
        if not isinstance(content,dict) or not content.get("ok"):
            raise RuntimeError("Unexpected MCP response: " + str(content)[:300])
        return content
