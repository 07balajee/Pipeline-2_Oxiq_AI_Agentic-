# Recruitment MCP Server

One MCP server giving all 14 recruitment agents read/write access to the
Supabase recruitment tables — with a **constant tool surface** regardless of how
many tables exist.

```
python -m unittest discover -s tests -t .    # 41 tests, no DB required
python validate_registry.py                  # diff registry vs live schema
python server.py                             # stdio
```

---

## The tool-loading problem

The obvious design — one read tool and one write tool per table — gives 32+ tool
definitions for 16 tables. Every agent loads every schema whether it touches the
table or not, and the context cost grows every time the DB does.

Here, **tables are data, not tool definitions**. The server exposes 9 tools and
that number never changes. Discovery is a *runtime call*, not a context cost.

| Tool | Purpose |
|---|---|
| `list_capabilities(agent_id)` | "Which tables may I touch, and how?" — names + ops + one line each. **No columns.** |
| `describe_resource(agent_id, table)` | Columns, PK, JSON arrays, status ladder — **only for tables you actually use** |
| `query_resource(...)` | Generic read with filter operators, ACL-checked |
| `write_resource(...)` | insert / update / upsert / append_json / delete, ACL-checked |
| `transition_status(...)` | The three status ladders |
| `record_offer_response(...)` | The atomic 4-table offer cascade |
| `resolve_call(...)` | Opt-in Haiku repair — proposes, never executes |
| `health_check(...)` | DB reachability, for retry decisions after an outage |
| `validate_registry(...)` | Registry vs live schema drift |

**Typical agent session:** one `list_capabilities` (~6 lines), one or two
`describe_resource` calls, then work. Agent 5 never loads the `offers` schema
because it never asks for it.

`registry.yaml` is the whole product — a direct transcription of the per-agent
mapping doc. Add a table or an agent there; no Python changes, no new tools.

---

## Fallback ladder

Infrastructure failures and interpretation failures get opposite treatment.

### Infrastructure — no LLM anywhere near it

```
L0  primary query
L1  retry transient failures only (timeout / reset / 502-504), backoff
L2  rebuild the client once and retry — covers a stale connection
L3  READS : serve the legacy JSON twin if one exists, tagged  stale: true
    WRITES: stop. "Supabase is down - check your Supabase project's status health."
```

Constraint violations, FK errors and unique collisions are **real answers**, not
outages — surfaced immediately, never retried.

Writes are never spooled and never written to a JSON twin. A stale read is
useful and is labelled as such; a stale write is a lie about the state of the
pipeline. The error states explicitly that nothing was partially applied, so the
agent can retry safely.

Degraded reads carry `source: "json_fallback"`, `stale: true` and a warning, and
are filtered by the same operator semantics as live reads. `append_json` and the
offer cascade **refuse outright** if their preceding read came back stale.

### Interpretation — opt-in, Claude Haiku

When the agent got the *call* wrong (unknown column, wrong table for the intent,
near-miss enum), it may call `resolve_call` with its arguments and the error.
Three constraints hold this safe:

1. **It repairs calls; it never executes them.** It returns a proposal; the agent
   re-submits through the normal path, where it is validated identically. The
   model sits entirely outside the execution path and cannot widen a grant.
2. **It never sees row data** — only the registry slice, the attempted arguments
   and the error string. Candidate PII never reaches the model.
3. **It is off the status path.** Illegal transitions already return the legal
   target set, which beats any guess.

Without `ANTHROPIC_API_KEY` the server runs normally; `resolve_call` reports that
repair is unavailable and returns the deterministic hint.

---

## Security posture

**stdio (agents in-process):** `agent_id` is a guardrail, not auth. Anyone who
can reach the pipe can claim to be `agent_11`. That is fine when you own the
pipe, and the value is real — Agent 5 *physically cannot* write to `offers`,
which catches LLM drift.

**HTTP:** that stops being fine. So:

- `REQUIRE_AGENT_AUTH=true` makes every tool call require an `agent_token`
  matching the claimed `agent_id` (constant-time compare; identical error text
  for unknown agent and bad token, so the endpoint doesn't enumerate agents).
- The server **refuses to start** in HTTP mode on a non-loopback interface with
  auth disabled. That combination is the one that quietly lets anything on the
  network mark a candidate Hired.
- `MCP_HOST` defaults to `127.0.0.1`, not `0.0.0.0`.

Other invariants:

- Status columns are unwritable through `write_resource`. An **insert** may set
  the ladder's initial state (`candidates` → `Applied`, `interviews` →
  `Scheduled`); every later change goes through `transition_status`.
- `update` and `delete` with an empty match are refused — no unbounded writes.
- **No agent holds a `delete` grant** (a test enforces this). Add `ops: [delete]`
  in `registry.yaml` deliberately if one ever needs it.
- The offer cascade is one tool. On failure it rolls back and names any table
  still needing manual repair, preserving the original error code so the agent
  can tell a retryable outage from a permanent rejection.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in SUPABASE_URL + SUPABASE_SERVICE_KEY

python -m unittest discover -s tests -t .    # should be 41 OK
python validate_registry.py                  # against your real database
python server.py
```

Run `sql/atomic_helpers.sql` in the Supabase SQL editor, then set
`USE_RPC_CASCADE=true` and `USE_RPC_APPEND=true`. This makes the offer cascade a
single transaction and JSONB appends a single statement instead of a
read-modify-write, and lets `validate_registry` verify empty tables.

### Validation output

```
ERROR    agent_7: write grant on interview_scores names missing columns ['meet_link']
WARNING  agent_13 holds a DELETE grant on campus_drives - is that intended?
SKIPPED  reselection_log - empty and no table_columns() helper; could not verify
```

Exit codes: `0` clean, `1` errors, `2` database unreachable. Wire it into CI —
it is the difference between catching schema drift at startup and catching it
inside an agent, mid-pipeline.

### MCP client config (stdio)

```json
{
  "mcpServers": {
    "recruitment-db": {
      "command": "python",
      "args": ["/absolute/path/to/recruitment_mcp/server.py"],
      "env": { "SUPABASE_URL": "...", "SUPABASE_SERVICE_KEY": "..." }
    }
  }
}
```

---

## Agent usage pattern

```python
list_capabilities(agent_id="agent_5")
# -> candidates (read, transition; may_set: Screening/Interview/Declined)
#    candidate_details (read)
#    screening_results (insert)

describe_resource(agent_id="agent_5", table="screening_results")

query_resource(agent_id="agent_5", table="candidates",
               filters={"status": "Applied", "job_id": 12},
               limit=25, correlation_id=journey_id)

write_resource(agent_id="agent_5", table="screening_results", op="insert",
               data={"candidate_id": 88, "job_id": 12, "screening_score": 74,
                     "shortlisted": True, "reason": "5y Django, JD match 0.81",
                     "screened_at": "2026-08-02T10:00:00Z"})

transition_status(agent_id="agent_5", entity="candidates",
                  entity_id=88, to_status="Interview", reason="score 74")
```

Filter operators — `eq neq gt gte lt lte like ilike in is_null`:

```python
# Agent 11's next-best-fit after a decline
query_resource(agent_id="agent_11", table="interview_scores",
               filters={"job_id": 12, "score": {"gte": 60}},
               order_by="rank", limit=1)

query_resource(agent_id="agent_5", table="candidates",
               filters={"status": {"in": ["Applied", "Screening"]}})
```

Appending to a JSONB array (Agents 2, 4, 7, 8, 14):

```python
write_resource(agent_id="agent_14", table="campus_drives", op="append_json",
               json_column="candidates", match={"id": "DRIVE-2026-01"},
               data={"value": {"name": "A. Rao", "email": "...", "gpa": 8.4}})
```

---

## Relationship to the onboarding system

Same house style as SA7 — MCP is the **data plane only**. Agent-to-agent
communication stays on your REST envelope (`correlation_id`, `trace_id`,
`trigger_source`), exactly as the onboarding Master↔spoke contract does. Every
tool accepts a `correlation_id` and echoes it back, so a recruitment →
onboarding handoff traces end to end on one id.

Agent 11 flipping a candidate to `Hired` is the handoff point into onboarding.

---

## Files

```
server.py               9 MCP tools
registry.py             registry loader, ACL, transition validation
registry.yaml           THE contract — 16 tables, 14 agents, 3 status ladders
db.py                   Supabase access + the fallback ladder
filters.py              filter operators (live path and JSON-twin path)
cascade.py              the atomic offer-response cascade
resolver.py             opt-in Haiku call repair
auth.py                 per-agent tokens + unsafe-startup guard
validate_registry.py    registry vs live schema drift (CLI + tool)
errors.py               typed errors with agent-readable hints
sql/atomic_helpers.sql  cascade, JSONB append, column introspection
tests/                  41 tests, no network or database needed
```
