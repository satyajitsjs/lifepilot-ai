# Deploy LifePilot Circles with Vercel

The Next.js frontend is ready for **Vercel**. The existing Python API requires
a persistent backend host for this hackathon MVP. These are two deployments.

## Architecture

```text
Browser -> Vercel Next.js (apps/web)
         -> same-origin /api/* rewrite
         -> public HTTPS FastAPI host (persistent Docker service)
         -> SQLite mounted volume, reminder worker and MCP subprocess
```

Vercel supports Python/FastAPI functions, but the **current implementation is
not serverless-safe**: it stores data in local SQLite, runs a 30-second
reminder polling task, uses in-memory LangGraph checkpoints, and launches MCP
processes. Deploying that backend unchanged as a Vercel Function can lose data
or stop background work. PostgreSQL, durable checkpoints, scheduled jobs and
an MCP execution review would be needed for fully serverless deployment.

## 1. Host FastAPI separately

A Docker provider offering a persistent mounted volume (Railway, Render with a
persistent disk, Fly.io or a VPS) can run the current API.

- GitHub source: `satyajitsjs/lifepilot-ai`
- Build context: repository root
- Dockerfile path: `infra/Dockerfile.api`
- Command: already configured in the Dockerfile; listens on `PORT` if provided
- Mount persistent storage at `/data`

For **demo-only fake data**, set these backend environment variables:

| Variable | Value |
|---|---|
| `DATABASE_PATH` | `/data/lifepilot.db` |
| `MCP_MODE` | `stdio` |
| `API_SECRET` | Long random secret, not the checked-in sample |
| `DEMO_MODE` | `true` for demo accounts only |
| `NVIDIA_API_KEY` | Optional; omit to use clearly-labelled rule-based demo |
| `NVIDIA_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b` (optional) |

Enable a public HTTPS domain for the API and verify:

```text
https://YOUR-API-DOMAIN/healthz
{"ok":true,"service":"lifepilot-api"}
```

**Security:** The demo login permits persona switching with no password.
Never use it for real personal data or an unprotected production launch.
Protect demos at the hosting provider and replace demo authentication with a
real identity provider for actual users.

## 2. Import Next.js into Vercel

1. Go to https://vercel.com/new and import GitHub
   `satyajitsjs/lifepilot-ai`.
2. Framework Preset: **Next.js**.
3. Root Directory: **`apps/web`**, NOT the GitHub repository root.
4. Install Command: `npm install`; Build Command: `npm run build` (defaults).
5. Add a project environment variable:
   - **Key:** `API_BACKEND_URL`
   - **Value:** `https://YOUR-API-DOMAIN`
   - **Environments:** Production (and Preview if needed)
6. Click Deploy. Your frontend gets a `*.vercel.app` URL.

**Important:** Do not add `NEXT_PUBLIC_API_URL` unless deliberately bypassing
the proxy and configuring CORS. Next.js compiles its rewrites during build.
**Redeploy after changing `API_BACKEND_URL`**.

GitHub Actions is **not required**. Vercel's native Git integration triggers
builds and deployments according to the chosen plan.

## 3. Validate

- `https://YOUR-VERCEL-SITE.vercel.app/healthz` returns the upstream health JSON.
- `https://YOUR-VERCEL-SITE.vercel.app/api/bootstrap` returns **401** without
  a valid bearer token; that confirms the API proxy is working.
- The dashboard loads demo users, circles and tasks through the same-origin API.
- Try creating a plan, then Reject (no changes), then Approve and inspect the
  executed MCP outcomes. Run a reminder if the backend worker is running.
- Browser Network requests must go to `/api/...` on the **Vercel origin**,
  never to `http://127.0.0.1:8000` from a deployed site.

If the UI renders but data does not load, check whether the backend is reachable
from the public internet over HTTPS, verify the Vercel environment variable,
then redeploy.

## 4. Local and Docker development

PowerShell from repository root, in two terminals:

```powershell
python .\services\api\run.py
```

```powershell
cd apps/web
Copy-Item .env.example .env.local
npm install
npm run dev
```

For an existing local `apps/web/.env.local`, remove any old
`NEXT_PUBLIC_API_URL` setting. The default proxy upstream is
`http://127.0.0.1:8000`.

Docker Compose runs the frontend and backend together:

```powershell
docker compose up --build -d
docker compose ps
```

The web Docker build sets `API_BACKEND_URL=http://api:8000`, the Compose
network hostname for FastAPI; the browser still uses `/api/*`.

## 5. If you want *all* services on Vercel

That requires a backend refactor, not only a `vercel.json` file: migrate from
SQLite to managed PostgreSQL, persist LangGraph checkpoints, replace polling
with scheduled jobs, review MCP tool process lifecycle and timeout limits,
and implement production authentication. This guide **does not claim** to
provide a full-stack Vercel deployment.

References:
- https://vercel.com/docs/monorepos
- https://vercel.com/docs/frameworks/backend/fastapi
