"""Optional real MCP 2.x stdio integration with a persisted executing proposal."""
import sys
import asyncio
import json
import pytest


def test_actual_mcp_protocol(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters
    from app import db
    from app.security import issue_token
    from app.config import ROOT

    monkeypatch.setattr(db,"DATABASE_PATH",tmp_path/"mcp.db")
    monkeypatch.setenv("DATABASE_PATH",str(tmp_path/"mcp.db"))
    db.initialize()
    proposal_id = "mcp-integration-approved"
    actions = [{"type":"assign_task","label":"Test","args":{
        "circle_id":"studio","assignee_id":"rahul","title":"MCP integration task"}}]
    with db.connect() as c:
        c.execute(
            "INSERT INTO proposals(id,actor_id,circle_id,prompt,summary,actions,mode,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (proposal_id,"alex","studio","MCP integration","MCP integration",json.dumps(actions),
             "test","executing",db.now())
        )
    server = StdioServerParameters(command=sys.executable,args=[str(ROOT/"services/mcp-server/server.py")])
    async def run():
        async with Client(server) as client:
            listing = await client.list_tools()
            assert {"assign_task","create_event"}.issubset({t.name for t in listing.tools})
            result = await client.call_tool("assign_task",{
                "auth_token":issue_token("alex"),"proposal_id":proposal_id,"action_index":0
            })
            assert result.is_error is False,result.content
    asyncio.run(run())
    with db.connect() as c:
        assert db.one(c,"SELECT id FROM tasks WHERE title=?",("MCP integration task",))
