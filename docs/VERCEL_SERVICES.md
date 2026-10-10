# LifePilot Circles — Vercel Services review (three services)

The configuration lives on `review/vercel-services`. **No deployment or merge was initiated.**

## Confirmed service topology

| Service | Root | Public routing | Runtime binding |
|---|---|---|---|
| `web` | `apps/web` | `/*` including `/api/*` through Next.js gateway | `API_SERVICE_URL` → `api` |
| `api` | `services/api` | none directly | `MCP_SERVICE_URL` → `mcp` |
| `mcp` | `services/mcp-server` | **internal only** | `API_INTERNAL_URL` → `api` |

The additional reverse `mcp → api` binding is required because the MCP
service deliberately has no database credentials or permission to invent task
parameters. It asks the API to execute only the **previously approved** action.

## Approval / execution path

Browser → web (`/api/*`) → api (LangGraph approval, PostgreSQL record
transitions to `executing`) → mcp (Streamable HTTP MCP 2.x) → api
(`/internal/mcp/execute`) → PostgreSQL.

Only the web service is publicly routed. The private API callback is not
accessible through the Next.js `/api/*` gateway. The gateway blocks path
traversal attempts. Service bindings grant network reachability, not identity.

The MCP tool receives a signed session token, `proposal_id` and
`action_index`. The API verifies:
1. `MCP_SERVICE_SECRET` using a constant-time comparison;
2. the signed user token and actor ID;
3. an existing proposal in `executing` or `partial` state;
4. tool type matching the exact persisted proposal action, plus circle scope;
5. circle membership and per-action idempotency.

This prevents an unapproved tool call from creating a task.

## Durable database

The API now uses managed **PostgreSQL** when `DATABASE_URL` is configured,
through psycopg 3 with dictionary rows. Existing SQLite-style placeholders
are adapted to psycopg parameters. Schema creation and demo seed data are
serialized by a transaction-scoped PostgreSQL advisory lock.

Without `DATABASE_URL`, the application **refuses** to use ephemeral SQLite
on Vercel; local development and unit tests can still use SQLite.

Choose a pooled/serverless-compatible PostgreSQL connection string. The next
production milestone should replace runtime schema initialization with
versioned migrations (e.g. Alembic) and add a connection pooling review.

LangGraph still uses a per-instance `InMemorySaver`; persisted proposals in
PostgreSQL are the durable source of truth and allow paused graph state to be
re-created on another instance. A true durable LangGraph checkpointer is a
further improvement before production.

## Reminders on serverless

Vercel Functions cannot reliably host an endless 30-second background loop,
so this loop is disabled on Vercel. A protected
`GET /api/cron/reminders` endpoint accepts
`Authorization: Bearer <CRON_SECRET>` and processes overdue reminders with
idempotency keys. **No recurring Vercel Cron schedule is enabled here** until
you approve its frequency and plan cost.

## Environment variables required before preview deployment

| Key | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | api | managed PostgreSQL DSN, **required** |
| `API_SECRET` | api | strong random HMAC key, at least 32 chars |
| `MCP_SERVICE_SECRET` | api + mcp | separate random shared secret, at least 32 chars |
| `DEMO_MODE` | api | defaults to `false` on Vercel |
| `NVIDIA_API_KEY` | api | optional AI provider |
| `CRON_SECRET` | api | optional protected reminder scheduler |

**Never manually set** the injected bindings `API_SERVICE_URL`,
`MCP_SERVICE_URL`, or `API_INTERNAL_URL`. On Vercel set `MCP_MODE=http`
(or leave it unset). `MCP_MODE=local` is intentionally forbidden on Vercel.

## Validation before deployment

- `python -m pytest -q tests` — API security and workflow tests.
- `python -m compileall -q services` — Python compilation.
- `vercel dev -L` at repo root — binding injection and ASGI initialization.
- Preview-only with **Deployment Protection** and fake demo identities:
  verify `/healthz`, login/bootstrap, rejected action creates no records,
  approved action persists through MCP, retried action is idempotent, and
  persistence survives separate invocations.
- Enable a scheduler only after confirming the desired cadence and cost.

**Not yet production safe:** Real OAuth/OIDC authentication, rate limiting,
provider PostgreSQL integration, actual Vercel functions round-trip and the
MCP handshake have not yet been demonstrated on deployed services. Public
access should remain protected until these are validated.

References: https://vercel.com/kb/guide/vercel-services
and https://py.sdk.modelcontextprotocol.io/run/asgi/
