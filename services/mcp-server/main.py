"""Private Vercel MCP Streamable HTTP service. All writes require DB approval."""
from __future__ import annotations
import os
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

mcp = MCPServer("LifePilot Circles")


async def _execute(tool: str, auth_token: str, proposal_id: str, action_index: int) -> dict:
    # Service bindings grant network reachability, not authorization.
    base = os.environ.get("API_INTERNAL_URL", "").rstrip("/")
    secret = os.environ.get("MCP_SERVICE_SECRET", "")
    if not base or not secret:
        raise ValueError("Required API_INTERNAL_URL binding or MCP_SERVICE_SECRET missing")
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            base + "/internal/mcp/execute",
            headers={"X-MCP-Service-Secret": secret},
            json={"tool": tool, "auth_token": auth_token,
                  "proposal_id": proposal_id, "action_index": action_index},
        )
        response.raise_for_status()
        result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Internal action was not executed successfully")
    return result


@mcp.tool()
async def assign_task(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute only a previously approved task assignment."""
    return await _execute("assign_task", auth_token, proposal_id, action_index)


@mcp.tool()
async def create_event(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute only a previously approved shared calendar event."""
    return await _execute("create_event", auth_token, proposal_id, action_index)


@mcp.tool()
async def create_reminder(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute only a previously approved reminder."""
    return await _execute("create_reminder", auth_token, proposal_id, action_index)


@mcp.tool()
async def send_message(auth_token: str, proposal_id: str, action_index: int) -> dict:
    """Execute only a previously approved in-app or opt-in external message."""
    return await _execute("send_message", auth_token, proposal_id, action_index)


# This ASGI service receives traffic ONLY via the api -> mcp binding.
# The Vercel internal router already controls Host headers. The API
# callback additionally verifies a shared secret, actor and DB approval.
# Do not add a public rewrite that targets this service.
app = mcp.streamable_http_app(
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
