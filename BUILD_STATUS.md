# Verification report — 10 October 2026

## Verified in this build environment

- Python backend syntax compilation: **PASS**
- Pytest API/workflow tests: **7 passed**
- Authenticated FastAPI HTTP smoke test: **PASS** (health, demo login, bootstrap)
- TypeScript/TSX **syntax transpilation**: **PASS** (4 files)
- UI HTML/CSS desktop screenshot: **captured and inspected** (1440px)
- UI HTML/CSS mobile screenshot: **captured and inspected** (390px, no horizontal overflow)

## Requires validation on your machine

- `npm install && npm run build` / browser interactions in the real Next.js app: **not executed here** because package registry DNS is unavailable.
- MCP SDK 2.x real stdio / Streamable HTTP round-trip: **not executed here** because MCP Python package is unavailable in this container (you already have it installed locally).
- LangGraph actual `interrupt()` / `Command(resume=...)` execution: **not executed here** because LangGraph Python package is unavailable in this container.
- NVIDIA Nemotron real API planning: **not executed** (no API key; deterministic demo plan exercised).
- Gmail/Google Calendar OAuth: **not implemented**. In-app events, ICS calendar export, and SMTP/Slack opt-in available.
- Public deployment and real OAuth: **not configured**.

Optional pytest tests named `test_mcp_integration.py` and `test_langgraph_integration.py` will run automatically after the respective packages are installed in your local Python environment.
