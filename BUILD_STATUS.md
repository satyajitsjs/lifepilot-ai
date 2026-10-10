# Verification report — Vercel Services review (11 October 2026)

## Verified in local implementation workspace

- Python backend syntax compilation: **PASS** (`python -m compileall -q services`)
- Pytest existing workflows and added service authorization tests:
  **12 passed, 2 skipped** (`python -m pytest -q tests`)
- New tests verify three private-service bindings and public exposure,
  authorization before MCP action execution, rejection of forged actors/tools,
  idempotent retries, protected scheduler endpoint, and PostgreSQL-only Vercel startup.
- TypeScript/TSX syntax transpilation: **PASS** (8 non-declaration files)
- `vercel.json` valid JSON; top-level public rewrite targets only `web`.

## Not yet validated — do not claim full deployment success

- No real Vercel build/deployment or `vercel dev -L` multi-service round trip.
- No live managed PostgreSQL configured; SQL translation tests passed but
  full initialization, concurrent writes and provider connection pooling remain untested.
- The MCP SDK 2.x Streamable HTTP handshake, Vercel ASGI lifespan and
  `api → mcp → api` service bindings have **not** been exercised against live services.
- Optional real stdio MCP test and LangGraph SDK integration test were skipped
  because the packages are unavailable in the local testing container.
- No real NVIDIA API key, external calendar/OAuth or SMTP/Slack providers tested.
- No recurring Vercel Cron schedule, paid plan or Vercel project was created.

## Known limitations

- Demo login is insecure for public real-user use. It defaults to disabled
  on Vercel; use explicit fake-data protected previews only.
- PostgreSQL persisted proposals are authoritative, but the LangGraph
  in-memory checkpoint history is not yet fully durable.
- Missing production identity, robust schema migrations, database pooling review,
  request throttling and full load/performance validation.
- Reminder endpoint is protected but must be scheduled separately after confirming
  desired frequency/cost.

This is a **review-branch deployment implementation**, not a completed production deployment.
