"""Agent authentication.

Default posture (stdio, agents in-process): `agent_id` is a GUARDRAIL, not auth.
Anyone who can reach the server can claim to be agent_11. That is acceptable
when the transport is a pipe you own, and its value is real - it stops LLM drift
from writing to a table the agent has no business in.

Over HTTP that stops being acceptable, because "anyone who can reach the port"
becomes a much larger set. So:

  * REQUIRE_AGENT_AUTH=true  -> every tool call must carry a valid agent_token
                               matching the claimed agent_id.
  * The server REFUSES TO START in HTTP mode on a non-loopback interface with
    auth disabled. That combination is the one that quietly lets anything on the
    network mark a candidate Hired, so it is a hard failure rather than a
    warning nobody reads.

Tokens come from AGENT_TOKENS (inline JSON) or AGENT_TOKENS_FILE (a JSON file,
preferred - keeps secrets out of the process listing).

Generate one per agent:  python -c "import secrets; print(secrets.token_urlsafe(32))"
"""

from __future__ import annotations

import hmac
import json
import logging
import os

from errors import McpError

log = logging.getLogger("recruitment_mcp.auth")

LOOPBACK = ("127.0.0.1", "localhost", "::1")


class AuthError(McpError):
    code = "unauthenticated"


def auth_required() -> bool:
    return os.getenv("REQUIRE_AGENT_AUTH", "false").strip().lower() == "true"


def _token_map() -> dict[str, str]:
    path = os.getenv("AGENT_TOKENS_FILE")
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthError(
                "Agent token file could not be read.",
                hint=f"Check AGENT_TOKENS_FILE={path!r}.",
                detail=str(exc),
            ) from exc

    inline = os.getenv("AGENT_TOKENS", "").strip()
    if not inline:
        return {}
    try:
        return json.loads(inline)
    except json.JSONDecodeError as exc:
        raise AuthError(
            "AGENT_TOKENS is not valid JSON.",
            hint='Expected {"agent_1": "<token>", ...}',
        ) from exc


def authenticate(agent_id: str, agent_token: str | None) -> None:
    """Raise unless the caller has proved it is `agent_id`.

    A no-op when REQUIRE_AGENT_AUTH is false (the stdio default).
    """
    if not auth_required():
        return

    tokens = _token_map()
    if not tokens:
        raise AuthError(
            "Authentication is required but no agent tokens are configured.",
            hint="Set AGENT_TOKENS_FILE, or disable REQUIRE_AGENT_AUTH for stdio use.",
        )

    expected = tokens.get(agent_id)
    if not expected:
        # Same message either way - do not reveal which agent_ids have tokens.
        log.warning("auth.unknown_agent agent=%s", agent_id)
        raise AuthError("Invalid agent credentials.",
                        hint="Pass agent_token matching your agent_id.")

    if not agent_token or not hmac.compare_digest(str(agent_token), str(expected)):
        log.warning("auth.bad_token agent=%s", agent_id)
        raise AuthError("Invalid agent credentials.",
                        hint="Pass agent_token matching your agent_id.")


def assert_safe_startup(transport: str, host: str) -> None:
    """Refuse the one configuration that is quietly dangerous."""
    if transport not in ("http", "streamable-http"):
        return
    if auth_required():
        return
    if host in LOOPBACK:
        log.warning(
            "HTTP transport on %s without agent auth. Fine for local development; "
            "set REQUIRE_AGENT_AUTH=true before binding to a network interface.",
            host,
        )
        return
    raise SystemExit(
        f"\nREFUSING TO START.\n"
        f"  transport=http  host={host}  REQUIRE_AGENT_AUTH=false\n\n"
        f"  Anything that can reach this port could claim to be agent_11 and mark\n"
        f"  a candidate Hired. Do one of:\n"
        f"    - set MCP_HOST=127.0.0.1 (local development), or\n"
        f"    - set REQUIRE_AGENT_AUTH=true and configure AGENT_TOKENS_FILE.\n"
    )
