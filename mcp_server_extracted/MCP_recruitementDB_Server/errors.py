"""Error types for the recruitment MCP server.

Every error carries a `code` (machine-readable, for the agent to branch on) and
a `message` (plain English, safe to surface to a human). `hint` tells the agent
what to do next - this is what stops it from burning turns guessing.
"""

from __future__ import annotations

from typing import Any


class McpError(Exception):
    code = "error"
    retryable = False

    def __init__(self, message: str, *, hint: str | None = None, **extra: Any):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.extra = extra

    def to_dict(self) -> dict:
        payload: dict[str, Any] = {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.hint:
            payload["hint"] = self.hint
        payload.update(self.extra)
        return payload


class CapabilityError(McpError):
    """Agent asked for a table/op its registry grant does not cover."""

    code = "capability_denied"


class SchemaError(McpError):
    """Unknown table, unknown column, or a column the agent may not touch."""

    code = "schema_error"


class TransitionError(McpError):
    """Illegal status move. `extra` carries the legal set."""

    code = "illegal_transition"


class DatabaseDownError(McpError):
    """Supabase unreachable after retries and a fresh connection."""

    code = "database_unavailable"
    retryable = True

    def __init__(self, detail: str = "", **extra: Any):
        super().__init__(
            "Supabase is down - check your Supabase project's status health.",
            hint=(
                "The write was NOT applied. Nothing was partially saved. "
                "Keep your payload and retry once the database is reachable."
            ),
            detail=detail,
            **extra,
        )


class DatabaseError(McpError):
    """A real database answer that happens to be a rejection (constraint, FK,
    unique violation). Not retryable - retrying produces the same result."""

    code = "database_error"


class ResolverError(McpError):
    code = "resolver_failed"
