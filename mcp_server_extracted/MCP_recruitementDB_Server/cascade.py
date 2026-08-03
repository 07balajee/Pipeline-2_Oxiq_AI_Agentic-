"""The one multi-table write that must not half-apply.

Agent 11's public offer response cascades:

    offer_links.status -> offer_letters.status -> offers.status -> candidates.status

Four tables, one logical fact. If a generic write_resource did this in four
calls and the third failed, the candidate would be Hired against a Pending
offer - the pipeline would be lying about a person's employment.

Preferred path: the Postgres function in sql/offer_cascade.sql, which does all
four in one transaction. Deploy it and set USE_RPC_CASCADE=true.

Fallback path: sequential writes in dependency order, with compensation. If a
step fails, already-applied steps are rolled back in reverse. If a compensation
itself fails (DB went down mid-cascade), the response reports exactly which
tables are inconsistent so a human can repair rather than guess.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import db
from errors import DatabaseDownError, McpError, SchemaError

log = logging.getLogger("recruitment_mcp.cascade")

DECISIONS = {
    "accepted": {
        "offer_links": "Accepted",
        "offer_letters": "Accepted",
        "offers": "Accepted",
        "candidates": "Hired",
    },
    "declined": {
        "offer_links": "Declined",
        "offer_letters": "Declined",
        "offers": "Declined",
        "candidates": "Declined",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_offer_response(token: str, decision: str) -> dict:
    decision = (decision or "").strip().lower()
    if decision not in DECISIONS:
        raise SchemaError(
            f"Unknown decision {decision!r}.",
            hint="decision must be 'accepted' or 'declined'.",
        )
    targets = DECISIONS[decision]

    if os.getenv("USE_RPC_CASCADE", "false").lower() == "true":
        def run(client):
            return client.rpc(
                "record_offer_response",
                {"p_token": token, "p_decision": decision},
            ).execute()

        result = db._execute(run, op_name="cascade_rpc")
        return {
            "ok": True,
            "atomic": True,
            "decision": decision,
            "applied": list(targets),
            "rows": list(result.data or []),
        }

    # ---- resolve the chain first; read failures are cheap and harmless ------
    link_rows = db.select(
        "offer_links",
        columns=["id", "token", "offer_letter_id", "candidate_name", "status"],
        filters={"token": token},
        limit=1,
    )
    if link_rows.get("stale"):
        raise DatabaseDownError("Refusing to run the offer cascade against a stale read.")
    links = link_rows.get("rows") or []
    if not links:
        raise SchemaError(
            f"No offer link found for token {token!r}.",
            hint="The token may be wrong or the link may never have been generated.",
        )
    link = links[0]

    if (link.get("status") or "").lower() not in ("pending", "sent", ""):
        return {
            "ok": True,
            "noop": True,
            "message": f"Offer link already resolved as {link.get('status')!r}; nothing changed.",
            "decision": decision,
        }

    letter = db.fetch_one("offer_letters", link["offer_letter_id"],
                          columns=["id", "candidate_id", "status"])
    if not letter:
        raise SchemaError(
            f"offer_letters row {link['offer_letter_id']!r} is missing.",
            hint="The offer link points at a letter that no longer exists.",
        )
    candidate_id = letter["candidate_id"]

    offer_rows = db.select("offers", columns=["id", "candidate_id", "status"],
                           filters={"candidate_id": candidate_id}, limit=1)
    offer = (offer_rows.get("rows") or [None])[0]

    # ---- apply in dependency order, remembering how to undo each step -------
    applied: list[tuple[str, dict, dict]] = []  # (table, restore_data, match)

    def step(table: str, data: dict, match: dict, previous: dict) -> None:
        db.update(table, data, match)
        applied.append((table, previous, match))

    try:
        step("offer_links", {"status": targets["offer_links"]},
             {"id": link["id"]}, {"status": link.get("status")})

        step("offer_letters", {"status": targets["offer_letters"]},
             {"id": letter["id"]}, {"status": letter.get("status")})

        if offer:
            step("offers", {"status": targets["offers"]},
                 {"id": offer["id"]}, {"status": offer.get("status")})

        step("candidates", {"status": targets["candidates"]},
             {"id": candidate_id}, {"status": None})

    except McpError as exc:
        failed_at = len(applied)
        rolled_back, stuck = [], []
        for table, previous, match in reversed(applied):
            if previous.get("status") is None:
                continue
            try:
                db.update(table, previous, match)
                rolled_back.append(table)
            except McpError:
                stuck.append(table)

        log.error("cascade.failed token=%s step=%s stuck=%s", token, failed_at, stuck)
        message = (
            exc.message
            if not stuck
            else f"{exc.message} Rollback incomplete - these tables need manual repair: {stuck}."
        )
        failure = McpError(
            message,
            hint=exc.hint,
            cascade="failed",
            rolled_back=rolled_back,
            needs_manual_repair=stuck,
            failed_at_step=failed_at,
            **{k: v for k, v in exc.extra.items() if k not in ("cascade",)},
        )
        failure.code = exc.code           # keep 'database_unavailable' etc. intact
        failure.retryable = exc.retryable and not stuck
        raise failure from exc

    return {
        "ok": True,
        "atomic": False,
        "decision": decision,
        "token": token,
        "candidate_id": candidate_id,
        "applied": [t for t, _, _ in applied],
        "recorded_at": _now(),
        "next": (
            "Candidate is Hired - onboarding can be triggered."
            if decision == "accepted"
            else "Offer declined - run reselection and log it in reselection_log."
        ),
    }
