"""Supabase access layer and the fallback ladder.

Fallback policy (decided deliberately, do not "improve" this without thinking):

  L0  primary query
  L1  retry transient failures (timeout / connection reset / 5xx), 2 attempts
  L2  rebuild the client once and retry - covers a stale connection
  L3  READS  : fall back to the legacy JSON twin if one is configured, and tag
               the result `stale: true` so the agent knows it is looking at a
               shadow copy.
      WRITES : stop. Raise DatabaseDownError with a plain-English message.
               No spooling, no JSON twin. A stale read is useful; a stale write
               is a lie about the state of the pipeline.

Constraint violations, FK errors and unique-key collisions are NOT transient -
they are real answers and are surfaced immediately without retry.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from typing import Any, Callable

import filters as filt
from errors import DatabaseDownError, DatabaseError, SchemaError
from registry import TableSpec, load_registry

log = logging.getLogger("recruitment_mcp.db")

HERE = os.path.dirname(os.path.abspath(__file__))

# Read at call time, not import time: a value frozen at import silently ignores
# any configuration applied after the module is first imported.


def _url() -> str:
    return os.getenv("SUPABASE_URL", "")


def _key() -> str:
    return os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")


def _data_dir() -> str:
    return os.getenv("JSON_FALLBACK_DIR", HERE)


def _max_attempts() -> int:
    return int(os.getenv("DB_MAX_ATTEMPTS", "3"))


def _base_backoff() -> float:
    return float(os.getenv("DB_BACKOFF_SECONDS", "0.4"))

_client = None

# Substrings that mean "the database did not answer" rather than "the database
# said no". Only these are retried.
_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporarily unavailable",
    "server disconnected",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "max retries exceeded",
    "name or service not known",
    "failed to establish",
    "remote end closed",
)

# HTTP 5xx gateway/proxy statuses, matched as standalone tokens. A bare substring
# check misfires: a Postgres SQLSTATE such as 23502 (not-null) or 23503 (FK)
# contains "502"/"503" and would be retried as if it were a 502 Bad Gateway,
# then surfaced as a bogus database_unavailable. Those are real rejections.
_TRANSIENT_STATUS_RE = re.compile(r"\b(502|503|504)\b")


def _is_transient(exc: Exception) -> bool:
    # A PostgREST error carrying a 5-char SQLSTATE code is the database answering.
    # Only connection (class 08) and operator-intervention (57) codes are truly
    # transient; constraint/FK/unique/type violations (23xxx, 22xxx, 42xxx, ...)
    # are permanent rejections and must never be retried.
    code = getattr(exc, "code", None)
    if isinstance(code, str) and len(code) == 5 and code[:2].isdigit():
        return code[:2] in ("08", "57")
    text = f"{type(exc).__name__} {exc}".lower()
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        return True
    return bool(_TRANSIENT_STATUS_RE.search(text))


def get_client():
    global _client
    if _client is None:
        url, key = _url(), _key()
        if not url or not key:
            raise DatabaseDownError("SUPABASE_URL / SUPABASE_SERVICE_KEY are not configured.")
        from supabase import create_client  # imported lazily so tests can stub

        _client = create_client(url, key)
    return _client


def reset_client() -> None:
    """Drop the cached client so the next call dials a fresh connection."""
    global _client
    _client = None


def _execute(fn: Callable[[Any], Any], *, op_name: str) -> Any:
    """Run `fn(client)` through the L1/L2 ladder."""
    last: Exception | None = None
    attempts = _max_attempts()
    for attempt in range(1, attempts + 1):
        try:
            return fn(get_client())
        except DatabaseDownError:
            raise
        except Exception as exc:  # noqa: BLE001 - we classify below
            last = exc
            if not _is_transient(exc):
                raise DatabaseError(str(exc), hint="This is a database rejection, not an outage.") from exc

            log.warning("db.transient op=%s attempt=%s/%s err=%s", op_name, attempt, attempts, exc)
            if attempt == attempts:
                break
            if attempt == attempts - 1:
                reset_client()  # L2: one fresh connection before giving up
            time.sleep(_base_backoff() * (2 ** (attempt - 1)) + random.uniform(0, 0.1))

    reset_client()
    raise DatabaseDownError(str(last) if last else "unknown transport failure")


# --------------------------------------------------------------------- reads


def _load_json_twin(spec: TableSpec) -> list[dict] | None:
    if not spec.json_fallback:
        return None
    path = spec.json_fallback
    if not os.path.isabs(path):
        path = os.path.join(_data_dir(), path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("json_fallback.unreadable path=%s err=%s", path, exc)
        return None

    if isinstance(data, dict):
        # Twins are stored either as {pk: row} or {"items": [...]}
        if "items" in data and isinstance(data["items"], list):
            return data["items"]
        rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                rows.append({spec.pk: key, **value})
        return rows
    if isinstance(data, list):
        return data
    return None


def select(
    table: str,
    *,
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 50,
    order_by: str | None = None,
    descending: bool = False,
) -> dict:
    spec = load_registry().table(table)
    col_expr = ",".join(columns) if columns else "*"

    def run(client):
        q = filt.apply_to_query(client.table(table).select(col_expr), filters)
        if order_by:
            q = q.order(order_by, desc=descending)
        return q.limit(limit).execute()

    try:
        result = _execute(run, op_name=f"select:{table}")
        rows = list(result.data or [])
        if rows:
            return {"ok": True, "source": "database", "stale": False, "count": len(rows), "rows": rows}

        # L3 read fallback: table is live but empty (the background_verifications
        # / schedule_roster case - the app still runs on the JSON twin).
        twin = _load_json_twin(spec)
        if twin is not None:
            twin = filt.apply_to_rows(twin, filters)[:limit]
            return {
                "ok": True,
                "source": "json_fallback",
                "stale": True,
                "count": len(twin),
                "rows": twin,
                "warning": (
                    f"{table} is empty in Supabase; served from the JSON twin. "
                    "This data may be out of date and is not authoritative."
                ),
            }
        return {"ok": True, "source": "database", "stale": False, "count": 0, "rows": []}

    except DatabaseDownError as down:
        twin = _load_json_twin(spec)
        if twin is None:
            raise
        twin = filt.apply_to_rows(twin, filters)[:limit]
        log.warning("db.down.read_served_from_twin table=%s", table)
        return {
            "ok": True,
            "source": "json_fallback",
            "stale": True,
            "count": len(twin),
            "rows": twin,
            "warning": (
                "Supabase is unreachable; served from the JSON twin. "
                "This data may be out of date and is not authoritative."
            ),
            "detail": down.extra.get("detail", ""),
        }


def fetch_one(table: str, pk_value: Any, columns: list[str] | None = None) -> dict | None:
    spec = load_registry().table(table)
    result = select(table, columns=columns, filters={spec.pk: pk_value}, limit=1)
    rows = result.get("rows") or []
    return rows[0] if rows else None


# -------------------------------------------------------------------- writes


def insert(table: str, data: dict) -> dict:
    def run(client):
        return client.table(table).insert(data).execute()

    result = _execute(run, op_name=f"insert:{table}")
    return {"ok": True, "op": "insert", "table": table, "rows": list(result.data or [])}


def update(table: str, data: dict, match: dict) -> dict:
    if not match:
        raise SchemaError(
            "update requires a non-empty match.",
            hint="Refusing an unbounded UPDATE - pass match={'id': ...}.",
        )

    def run(client):
        q = client.table(table).update(data)
        for key, value in match.items():
            q = q.eq(key, value)
        return q.execute()

    result = _execute(run, op_name=f"update:{table}")
    return {"ok": True, "op": "update", "table": table, "rows": list(result.data or [])}


def upsert(table: str, data: dict) -> dict:
    def run(client):
        return client.table(table).upsert(data).execute()

    result = _execute(run, op_name=f"upsert:{table}")
    return {"ok": True, "op": "upsert", "table": table, "rows": list(result.data or [])}


def delete(table: str, match: dict) -> dict:
    """Hard delete. Requires a non-empty match; no agent holds this grant by
    default (see registry.yaml - add ops: [delete] deliberately)."""
    if not match:
        raise SchemaError(
            "delete requires a non-empty match.",
            hint="Refusing an unbounded DELETE - pass match={'id': ...}.",
        )

    def run(client):
        q = client.table(table).delete()
        for key, value in match.items():
            q = q.eq(key, value)
        return q.execute()

    result = _execute(run, op_name=f"delete:{table}")
    rows = list(result.data or [])
    return {"ok": True, "op": "delete", "table": table, "deleted": len(rows), "rows": rows}


def live_columns(table: str) -> list[str] | None:
    """Actual column names from Postgres, for registry validation.

    Prefers the table_columns() RPC (works on empty tables); falls back to the
    keys of a sample row, which returns None if the table is empty.
    """
    try:
        def run_rpc(client):
            return client.rpc("table_columns", {"p_table": table}).execute()

        result = _execute(run_rpc, op_name=f"columns_rpc:{table}")
        rows = list(result.data or [])
        if rows:
            if isinstance(rows[0], dict):
                return sorted(r.get("column_name") for r in rows if r.get("column_name"))
            return sorted(str(r) for r in rows)
    except (DatabaseError, DatabaseDownError):
        pass

    sample = select(table, limit=1)
    if sample.get("source") != "database" or not sample.get("rows"):
        return None
    return sorted(sample["rows"][0].keys())


def append_json(table: str, column: str, value: Any, match: dict) -> dict:
    """Append to a JSONB array column.

    Agents 2, 4, 7, 8 and 14 all need this (approval_chain, channels, timeline,
    notes, campus_drives.candidates). A plain upsert would clobber the array, so
    this is a read-modify-write. To make it atomic under concurrency, deploy
    sql/atomic_helpers.sql and set USE_RPC_APPEND=true.
    """
    spec = load_registry().table(table)
    if column not in spec.json_arrays:
        raise SchemaError(
            f"{table}.{column} is not registered as a JSON array column.",
            hint=f"Appendable columns on {table}: {spec.json_arrays or 'none'}.",
        )
    if not match:
        raise SchemaError("append_json requires a match identifying exactly one row.")

    if os.getenv("USE_RPC_APPEND", "false").lower() == "true":
        pk_value = match.get(spec.pk)

        def run_rpc(client):
            return client.rpc(
                "append_json_array",
                {
                    "p_table": table,
                    "p_column": column,
                    "p_pk_column": spec.pk,
                    "p_pk_value": str(pk_value),
                    "p_value": value if isinstance(value, list) else [value],
                },
            ).execute()

        result = _execute(run_rpc, op_name=f"append_rpc:{table}.{column}")
        return {"ok": True, "op": "append_json", "table": table, "column": column,
                "atomic": True, "rows": list(result.data or [])}

    current = select(table, columns=[spec.pk, column], filters=match, limit=1)
    if current.get("stale"):
        raise DatabaseDownError("Refusing to append on top of a stale JSON-twin read.")
    rows = current.get("rows") or []
    if not rows:
        raise SchemaError(
            f"No row in {table} matching {match}.",
            hint="Insert the row before appending to its JSON array.",
        )

    existing = rows[0].get(column) or []
    if not isinstance(existing, list):
        raise SchemaError(f"{table}.{column} is not a JSON array in the database.")
    items = value if isinstance(value, list) else [value]
    merged = existing + items

    out = update(table, {column: merged}, match)
    out.update({"op": "append_json", "column": column, "atomic": False,
                "appended": len(items), "length": len(merged)})
    return out
