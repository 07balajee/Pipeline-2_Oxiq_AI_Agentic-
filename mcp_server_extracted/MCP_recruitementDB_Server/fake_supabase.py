"""A minimal in-memory stand-in for the Supabase client.

Enough of the PostgREST builder surface for db.py to run against it unchanged,
so the tests exercise the real filter, retry and cascade code paths rather than
mocks of them.
"""

from __future__ import annotations

import copy
from typing import Any


class FakeQuery:
    def __init__(self, store: "FakeClient", table: str, action: str,
                 payload: Any = None):
        self.store = store
        self.table_name = table
        self.action = action
        self.payload = payload
        self.clauses: list[tuple[str, str, Any]] = []
        self.columns = "*"
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    # ---- builder -------------------------------------------------------
    def select(self, columns="*"):
        self.columns = columns
        return self

    def eq(self, c, v):      self.clauses.append((c, "eq", v));      return self
    def neq(self, c, v):     self.clauses.append((c, "neq", v));     return self
    def gt(self, c, v):      self.clauses.append((c, "gt", v));      return self
    def gte(self, c, v):     self.clauses.append((c, "gte", v));     return self
    def lt(self, c, v):      self.clauses.append((c, "lt", v));      return self
    def lte(self, c, v):     self.clauses.append((c, "lte", v));     return self
    def like(self, c, v):    self.clauses.append((c, "like", v));    return self
    def ilike(self, c, v):   self.clauses.append((c, "ilike", v));   return self
    def in_(self, c, v):     self.clauses.append((c, "in", v));      return self
    def is_(self, c, v):     self.clauses.append((c, "is", v));      return self

    def order(self, column, desc=False):
        self._order = (column, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # ---- execution -----------------------------------------------------
    def _matches(self, row: dict) -> bool:
        for column, op, value in self.clauses:
            actual = row.get(column)
            if op == "eq" and actual != value:
                return False
            if op == "neq" and actual == value:
                return False
            if op == "in" and actual not in value:
                return False
            if op == "is":
                is_null = actual is None
                if value == "null" and not is_null:
                    return False
                if value == "not.null" and is_null:
                    return False
            if op in ("like", "ilike"):
                needle = str(value).replace("%", "")
                hay = str(actual or "")
                if op == "ilike":
                    hay, needle = hay.lower(), needle.lower()
                if needle not in hay:
                    return False
            if op in ("gt", "gte", "lt", "lte"):
                if actual is None:
                    return False
                if op == "gt" and not actual > value:
                    return False
                if op == "gte" and not actual >= value:
                    return False
                if op == "lt" and not actual < value:
                    return False
                if op == "lte" and not actual <= value:
                    return False
        return True

    def execute(self):
        self.store.calls.append((self.action, self.table_name))
        rows = self.store.data.setdefault(self.table_name, [])

        if self.action == "select":
            out = [copy.deepcopy(r) for r in rows if self._matches(r)]
            if self._order:
                column, desc = self._order
                out.sort(key=lambda r: (r.get(column) is None, r.get(column)), reverse=desc)
            if self._limit is not None:
                out = out[: self._limit]
            if self.columns != "*":
                wanted = [c.strip() for c in self.columns.split(",")]
                out = [{k: v for k, v in r.items() if k in wanted} for r in out]
            return FakeResult(out)

        if self.action == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            created = []
            for item in items:
                row = copy.deepcopy(item)
                row.setdefault("id", len(rows) + 1)
                rows.append(row)
                created.append(copy.deepcopy(row))
            return FakeResult(created)

        if self.action == "update":
            changed = []
            for row in rows:
                if self._matches(row):
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return FakeResult(changed)

        if self.action == "upsert":
            row = copy.deepcopy(self.payload)
            pk = "id" if "id" in row else next(iter(row))
            for existing in rows:
                if existing.get(pk) == row.get(pk):
                    existing.update(row)
                    return FakeResult([copy.deepcopy(existing)])
            rows.append(row)
            return FakeResult([copy.deepcopy(row)])

        if self.action == "delete":
            removed = [copy.deepcopy(r) for r in rows if self._matches(r)]
            self.store.data[self.table_name] = [r for r in rows if not self._matches(r)]
            return FakeResult(removed)

        raise AssertionError(f"unsupported action {self.action}")


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTableHandle:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def select(self, columns="*"):
        return FakeQuery(self.store, self.name, "select").select(columns)

    def insert(self, payload):
        return FakeQuery(self.store, self.name, "insert", payload)

    def update(self, payload):
        return FakeQuery(self.store, self.name, "update", payload)

    def upsert(self, payload):
        return FakeQuery(self.store, self.name, "upsert", payload)

    def delete(self):
        return FakeQuery(self.store, self.name, "delete")


class FakeClient:
    """`data` maps table name -> list of row dicts."""

    def __init__(self, data: dict[str, list[dict]] | None = None):
        self.data = data or {}
        self.calls: list[tuple[str, str]] = []
        self.fail_on: dict[tuple[str, str], Exception] = {}

    def table(self, name):
        return FakeTableHandle(self, name)

    def rpc(self, *_args, **_kwargs):
        raise Exception("rpc not available in this fake")


class FlakyClient(FakeClient):
    """Raises `error` for the first `fail_times` calls, then behaves normally."""

    def __init__(self, data=None, error=None, fail_times=0):
        super().__init__(data)
        self.error = error or ConnectionError("Connection reset by peer")
        self.remaining = fail_times

    def table(self, name):
        if self.remaining > 0:
            self.remaining -= 1
            raise self.error
        return super().table(name)


class FailingStepClient(FakeClient):
    """Fails the Nth write to a given table - used to test cascade rollback."""

    def __init__(self, data=None, fail_table=None, error=None):
        super().__init__(data)
        self.fail_table = fail_table
        self.error = error or ConnectionError("Connection reset by peer")

    def table(self, name):
        if name == self.fail_table:
            raise self.error
        return super().table(name)
