# Agent1 — dummy agent + MCP client harness

A minimal, self-contained test that drives the **real** recruitment MCP server
(`../server.py`) over a genuine MCP **stdio** session — the same transport an
in-process agent uses — acting as `agent_1` ("Manager provides Job Description").

```bash
python Agent1/agent1_client.py      # run from the server root
```

- **`agent1_client.py`** — a `DummyAgent1` (knows its `agent_id`, calls tools) plus
  a scripted flow judged step-by-step against expected outcomes.

`server.py` loads `.env` on startup. **With** `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
configured, the read/write steps run against the live database; **without** them,
those steps show the clean DB-down / write-stop path (`database_unavailable`). The
ACL denials fire either way — the guardrail is enforced independently of the DB.

## What it exercises (8 steps)

| Step | Tool | With live DB | Without creds |
|---|---|---|---|
| 1 | `health_check` | ok, `database: up` | ok, `database: down` |
| 2 | `list_capabilities` | Agent 1 sees only `requisitions` (read/insert/update) | same |
| 3 | `describe_resource(requisitions)` | contract + status ladder + live columns | contract only |
| 4 | `query_resource(requisitions)` | live rows | `database_unavailable` |
| 5 | `write_resource insert` | DB decides (needs a valid PK `id`) | `database_unavailable` |
| 5b | `query_resource(ilike 'DUMMY')` | read-back | `database_unavailable` |
| 6 | `insert status='Approved'` | **denied** — managed status column | **denied** |
| 7 | `query_resource(candidates)` | **denied** — no grant | **denied** |

A step counts as met if it returns `ok`, is correctly **denied** by the ACL, or
cleanly **stops** on a real DB rejection / outage (`database_error` /
`database_unavailable`) — the harness never treats those as failures, because the
server classifying and reporting them correctly is the point.

Note: `requisitions.id` is a required text PK with no DB default (ids look like
`REQ-2026-513F`), so a real insert must supply its own `id`; the demo omits it on
purpose, so against a live DB step 5 is correctly rejected (`23502` not-null) and
nothing is written.

## Note on the SDK

This harness surfaced that the installed MCP SDK is **2.0.0**, which renamed
`FastMCP` → `MCPServer` (`mcp.server.mcpserver`). `server.py` now imports either
name, so it runs on both 1.x and 2.x. See the SDK note in the root `CLAUDE.md`.
