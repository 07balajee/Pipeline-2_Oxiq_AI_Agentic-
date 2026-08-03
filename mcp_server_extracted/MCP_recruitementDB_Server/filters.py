"""Filter operators for query_resource.

Two forms are accepted:

    {"job_id": 12}                      -> equality (shorthand)
    {"score": {"gte": 70}}              -> operator form
    {"status": {"in": ["Applied", "Screening"]}}
    {"rank": {"lte": 3}, "job_id": 12}  -> ANDed together

The same operator set is implemented twice on purpose: once against PostgREST
for the live path, once in pure Python for the JSON-twin fallback path, so a
degraded read filters identically to a live one instead of silently returning
everything.
"""

from __future__ import annotations

from typing import Any

from errors import SchemaError

OPERATORS = ("eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike", "in", "is_null")


def _normalise(filters: dict | None) -> list[tuple[str, str, Any]]:
    """-> [(column, operator, value), ...]"""
    out: list[tuple[str, str, Any]] = []
    for column, raw in (filters or {}).items():
        if isinstance(raw, dict):
            if not raw:
                raise SchemaError(
                    f"Empty filter object for {column!r}.",
                    hint=f"Use one of: {', '.join(OPERATORS)}.",
                )
            for op, value in raw.items():
                op_norm = op.strip().lower()
                if op_norm not in OPERATORS:
                    raise SchemaError(
                        f"Unknown filter operator {op!r} on {column!r}.",
                        hint=f"Supported operators: {', '.join(OPERATORS)}.",
                    )
                if op_norm == "in" and not isinstance(value, (list, tuple)):
                    raise SchemaError(
                        f"Operator 'in' on {column!r} needs a list.",
                        hint='e.g. {"status": {"in": ["Applied", "Screening"]}}',
                    )
                out.append((column, op_norm, value))
        else:
            out.append((column, "eq", raw))
    return out


def filter_columns(filters: dict | None) -> list[str]:
    return [c for c, _, _ in _normalise(filters)]


def apply_to_query(query, filters: dict | None):
    """Apply filters to a PostgREST query builder."""
    for column, op, value in _normalise(filters):
        if op == "eq":
            query = query.eq(column, value)
        elif op == "neq":
            query = query.neq(column, value)
        elif op == "gt":
            query = query.gt(column, value)
        elif op == "gte":
            query = query.gte(column, value)
        elif op == "lt":
            query = query.lt(column, value)
        elif op == "lte":
            query = query.lte(column, value)
        elif op == "like":
            query = query.like(column, value)
        elif op == "ilike":
            query = query.ilike(column, value)
        elif op == "in":
            query = query.in_(column, list(value))
        elif op == "is_null":
            query = query.is_(column, "null" if value else "not.null")
    return query


def _matches(row: dict, column: str, op: str, value: Any) -> bool:
    actual = row.get(column)
    try:
        if op == "eq":
            return actual == value
        if op == "neq":
            return actual != value
        if op == "is_null":
            return (actual is None) if value else (actual is not None)
        if op == "in":
            return actual in list(value)
        if op in ("like", "ilike"):
            if actual is None:
                return False
            pattern = str(value).replace("%", "")
            haystack, needle = str(actual), pattern
            if op == "ilike":
                haystack, needle = haystack.lower(), needle.lower()
            return needle in haystack
        if actual is None:
            return False
        if op == "gt":
            return actual > value
        if op == "gte":
            return actual >= value
        if op == "lt":
            return actual < value
        if op == "lte":
            return actual <= value
    except TypeError:
        return False
    return False


def apply_to_rows(rows: list[dict], filters: dict | None) -> list[dict]:
    """Same semantics, applied in Python to JSON-twin rows."""
    clauses = _normalise(filters)
    return [row for row in rows if all(_matches(row, c, o, v) for c, o, v in clauses)]
