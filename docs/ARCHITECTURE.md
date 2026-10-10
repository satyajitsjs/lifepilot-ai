# Architecture and safety boundaries

```text
Next.js 16 frontend (apps/web)
   |
   | Bearer demo token over HTTP
   v
FastAPI (services/api/app/main.py)
   |-- demo identity and circle membership
   |-- agent.py: LangChain + NVIDIA Nemotron, or labelled offline deterministic planner
   |-- approval_graph.py: LangGraph interrupt/checkpoint/resume
   |-- proposals in SQLite to survive API restarts
   |-- approval endpoint verifies actor + circle and marks proposal executing
   v
MCP Client (services/api/app/mcp_client.py)
   |  stdio client spawns Python MCP server for each approved action
   v
MCPServer 2.x (services/mcp-server/server.py)
   |-- assign_task
   |-- create_event
   |-- create_reminder
   |-- send_message
   v
Tool domain service (services/api/app/actions.py)
   |-- verifies signed actor token, circle membership and recipient membership
   |-- unique idempotency keys
   |-- SQLite persistence
   |-- in-app notifications
   |-- optional SMTP / Slack webhook
   v
FastAPI returns verified per-tool outcomes; UI refreshes live data.
```

## Why no Postgres yet?

A local SQLite database makes the hackathon demo trivially reproducible for both team members. Production deployment should migrate to PostgreSQL and use Alembic, especially for concurrent writes. The schema is in `db.py` so migration is straightforward, but it is **not implemented** here.

## Approval and durability

LangGraph `interrupt()` pauses a thread. `InMemorySaver` preserves state inside the running API process. `proposals` DB records independently persist status and action definitions. If the API restarts before approval, `approval_graph.resume()` recreates the paused graph and then resumes it. Production should use a persistent LangGraph Postgres checkpointer to preserve the *whole* graph history and guarantee resume across workers.

The `proposals` row is changed from `pending` to `executing` using an atomic conditional update before execution, preventing duplicate approval requests. Every MCP action receives an idempotency key `<proposal-id>:<index>`. Tool tables store unique keys to prevent duplicate creations after a timeout. Partial errors are recorded in proposal outcomes.

## Security notes

- API caller identity comes from an HMAC-signed expiring session token; user IDs from language model output are **never** trusted as actor identity.
- Circle membership is checked on proposals, tool execution, and reads.
- MCP runs through a locally launched stdio process for approved actions. The optional HTTP MCP server is bound to loopback in Compose and requires production OAuth or an auth proxy before internet exposure.
- The demo login endpoint intentionally allows persona switching. **It is not real user authentication** and must be removed/replaced with OIDC/OAuth before production.
- Never send private content to an LLM without informing users; API key, SMTP password and Slack webhook stay in server environment variables.
- LangChain generates **proposals**, not actions. The backend validates actions and requires explicit approval before MCP calls.

## Integration reality

| Feature | What is actually implemented |
|---|---|
| Multi-user team & family circles | Seeded demo circles and membership-based task/event access |
| Task assignment | Real persistent task records and in-app notifications |
| Reminders | Persistent reminders + 30-second background polling, in-app delivery |
| Calendar | Real in-app event records + downloadable `.ics` file, not Google Calendar OAuth |
| Messaging | In-app delivery; optionally sends Slack webhook or SMTP email with credentials |
| AI | LangChain `ChatOpenAI` against NVIDIA when key is set; clearly labelled deterministic demo planner without a key |
| HITL | LangGraph `interrupt`, resume on approve/reject; DB statuses authoritative |
| MCP | Official Python SDK v2 `MCPServer`, stdio execution, separate localhost-only Streamable HTTP server |

## Known gaps before public production

Real OAuth/OIDC, protected public MCP OAuth endpoint, multi-worker persistent checkpointing, PostgreSQL migrations, API rate limiting, personal calendar OAuth (e.g. Google), scheduled external email reminders, robust observability and a production deployment review. This is a hackathon-grade working MVP, **not** a production SaaS.
