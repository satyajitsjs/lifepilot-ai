# LifePilot Circles — architecture

## Local development / Docker

- Next.js 16 in `apps/web`, browser requests same-origin `/api/*`.
- Next.js server gateway forwards to local FastAPI port 8000 or Docker
  `http://api:8000` (via `API_BACKEND_URL`).
- FastAPI backend creates tasks, circles, events, in-app reminders and messages.
- SQLite remains the local demo database and existing tests use a temporary file.
- Python SDK v2 local MCP over stdio; demo mode is deliberately insecure and
  intended solely for non-personal fake data.

## Vercel Services — review branch only

```text
 Browser / user
       |
       v
Vercel web service (Next.js)        PUBLIC /*
       |
       | API_SERVICE_URL runtime binding
       v
Vercel api service (FastAPI)        INTERNAL
       |  LangChain/NVIDIA optional plan generator
       |  PostgreSQL durable proposals + LangGraph interrupt/resume
       |
       | MCP_SERVICE_URL runtime binding (MCP HTTP)
       v
Vercel mcp service (MCPServer v2)  INTERNAL
       |
       | API_INTERNAL_URL runtime binding
       | X-MCP-Service-Secret and signed actor token
       v
Vercel api (/internal/mcp/execute)
       |
       | matches type, actor, circle and index against approved DB proposal
       v
Managed PostgreSQL (DATABASE_URL)
```

The additional reverse `mcp → api` binding is necessary because the API
owns the domain write logic and the database connection. MCP tools accept
only a signed actor token and a persisted proposal ID/action index; they
cannot invent or modify the action's parameters.

## Approval safety / durability

- `/api/assistant/plan` persists a pending proposal and invokes LangGraph
  `interrupt()`. No tool executes at this stage.
- Approve transitions its PostgreSQL record to `executing` with an atomic
  conditional update. Reject marks it `rejected`, no tool execution.
- Tools fetch the original approved action from PostgreSQL through the
  private internal callback, verify actor and circle permissions, and use
  a per-action idempotency key for retry safety.
- LangGraph `InMemorySaver` is still process-local. Persisted proposal state
  permits reconstruction on another instance, but full cross-worker
  checkpoint history is a future hardening task.

## Database / reminders

- Hosted API requires `DATABASE_URL` (psycopg PostgreSQL). Vercel runtime
  refuses ephemeral SQLite. PostgreSQL init uses a transaction advisory lock
  to serialize demo seeding. Replace startup DDL with migrations when shipping
  production.
- Serverless functions have no reliable continuous polling loop. An
  authenticated `GET /api/cron/reminders` endpoint checks due tasks;
  no recurring cron is enabled by default.

## Public access boundaries

- The root Vercel rewrites route every public request to `web`, not `api`
  or `mcp`. Next.js only proxies intended public `/api/*` calls.
- `/internal/mcp/execute` is not publicly proxied and checks an independent
  `MCP_SERVICE_SECRET`, signed actor identity, and an executing proposal.
- `MCP_SERVICE_URL`, `API_INTERNAL_URL` and `API_SERVICE_URL` are
  runtime service bindings, not manually configured URLs.
- The demo-user login is not real authentication; on Vercel it defaults to
  disabled. Add OIDC/OAuth before public use with real people and data.

See [VERCEL_SERVICES.md](VERCEL_SERVICES.md) for deployment requirements
and [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for the legacy alternative
with an externally hosted API.
