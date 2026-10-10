# Learn the whole LifePilot Circles stack, one file at a time

You wanted to learn as you build. The project is complete enough to run, and the sequence below helps you understand it rather than blindly copy code.

## Lesson 1 — Read the request from UI to backend

Open `apps/web/components/dashboard.tsx`. Find `createPlan()`: it sends an authenticated HTTP `POST` to `/api/assistant/plan`. Open `services/api/app/main.py` and find `propose()`.

**Think:** Why must the server check circle membership even if the frontend already knows the circle?

## Lesson 2 — LLM output isn't an action

Read `agent.py` and compare `_fallback_plan()` vs `make_plan()`. When NVIDIA key is configured, LangChain calls Nemotron and requests structured JSON. `validate_actions()` rejects unknown tools and invalid circle recipients.

**Think:** Why is `tool_name` from LLM not enough authorization to execute?

## Lesson 3 — LangGraph is workflow state

Read `approval_graph.py`. `interrupt()` yields the proposal summary and pauses until `Command(resume=True/False)`. Memory checkpoints enable development; a DB proposal record independently preserves the action state.

**Think:** How would a pending workflow survive a process crash without a durable checkpointer?

## Lesson 4 — MCP is a tool protocol

Read `services/mcp-server/server.py`: `@mcp.tool()` exposes type-annotated Python functions. The API's `mcp_client.py` launches this server through stdio and calls a selected tool after approval.

**Think:** What's the difference between `list_tools()` and `call_tool()`? Can a function be an MCP tool without the decorator?

## Lesson 5 — Real side effects and safety

Read `actions.py`. Task creation validates membership, persists to SQLite, creates a notification and logs an activity event. Idempotency keys prevent double creation if a response times out.

**Think:** What happens if a task creation completes but the network response is lost?

## Lesson 6 — UI, data, and state

The dashboard gets fresh data from `/api/bootstrap` after every approved action. There are no hardcoded success responses in the Next.js app. Open the API explorer at `http://127.0.0.1:8000/docs`.

**Think:** Why is a persisted task still visible after you refresh the browser?

## Suggested follow-on exercises

1. Add a `tasks.list` **read-only** MCP tool, write a unit test, then call it through Inspector.
2. Add a circle-member invitation flow, with validation and auth.
3. Build a PostgreSQL adapter and migrate the SQLite schema.
4. Add per-user Google Calendar OAuth with refresh token storage and explicit scopes.
5. Add the persistent LangGraph Postgres checkpointer.
6. Write a test proving an unapproved tool call never executes.
