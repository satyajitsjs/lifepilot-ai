"""Optional real MCP 2.x stdio integration check. Requires `pip install mcp>=2`."""
import sys
import asyncio
from pathlib import Path
import pytest

def test_actual_mcp_protocol(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters
    from app import db
    from app.security import issue_token
    from app.config import ROOT
    monkeypatch.setattr(db,"DATABASE_PATH",tmp_path/"mcp.db")
    db.initialize()
    from app.config import API_SECRET
    # Child inherits database path by environment rather than parent's monkeypatch.
    monkeypatch.setenv("DATABASE_PATH",str(tmp_path/"mcp.db"))
    server=StdioServerParameters(command=sys.executable,args=[str(ROOT/"services/mcp-server/server.py")])
    async def run():
        async with Client(server) as client:
            tool_list=await client.list_tools()
            names=[t.name for t in tool_list.tools]
            assert "assign_task" in names
            assert "create_event" in names
            result=await client.call_tool("assign_task",{
                "auth_token":issue_token("alex"),"circle_id":"studio","assignee_id":"rahul",
                "title":"MCP integration task","idempotency_key":"mcp-integration-1"
            })
            assert result.is_error is False, result.content
    asyncio.run(run())
    with db.connect() as c:
        assert db.one(c,"SELECT id FROM tasks WHERE title=?",("MCP integration task",))
