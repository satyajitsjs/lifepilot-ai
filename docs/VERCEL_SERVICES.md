# Vercel Services — architectural review

This **review branch only** introduces the repository-root `vercel.json`,
which defines two independently built services in a single Vercel project.

| Service | Root | Framework | Traffic |
|---|---|---|---|
| `web` | `apps/web` | Next.js | Public: `/*` |
| `api` | `services/api` | FastAPI; `main:app` | No direct public rewrite |

## Routing and binding

The **calling** service `web` declares exactly one internal binding:

```json
{"type":"service","service":"api","format":"url","env":"API_SERVICE_URL"}
```

Vercel injects `API_SERVICE_URL` at **function runtime**. Do not set it
manually or expose it as a `NEXT_PUBLIC_*` build variable.

The public catch-all `/(.*)` rewrite sends all traffic to `web`.
Next.js handles `/api/*` and `/healthz` with server-side route handlers,
which forward the calls through the private `API_SERVICE_URL` binding.
FastAPI keeps the original `/api/*` paths — no prefix removal is needed.
The browser accesses `/api/*` on the same origin, with no hardcoded domain.
Its bearer Authorization header travels to FastAPI through the gateway.
Backend `/docs` is **not** directly exposed.

In Docker Compose and local Next.js, the proxy instead reads
`API_BACKEND_URL` (Docker: `http://api:8000`; local: `http://127.0.0.1:8000`).
These are NOT Vercel service bindings. Use `vercel dev -L` for integrated
local Services development with bindings automatically injected.

## Critical: this is NOT a production-ready full-stack launch

1. **Ephemeral storage.** API falls back to `/tmp/lifepilot.db` on Vercel.
   It is writable for smoke tests but not durable or shared between function
   instances. Real persistent circles, task assignments and approvals need a
   managed PostgreSQL database and a migration.
2. **Reminder worker.** The continuous in-process 30-second polling loop is
   disabled on Vercel, because functions are not always running. Use a
   scheduled job/cron after migrating to persistent storage.
3. **MCP transport.** The MCP server currently lives in
   `services/mcp-server/server.py`, outside the API service root.
   With `MCP_MODE=stdio` the API reports a real failure for an approved
   tool call rather than pretending to use MCP. Setting `MCP_MODE=local`
   is an explicit, **non-MCP, non-durable** demo option only. For actual
   hackathon MCP integration, decide whether to add a third internal
   `mcp` service with a binding `api` -> `mcp`, or implement another
   verified MCP transport.
4. **Authentication.** Existing demo identities can switch users freely.
   Do not run with real personal data or public write access without a
   real identity provider and a security review.
5. **Billing.** Vercel Services requests and functions are metered under
   your plan. No GitHub Actions workflows were created or modified.

## Vercel project setup after confirmation

- Connect `satyajitsjs/lifepilot-ai` to a Vercel project.
- Set the framework preset to **Services**, and use the **repository root**
  (not `apps/web`) so Vercel reads root `vercel.json`.
- Do NOT create `API_SERVICE_URL` in Environment Variables; Vercel
  supplies that internal URL to `web` at request runtime.
- Configure a long random `API_SECRET`. Use `DEMO_MODE` only for
  a protected demo, and never for real users.
- Run `vercel dev -L` locally, check `/healthz`, demo login and
  `/api/bootstrap`, and verify browser requests stay on the same origin.
- A fully operational shared deployment requires resolving the blockers
  above before enabling public access.

## Confirmation requested

1. Keep the service names `web` and `api`?
2. Keep `web` public at `/*`, with `/api/*` proxied through Next.js to
   internal `api`, or expose `api` directly on public `/api/*`?
3. Keep only `web` -> `api` via `API_SERVICE_URL`, or also
   add a third internal `mcp` service called by `api`?
4. For the actual deployment, do you prefer an ephemeral demo preview or
   a persistent PostgreSQL-backed setup with functional MCP approvals?

Relevant Vercel documentation: https://vercel.com/kb/guide/vercel-services
