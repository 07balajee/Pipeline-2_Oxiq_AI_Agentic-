# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An MCP server (FastMCP, stdio or HTTP) that gives ~14 recruitment agents ACL-checked
read/write access to Supabase tables through a **constant surface of 9 tools**,
regardless of how many tables exist. Tables are *data* (`registry.yaml`), not tool
definitions — so an agent's context holds 9 tool schemas whether the DB has 16 tables
or 160. Discovery (`list_capabilities`, `describe_resource`) is a runtime call, not a
context cost.

## Commands

```bash
pip install -r requirements.txt

# Run the server
python server.py                          # stdio (default; agents in-process)
MCP_TRANSPORT=http python server.py       # HTTP (binds 127.0.0.1:8010 by default)

python validate_registry.py               # diff registry.yaml vs live schema (exit 0 clean / 1 errors / 2 DB unreachable)

python Agent1/agent1_client.py            # dummy Agent 1 drives the server over a real MCP stdio session (no DB needed)
```

### MCP SDK version

`requirements.txt` pins `mcp>=1.2.0`, but the **2.0.0** release renamed `FastMCP`
→ `MCPServer` (`mcp.server.mcpserver`) and dropped `mcp.server.fastmcp`, plus moved
HTTP host/port from `mcp.settings` to `run()` kwargs. `server.py` now imports either
name and sets host/port both ways, so it runs on 1.x and 2.x. If you touch the server
entrypoint or transport, keep both paths working (or pin `mcp<2`).

### Tests — layout is currently broken

`test_all.py` does `from tests.fake_supabase import ...` and `sys.path.insert(0, parent_of_parent)`,
i.e. it expects to live at `tests/test_all.py` with `tests/fake_supabase.py` (and a
`tests/__init__.py`) beside it, plus `sql/atomic_helpers.sql` and `data/*.json`. **But
every file is currently flat in the repo root**, so the documented command
`python -m unittest discover -s tests -t .` fails with `ModuleNotFoundError: No module
named 'tests'`. Before running the 41-test suite you must either recreate the
`tests/`, `sql/`, and `data/` subdirectories the code references, or adjust the imports.
Do not assume tests pass as checked out.

Tests need no network or DB — `fake_supabase.py` provides in-memory `FakeClient` /
`FlakyClient` / `FailingStepClient` stubs that exercise the real filter, retry,
fallback, and cascade code paths.

## Architecture

Request flow for every tool: `server.py` `_guard()` → `auth.authenticate()` →
`registry.authorize_*()` → `db.py` (Supabase + fallback ladder) → structured dict.

- **`server.py`** — the 9 `@mcp.tool()` functions. All tool bodies run through
  `_guard()`, which authenticates, stamps a `correlation_id` (the agent's own if
  supplied, so recruitment→onboarding handoffs trace on one id), and converts
  `McpError` subclasses into structured dicts (`{ok, code, message, hint, retryable}`)
  the agent can branch on. Errors other than unauthenticated/DB-down/illegal-transition
  get a `recovery` hint pointing at `resolve_call`.
- **`registry.py` + `registry.yaml`** — `registry.yaml` **is the product**: a direct
  transcription of the per-agent DB-mapping doc (tables, agents, 3 status ladders). All
  authorization logic lives in `Registry.authorize_read/write/transition/cascade`.
  Adding a table or agent is a YAML edit — **no Python changes, no new tools**.
  `load_registry()` is `@lru_cache`d; call `reload_registry()` to pick up edits.
- **`db.py`** — Supabase access + the deliberate fallback ladder (see below). Config
  (`SUPABASE_URL`, retry counts, etc.) is read via `os.getenv` **at call time, not
  import time**, on purpose — a value frozen at import ignores config applied later
  (this is why tests can set env then import). The `supabase` client is imported lazily
  inside `get_client()` so tests can stub it.
- **`cascade.py`** — `record_offer_response`, the one multi-table write that must not
  half-apply (`offer_links → offer_letters → offers → candidates`). Prefers a single-txn
  Postgres RPC (`USE_RPC_CASCADE=true`); otherwise does sequential writes with
  reverse-order compensation, and on unrecoverable failure names the exact tables left
  inconsistent for manual repair.
- **`resolver.py`** — opt-in Haiku call-repair. **Never executes**, never sees row data
  (only the registry slice + attempted args + error string), off by default and off the
  status path. Returns a *proposal* the agent must re-submit through the normal
  validated path. Runs fine without `ANTHROPIC_API_KEY` (reports repair unavailable).
- **`auth.py`** — per-agent token check (constant-time compare, identical error for
  unknown-agent and bad-token so it can't enumerate agents) + `assert_safe_startup`.
- **`filters.py`** — filter operators (`eq neq gt gte lt lte like ilike in is_null`),
  applied identically to the live query path and the JSON-twin path.
- **`errors.py`** — typed `McpError` subclasses; the `code` string is the agent's branch
  key. Key codes: `capability_denied`, `schema_error`, `illegal_transition`,
  `database_unavailable` (retryable), `database_error` (a real rejection, *not* retryable).

## Invariants — do not "improve" these without understanding them

- **Fallback ladder** (`db.py`): retry only *transient* transport failures (see
  `_TRANSIENT_MARKERS`), rebuild the client once, then — **reads** fall back to a legacy
  JSON twin tagged `stale: true` / `source: "json_fallback"`; **writes** stop hard with
  `database_unavailable` and are never spooled ("a stale read is useful; a stale write is
  a lie about the pipeline"). Constraint/FK/unique violations are *real answers*,
  surfaced immediately, never retried. `append_json` and the offer cascade **refuse** if
  their preceding read came back stale. Always check `source`/`stale` on read results.
- **Managed status columns** are unwritable via `write_resource` — the *only* exception
  is an `insert` setting a ladder's initial state. Every later change goes through
  `transition_status`, validated against both the ladder and the agent's `may_set` set.
- `update`/`delete` with an empty `match` are refused (no unbounded writes). **No agent
  holds a `delete` grant** by default; a test enforces this.
- **HTTP + non-loopback host + auth disabled = refuse to start** (`assert_safe_startup`).
  `MCP_HOST` defaults to `127.0.0.1` on purpose. Over stdio, `agent_id` is a guardrail
  (catches LLM drift), not auth.

## Data plane only

This server is the **data plane**. Agent-to-agent messaging stays on the external REST
envelope (`correlation_id`, `trace_id`, `trigger_source`). Agent 11 flipping a candidate
to `Hired` (via the offer cascade) is the handoff point into the onboarding system.
