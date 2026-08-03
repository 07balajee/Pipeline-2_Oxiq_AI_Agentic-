"""Opt-in call repair, backed by Claude Haiku.

Three constraints hold this design together. Do not relax them:

  1. It REPAIRS CALLS, IT NEVER EXECUTES THEM. The tool returns a corrected
     argument set; the agent decides whether to re-submit it through the normal
     write_resource / query_resource path, where it is validated exactly like
     any other call. The model therefore sits completely outside the execution
     path and cannot bypass the ACL.

  2. IT NEVER SEES ROW DATA. Its inputs are the registry slice, the column list,
     the agent's own arguments and the error string. Candidate PII never reaches
     the model.

  3. IT IS OFF BY DEFAULT AND OFF THE STATUS PATH. Nothing calls it
     automatically. transition_status failures already return the legal target
     set, which is a better answer than a guess.

If ANTHROPIC_API_KEY is unset, the server still runs - resolve_call simply
reports that repair is unavailable and returns the deterministic hint instead.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from errors import ResolverError
from registry import load_registry

log = logging.getLogger("recruitment_mcp.resolver")

MODEL = os.getenv("RESOLVER_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = int(os.getenv("RESOLVER_MAX_TOKENS", "800"))

SYSTEM = """You repair malformed database tool calls for a recruitment pipeline.

You are given: the agent's capability grant, the table schema, the tool call it
attempted, and the error it received. Return the corrected call.

Rules:
- Only use tables and columns present in the grant. Never invent either.
- If the correct table is a different one within the grant, switch to it.
- If a value is a near-miss on an enum, snap it to the legal value.
- If the call cannot be repaired from the grant alone, say so.
- You do not execute anything. You only propose.

Respond with JSON only - no prose, no markdown fences:
{
  "repairable": true | false,
  "tool": "query_resource" | "write_resource" | "transition_status",
  "arguments": { ... },
  "changed": ["short description of each change"],
  "reason": "one sentence"
}"""


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover
        raise ResolverError("anthropic SDK is not installed.") from exc
    return Anthropic(api_key=key)


def _schema_slice(agent_id: str, table: str | None) -> dict:
    reg = load_registry()
    grant = reg.agent(agent_id)
    slim: dict[str, Any] = {
        "agent_id": agent_id,
        "read": grant.get("read") or {},
        "write": grant.get("write") or {},
    }
    if table and table in reg.tables:
        spec = reg.tables[table]
        slim["table"] = {
            "name": spec.name,
            "pk": spec.pk,
            "purpose": spec.purpose,
            "json_arrays": spec.json_arrays,
        }
        if table in reg.transitions:
            t = reg.transitions[table]
            slim["table"]["status_column"] = t.column
            slim["table"]["transitions"] = t.map
    return slim


def resolve(agent_id: str, attempted_call: dict, error: dict | str) -> dict:
    table = (attempted_call or {}).get("table")
    client = _client()
    if client is None:
        return {
            "ok": True,
            "repairable": False,
            "reason": "Resolver unavailable - ANTHROPIC_API_KEY is not configured.",
            "hint": (isinstance(error, dict) and error.get("hint"))
                    or "Use list_capabilities and describe_resource to correct the call yourself.",
        }

    payload = {
        "capability_grant": _schema_slice(agent_id, table),
        "attempted_call": attempted_call,
        "error": error,
    }

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception as exc:  # noqa: BLE001 - resolver failure must never be fatal
        log.warning("resolver.call_failed err=%s", exc)
        return {
            "ok": True,
            "repairable": False,
            "reason": f"Resolver call failed: {exc}",
            "hint": (isinstance(error, dict) and error.get("hint")) or "Correct the call manually.",
        }

    cleaned = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "ok": True,
            "repairable": False,
            "reason": "Resolver did not return usable JSON.",
            "raw": text[:500],
        }

    parsed["ok"] = True
    parsed["executed"] = False
    parsed["note"] = (
        "This is a proposal, not a result. Re-submit it yourself - it will be "
        "validated against your grant like any other call."
    )
    log.info("resolver.proposed agent=%s repairable=%s", agent_id, parsed.get("repairable"))
    return parsed
