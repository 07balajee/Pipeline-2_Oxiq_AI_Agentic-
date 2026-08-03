"""Recruitment MCP Server.

THE TOOL-LOADING PROBLEM AND HOW THIS SOLVES IT
-----------------------------------------------
Exposing read+write tools per table would mean ~16 tables x 2 ops = 32+ tool
definitions, every schema sitting in every agent's context whether that agent
touches the table or not. Context cost grows with the database.

Here, tables are DATA, not tool definitions. The server exposes 9 tools, and
that number never changes - add 100 tables to registry.yaml and each agent still
loads 9 schemas. Discovery is a runtime call, not a context cost:

    1. list_capabilities(agent_id)      -> "which tables may I touch, and how?"
                                           ~6 lines. No columns.
    2. describe_resource(agent_id, tbl) -> columns, PK, enums. ONLY on demand.
    3. query_resource(...)              -> generic read,  ACL-checked
    4. write_resource(...)              -> generic write, ACL-checked
    5. transition_status(...)           -> the three status ladders
    6. record_offer_response(...)       -> the atomic 4-table offer cascade
    7. resolve_call(...)                -> opt-in Haiku repair, executes nothing
    8. health_check(...)                -> DB reachability, for retry decisions
    9. validate_registry(...)           -> registry vs live schema drift

Run:  python server.py                          (stdio - agents in-process)
      MCP_TRANSPORT=http python server.py       (HTTP - separate agent services)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

try:  # load SUPABASE_URL / SUPABASE_SERVICE_KEY etc. from a local .env if present
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:  # python-dotenv optional; real env vars still work without it
    pass

try:  # mcp SDK 1.x
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # mcp SDK 2.x renamed FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

import auth
import cascade
import db
import filters as filt
import resolver
import validate_registry as validator
from errors import McpError, SchemaError
from registry import load_registry, reload_registry

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("recruitment_mcp")

mcp = FastMCP("recruitment-db")


def _guard(fn, *, agent_id: str, tool: str, agent_token: str | None = None,
           correlation_id: str | None = None, authenticate: bool = True):
    """Every tool body runs through here.

    Authenticates the caller, stamps the correlation_id (the agent's own if it
    supplied one, so a recruitment -> onboarding handoff traces end to end), and
    turns exceptions into structured dicts an agent can branch on rather than a
    wall of text.
    """
    cid = correlation_id or str(uuid.uuid4())
    try:
        if authenticate:
            auth.authenticate(agent_id, agent_token)
        result = fn()
        if isinstance(result, dict):
            result.setdefault("correlation_id", cid)
        log.info("tool.ok tool=%s agent=%s cid=%s", tool, agent_id, cid)
        return result
    except McpError as exc:
        payload = exc.to_dict()
        payload["correlation_id"] = cid
        payload["tool"] = tool
        if exc.code not in ("unauthenticated", "database_unavailable", "illegal_transition"):
            payload.setdefault(
                "recovery",
                "Call resolve_call with this error and your arguments for a repair proposal.",
            )
        log.warning("tool.error tool=%s agent=%s code=%s cid=%s msg=%s",
                    tool, agent_id, exc.code, cid, exc.message)
        return payload
    except Exception as exc:  # noqa: BLE001
        log.exception("tool.unhandled tool=%s agent=%s cid=%s", tool, agent_id, cid)
        return {"ok": False, "code": "internal_error", "message": str(exc),
                "correlation_id": cid, "tool": tool}


# ---------------------------------------------------------------- 1. DISCOVERY


@mcp.tool()
def list_capabilities(
    agent_id: str,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Ask which tables this agent may read or write, and with which operations.

    Call this FIRST, once per session. It is the answer to "does a tool exist
    for my table?" - it returns table names, allowed operations and a one-line
    purpose, but deliberately NOT column lists. Use describe_resource for those,
    only for the tables you actually touch.

    agent_id: e.g. "agent_5" (Screening). See registry.yaml for the full list.
    agent_token: required only when the server runs with REQUIRE_AGENT_AUTH.
    correlation_id: pass your journey's id to thread tracing across services.
    """
    return _guard(lambda: load_registry().capabilities(agent_id),
                  agent_id=agent_id, tool="list_capabilities",
                  agent_token=agent_token, correlation_id=correlation_id)


@mcp.tool()
def describe_resource(
    agent_id: str,
    table: str,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Get the column contract for ONE table, on demand.

    Returns the columns this agent may read and write, the primary key, JSON
    array columns that support op="append_json", and the status ladder if the
    table has one. Call it only after list_capabilities says you may use the
    table - this is the call that keeps schemas out of your context until the
    moment you need them.
    """

    def run():
        reg = load_registry()
        spec = reg.table(table)
        grant = reg.agent(agent_id)
        readable = (grant.get("read") or {}).get(table)
        write_spec = (grant.get("write") or {}).get(table) or {}

        if readable is None and not write_spec:
            raise SchemaError(
                f"Agent {agent_id!r} has no grant on {table!r}.",
                hint="Call list_capabilities to see your tables.",
            )

        out: dict[str, Any] = {
            "ok": True,
            "table": table,
            "primary_key": spec.pk,
            "purpose": spec.purpose,
            "readable_columns": readable,
            "writable_columns": write_spec.get("columns"),
            "write_operations": write_spec.get("ops") or [],
            "json_array_columns": spec.json_arrays,
            "has_json_fallback": bool(spec.json_fallback),
            "filter_operators": list(filt.OPERATORS),
        }

        if table in reg.transitions:
            t = reg.transitions[table]
            out["status_column"] = t.column
            out["transitions"] = t.map
            out["initial_status"] = t.initial
            out["this_agent_may_set"] = write_spec.get("statuses")
            out["note"] = (
                f"{table}.{t.column} is managed. An insert may set the initial state "
                f"{t.initial!r}; every later change goes through transition_status."
            )

        try:
            cols = db.live_columns(table)
            out["live_columns"] = cols
            if cols is None:
                out["live_columns_note"] = "Table is empty; showing the registry contract only."
        except McpError:
            out["live_columns"] = None
            out["live_columns_note"] = "Database not reachable; showing registry contract only."

        return out

    return _guard(run, agent_id=agent_id, tool="describe_resource",
                  agent_token=agent_token, correlation_id=correlation_id)


# -------------------------------------------------------------------- 2. READ


@mcp.tool()
def query_resource(
    agent_id: str,
    table: str,
    filters: dict | None = None,
    columns: list[str] | None = None,
    limit: int = 50,
    order_by: str | None = None,
    descending: bool = False,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Read rows from a table this agent is granted on.

    filters accept equality shorthand and operators, ANDed together:

        {"job_id": 12}                          equality
        {"score": {"gte": 70}}                  gt, gte, lt, lte, neq
        {"status": {"in": ["Applied", "Screening"]}}
        {"name": {"ilike": "rao"}}              substring, case-insensitive
        {"rejected_at": {"is_null": True}}

    Combine with order_by + descending + limit for ranked lookups, e.g. Agent
    11's next-best-fit: filters={"job_id": 12, "score": {"gte": 60}},
    order_by="rank", limit=1.

    IMPORTANT: check `source` and `stale` on the result. If Supabase was
    unreachable or the table is empty you may be reading a legacy JSON twin -
    the payload says stale=true and carries a warning. Do not treat stale data
    as authoritative for a decision that then writes.
    """

    def run():
        reg = load_registry()
        cols = reg.authorize_read(agent_id, table, columns)
        filter_cols = filt.filter_columns(filters)
        if filter_cols:
            reg.authorize_read(agent_id, table, filter_cols)
        if order_by:
            reg.authorize_read(agent_id, table, [order_by])
        return db.select(table, columns=cols, filters=filters or {},
                         limit=min(limit, 500), order_by=order_by, descending=descending)

    return _guard(run, agent_id=agent_id, tool="query_resource",
                  agent_token=agent_token, correlation_id=correlation_id)


# ------------------------------------------------------------------- 3. WRITE


@mcp.tool()
def write_resource(
    agent_id: str,
    table: str,
    op: str,
    data: dict | None = None,
    match: dict | None = None,
    json_column: str | None = None,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Write to a table this agent is granted on.

    op:
      "insert"      - new row; data is the row. May set a managed status column
                      only to its initial state (e.g. candidates 'Applied').
      "update"      - data is the changed columns; match identifies the row(s).
                      An empty match is refused (no unbounded updates).
      "upsert"      - insert or replace by primary key; data includes the PK
      "append_json" - append to a JSONB array (approval_chain, channels,
                      timeline, notes, campus_drives.candidates). Pass
                      json_column, put the item(s) in data["value"], and match
                      the single target row.
      "delete"      - hard delete; requires a non-empty match. No agent holds
                      this grant unless it was added deliberately.

    Later status changes are NOT made here - use transition_status.

    On outage: the server retries, reconnects once, then returns
    code="database_unavailable". Nothing is partially applied and nothing is
    spooled. Keep your payload and retry when the database is back.
    """

    def run():
        reg = load_registry()
        op_norm = (op or "").strip().lower()
        payload = data or {}

        if op_norm == "append_json":
            column = json_column or payload.get("column")
            if not column:
                raise SchemaError(
                    "append_json requires json_column.",
                    hint='e.g. json_column="timeline", data={"value": {...}}',
                )
            reg.authorize_write(agent_id, table, "append_json", [column])
            value = payload.get("value", payload)
            return db.append_json(table, column, value, match or {})

        if op_norm == "delete":
            reg.authorize_write(agent_id, table, "delete", list((match or {}).keys()))
            return db.delete(table, match or {})

        if op_norm not in ("insert", "update", "upsert"):
            raise SchemaError(
                f"Unknown op {op!r}.",
                hint="op must be one of: insert, update, upsert, append_json, delete.",
            )

        if not isinstance(payload, dict) or not payload:
            raise SchemaError("data must be a non-empty object.")

        reg.authorize_write(agent_id, table, op_norm, list(payload.keys()), values=payload)

        if op_norm == "insert":
            return db.insert(table, payload)
        if op_norm == "update":
            return db.update(table, payload, match or {})
        return db.upsert(table, payload)

    return _guard(run, agent_id=agent_id, tool="write_resource",
                  agent_token=agent_token, correlation_id=correlation_id)


# -------------------------------------------------------------- 4. TRANSITIONS


@mcp.tool()
def transition_status(
    agent_id: str,
    entity: str,
    entity_id: Any,
    to_status: str,
    reason: str | None = None,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Move a managed status column along its ladder.

    entity: "candidates" | "requisitions" | "interviews".

    The move is checked against the ladder AND against what this agent is
    allowed to set. An illegal move is rejected with the legal target set from
    the current state, so you can correct it directly - there is no need to
    guess or to call the resolver for this.
    """

    def run():
        reg = load_registry()
        ladder = reg.authorize_transition(agent_id, entity, to_status)
        spec = reg.table(entity)

        current_row = db.fetch_one(entity, entity_id, columns=[spec.pk, ladder.column])
        if current_row is None:
            raise SchemaError(
                f"No {entity} row with {spec.pk}={entity_id!r}.",
                hint="Check the id, or insert the row first.",
            )
        current = current_row.get(ladder.column)
        if current == to_status:
            return {"ok": True, "noop": True, "entity": entity, "entity_id": entity_id,
                    "status": to_status, "message": "Already in this state; nothing changed."}

        ladder.validate(current, to_status)
        result = db.update(entity, {ladder.column: to_status}, {spec.pk: entity_id})
        log.info("transition entity=%s id=%s %s -> %s agent=%s reason=%s",
                 entity, entity_id, current, to_status, agent_id, reason)
        return {"ok": True, "entity": entity, "entity_id": entity_id,
                "from": current, "to": to_status, "reason": reason,
                "rows": result.get("rows", [])}

    return _guard(run, agent_id=agent_id, tool="transition_status",
                  agent_token=agent_token, correlation_id=correlation_id)


# ----------------------------------------------------------------- 5. CASCADE


@mcp.tool()
def record_offer_response(
    agent_id: str,
    token: str,
    decision: str,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Record a candidate's response to an offer link (Agent 11 only).

    decision: "accepted" or "declined".

    This is one tool rather than four writes because the response cascades
    offer_links -> offer_letters -> offers -> candidates and must not half-
    apply. If any step fails, applied steps are rolled back and the response
    names any table that still needs manual repair.

    On "declined", follow up with your reselection logic and record it in
    reselection_log.
    """

    def run():
        load_registry().authorize_cascade(agent_id)
        return cascade.record_offer_response(token, decision)

    return _guard(run, agent_id=agent_id, tool="record_offer_response",
                  agent_token=agent_token, correlation_id=correlation_id)


# ---------------------------------------------------------------- 6. RESOLVER


@mcp.tool()
def resolve_call(
    agent_id: str,
    attempted_call: dict,
    error: dict | str,
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Ask Claude Haiku to repair a call that failed - OPT-IN, never automatic.

    Pass the arguments you tried and the error you got back. You receive a
    PROPOSED corrected call. It is not executed: re-submit it yourself through
    query_resource / write_resource, where it is validated against your grant
    exactly like any other call.

    Use it for unknown columns, wrong table for your intent, or near-miss enum
    values. Do NOT use it for illegal transitions (that error already tells you
    the legal targets) or for database outages (nothing to repair - retry
    later).
    """
    return _guard(lambda: resolver.resolve(agent_id, attempted_call, error),
                  agent_id=agent_id, tool="resolve_call",
                  agent_token=agent_token, correlation_id=correlation_id)


# ------------------------------------------------------- 7. HEALTH & INTEGRITY


@mcp.tool()
def health_check(
    agent_id: str = "system",
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Report database reachability, registry version and resolver availability.

    Call this when a write comes back with code="database_unavailable" to see
    whether the outage is still ongoing before retrying. Never requires
    authentication - it must stay callable during an incident.
    """

    def run():
        reg = reload_registry()
        status: dict[str, Any] = {
            "ok": True,
            "registry_version": reg.version,
            "tables": len(reg.tables),
            "agents": len(reg.agents),
            "auth_required": auth.auth_required(),
            "resolver_enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "resolver_model": resolver.MODEL,
        }
        try:
            probe = db.select(next(iter(reg.tables)), limit=1)
            status["database"] = "up" if probe.get("source") == "database" else "degraded"
            status["serving_from"] = probe.get("source")
        except McpError as exc:
            status["database"] = "down"
            status["message"] = exc.message
        return status

    return _guard(run, agent_id=agent_id, tool="health_check",
                  correlation_id=correlation_id, authenticate=False)


@mcp.tool()
def validate_registry(
    agent_id: str = "system",
    agent_token: str | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Diff registry.yaml against the live Supabase schema.

    Reports granted columns that do not exist, missing tables, broken status
    ladders and delete grants. Run this after any schema change - it is the
    difference between catching drift at startup and catching it inside an
    agent, mid-pipeline. Also available offline as: python validate_registry.py
    """
    return _guard(validator.validate, agent_id=agent_id, tool="validate_registry",
                  agent_token=agent_token, correlation_id=correlation_id)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http"):
        host = os.getenv("MCP_HOST", "127.0.0.1")
        port = int(os.getenv("MCP_PORT", "8010"))
        auth.assert_safe_startup(transport, host)
        if hasattr(getattr(mcp, "settings", None), "host"):  # mcp 1.x
            mcp.settings.host = host
            mcp.settings.port = port
            mcp.run(transport="streamable-http")
        else:  # mcp 2.x takes host/port as run() kwargs
            mcp.run(transport="streamable-http", host=host, port=port)
    else:
        mcp.run()
