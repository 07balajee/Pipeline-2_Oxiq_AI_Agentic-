"""Agent 8 core - wires the three human-in-the-loop turns (form -> ranking
approval -> persist) together against injected MCP implementations. Ported
unchanged from the standalone agent8_hr_interview_ranking reference
implementation; agents/agent8/agent.py is the Pipeline-2 adapter that maps
these turns onto WorkflowContext / AgentResponse and the master graph's
approval-gated state machine.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal

from . import scoring, confidence as confidence_mod, validation
from .errors import AgentError, ErrorCode
from .mcp.base import (
    DatabaseMCP, AnalyticsMCP, PolicyMCP, SalaryBandMCP,
    ResumeMCP, DocumentMCP, NotificationMCP, MeetMCP, LLMRationaleMCP,
)


class Agent8:
    def __init__(
        self,
        db: DatabaseMCP,
        analytics: AnalyticsMCP,
        policy: PolicyMCP,
        salary_band: SalaryBandMCP,
        resume: ResumeMCP,
        document: DocumentMCP,
        notification: NotificationMCP,
        meet: MeetMCP,
        llm: LLMRationaleMCP,
    ):
        self.db = db
        self.analytics = analytics
        self.policy = policy
        self.salary_band = salary_band
        self.resume = resume
        self.document = document
        self.notification = notification
        self.meet = meet
        self.llm = llm

    # ---------------------------------------------------------------- Turn 1
    def turn1_pre_round(self, envelope: dict) -> dict:
        ctx = envelope["context"]
        candidate = ctx["candidate"]

        interviews = self.db.read("interviews", {"candidate_id": candidate["id"]})
        technical_scores = self.db.read("interview_scores", {"candidate_id": candidate["id"]})

        validation.validate_pre_round(candidate, interviews, technical_scores)

        profile = self.resume.get_profile(candidate["id"])
        form_url = self.document.generate("hr_evaluation_form", candidate, ctx["job"], "HR")

        if ctx["interview"]["mode"] == "online":
            self.meet.validate(ctx["interview"]["meeting_link"])

        return {
            "trace_id": envelope["trace_id"],
            "agent": "Agent8_HRInterviewRanking",
            "status": "needs_human",
            "data": {"profile": profile, "evaluation_form_url": form_url, "draft_observations": "DRAFT - not scores"},
            "human_escalation": {"required": True, "reason": "hr_evaluation_needed"},
            "confidence": 1.0,
        }

    # ---------------------------------------------------------------- Turn 2
    def turn2_compute_and_rank(self, envelope: dict) -> dict:
        idem = envelope["idempotency_key"]
        cached = self.db.read("turn2_snapshots", {"idempotency_key": idem})
        if cached:
            # Replay of an already-computed Turn 2 (orchestrator retry, etc.).
            # Return exactly what the human saw before - never re-derive the
            # ranking table or re-call the LLM, since either could drift
            # (underlying rows may have changed, and rationale drafting is
            # non-deterministic).
            response = dict(cached[0]["response"])
            response["_internal_ranked"] = self._deserialize_ranked(cached[0]["ranked"])
            return response

        ctx = envelope["context"]
        candidate = ctx["candidate"]
        weights = envelope["human_decisions"]["weights"]
        evaluation = envelope["human_decisions"]["evaluation"]

        existing_hr = self.db.read("interview_scores", {"candidate_id": candidate["id"], "round": "HR"})
        cohort_technical = {
            cid: self._latest_technical_score(cid) for cid in ctx["cohort"]
        }

        validation.validate_pre_rank(
            evaluation, cohort_technical, weights_used_elsewhere=None,
            weights=weights, existing_hr_score=(existing_hr[0] if existing_hr else None),
        )

        is_leadership_track = ctx["requisition"]["grade"].lower().startswith("lead")

        hr_score = self.analytics.compute_hr_score(evaluation, is_leadership_track)
        analytics_mismatch = False
        local_hr_score = scoring.compute_hr_score(
            evaluation["communication_rating"], evaluation["culture_fit_rating"],
            evaluation["behaviour_rating"], evaluation.get("motivation_rating"),
            evaluation.get("leadership_rating"), is_leadership_track,
        )
        if hr_score is None:
            hr_score = local_hr_score
        elif hr_score != local_hr_score:
            analytics_mismatch = True
            hr_score = local_hr_score  # §8 formula always wins

        # Build the full cohort's CandidateScore objects.
        cohort_scores = []
        for cid in ctx["cohort"]:
            tech = cohort_technical[cid]
            this_hr = hr_score if cid == candidate["id"] else self._latest_hr_score(cid)
            if this_hr is None:
                continue  # excluded - no HR round yet, never imputed
            final = scoring.compute_final_score(tech, this_hr, weights)
            cohort_scores.append(scoring.CandidateScore(
                candidate_id=cid, technical_score=tech, hr_score=this_hr, final_score=final,
                screening_score=self._latest_screening_score(cid),
                applied_at=self._applied_at(cid),
            ))

        ranked, unresolved_ties = scoring.rank_cohort(cohort_scores)
        for c in ranked:
            c.recommendation = scoring.recommend(
                c.rank, c.final_score, ctx["positions_available"], c.technical_score, c.hr_score
            )
        anomalies = scoring.detect_anomalies(ranked, ctx["positions_available"])
        conf = confidence_mod.compute_confidence(anomalies, unresolved_ties)

        policy_result = self.policy.check(envelope["job_id"], ctx["cohort"], {})
        band_result = self.salary_band.check(
            ctx["requisition"]["grade"], ctx["requisition"]["estimated_ctc"], None
        )

        this_candidate = next(c for c in ranked if c.candidate_id == candidate["id"])
        rationale = self.llm.draft_rationale({
            "final_score": str(this_candidate.final_score),
            "technical_score": this_candidate.technical_score,
            "hr_score": this_candidate.hr_score,
            "cohort_size": len(ranked),
            "rank": this_candidate.rank,
            "overall_comments": evaluation.get("overall_comments", ""),
        })

        warnings = []
        if analytics_mismatch:
            warnings.append({"code": "ANALYTICS_MISMATCH", "message": "local §8 formula used; Analytics MCP disagreed"})
        if unresolved_ties:
            warnings.append({"code": "CUT_LINE_TIE", "message": f"Unresolved ties: {unresolved_ties}"})
        if not band_result["within_band"]:
            warnings.append({"code": "BAND_MISMATCH", "message": "Candidate expectation outside salary band (advisory)"})

        response = {
            "trace_id": envelope["trace_id"],
            "agent": "Agent8_HRInterviewRanking",
            "status": "needs_human",
            "data": {
                "formula": "0.60*technical + 0.40*hr; hr = weighted rating composite, ROUND_HALF_UP",
                "cohort_ranking": [
                    {"rank": c.rank, "candidate_id": c.candidate_id, "final": str(c.final_score),
                     "recommendation": c.recommendation}
                    for c in ranked
                ],
                "rationale": rationale,
                "flags": anomalies,
                "policy_allowed": policy_result["allowed"],
            },
            "human_escalation": {
                "required": True,
                "reason": "final_decision_approval",
                "ranking_preview": [
                    {"rank": c.rank, "candidate_id": c.candidate_id, "technical": c.technical_score,
                     "hr": c.hr_score, "final": str(c.final_score), "recommendation": c.recommendation}
                    for c in ranked
                ],
            },
            "warnings": warnings,
            "confidence": conf,
        }

        candidate_status = {c.candidate_id: self._candidate_status(c.candidate_id) for c in ranked}
        self.db.write("turn2_snapshots", "INSERT", {}, {
            "idempotency_key": idem,
            "trace_id": envelope["trace_id"],
            "response": response,
            "ranked": self._serialize_ranked(ranked),
            "candidate_status": candidate_status,
        }, f"{idem}-turn2-snapshot")

        response["_internal_ranked"] = ranked  # not part of the public schema - carried to Turn 3 by the caller
        return response

    # ---------------------------------------------------------------- Turn 3
    def turn3_persist(self, envelope: dict, ranked: list[scoring.CandidateScore]) -> dict:
        ctx = envelope["context"]
        idem = envelope["idempotency_key"]
        this_candidate_id = envelope["candidate_id"]

        snapshot_rows = self.db.read("turn2_snapshots", {"idempotency_key": idem})
        snapshot = snapshot_rows[0] if snapshot_rows else None
        snapshot_ranked = None
        current_by_candidate: dict[int, dict] = {}
        if snapshot:
            candidate_status_at_approval = snapshot["candidate_status"]
            snapshot_ranked = [
                dict(row, status=candidate_status_at_approval.get(row["candidate_id"]))
                for row in snapshot["ranked"]
            ]
            for row in snapshot_ranked:
                cid = row["candidate_id"]
                current_by_candidate[cid] = {
                    "technical_score": self._latest_technical_score(cid),
                    "hr_score": self._latest_hr_score(cid),
                    "status": self._candidate_status(cid),
                }
            # The acting candidate's HR score is written by THIS turn, so it
            # is never yet in the DB when we check - compare everything else
            # (technical score, status) but not a field this turn itself owns.
            if this_candidate_id in current_by_candidate:
                current_by_candidate[this_candidate_id]["hr_score"] = next(
                    r["hr_score"] for r in snapshot_ranked if r["candidate_id"] == this_candidate_id
                )
        validation.validate_ranking_snapshot_current(snapshot_ranked, current_by_candidate)

        decision = envelope["human_decisions"]["final_decision"]
        policy_result = self.policy.check(envelope["job_id"], ctx["cohort"], decision or {})

        selected_count = sum(1 for c in ranked if c.recommendation == "Selected")
        validation.validate_pre_persist(
            policy_allowed=policy_result["allowed"],
            selected_count=selected_count,
            positions_available=ctx["positions_available"],
            overselection_override=bool(decision and decision.get("override_positions")),
        )

        idem = envelope["idempotency_key"]
        this_candidate = next(c for c in ranked if c.candidate_id == envelope["candidate_id"])

        db_writes = []
        row = self.db.write("interview_scores", "INSERT", {}, {
            "candidate_id": this_candidate.candidate_id, "round": "HR",
            "score": this_candidate.hr_score, "rank": this_candidate.rank,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "idempotency_key": idem,
        }, idem)
        db_writes.append({"table": "interview_scores", "op": "INSERT", "id": row.get("id"),
                           "fields": {"round": "HR", "score": this_candidate.hr_score, "rank": this_candidate.rank}})

        for c in ranked:
            self.db.write("interview_scores", "UPDATE", {"candidate_id": c.candidate_id, "round": "HR"},
                           {"rank": c.rank}, f"{idem}-rank-{c.candidate_id}")
        db_writes.append({"table": "interview_scores", "op": "UPDATE", "id": "cohort",
                           "fields": {"rank": f"back-filled for {len(ranked)} candidates"}})

        status_map = {"Selected": "Offer", "Rejected": "Declined"}
        new_status = status_map.get(this_candidate.recommendation)  # None for Waitlist - no write
        if new_status:
            self.db.write("candidates", "UPDATE", {"id": this_candidate.candidate_id},
                           {"status": new_status}, f"{idem}-status")
            db_writes.append({"table": "candidates", "op": "UPDATE", "id": this_candidate.candidate_id,
                               "fields": {"status": new_status}})

        self.db.write("interviews", "UPDATE", {"candidate_id": this_candidate.candidate_id, "round": "HR"},
                       {"status": "Completed"}, f"{idem}-interview-status")
        db_writes.append({"table": "interviews", "op": "UPDATE", "id": ctx["interview"]["interview_id"],
                           "fields": {"status": "Completed"}})

        self.notification.send("email", ctx["candidate"]["email"], "hr_outcome",
                                {"recommendation": this_candidate.recommendation})

        return {
            "trace_id": envelope["trace_id"],
            "agent": "Agent8_HRInterviewRanking",
            "status": "success",
            "handoff": {"candidate_id": this_candidate.candidate_id, "job_id": envelope["job_id"],
                        "current_agent": "OfferGenerator"},
            "data": {
                "final_rank": this_candidate.rank,
                "final_score": str(this_candidate.final_score),
                "recommendation": this_candidate.recommendation,
            },
            "db_writes": db_writes,
            "confidence": 1.0,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _serialize_ranked(ranked: list[scoring.CandidateScore]) -> list[dict]:
        return [
            {
                "candidate_id": c.candidate_id, "technical_score": c.technical_score,
                "hr_score": c.hr_score, "final_score": str(c.final_score),
                "screening_score": c.screening_score, "applied_at": c.applied_at,
                "rank": c.rank, "recommendation": c.recommendation,
            }
            for c in ranked
        ]

    @staticmethod
    def _deserialize_ranked(rows: list[dict]) -> list[scoring.CandidateScore]:
        return [
            scoring.CandidateScore(
                candidate_id=r["candidate_id"], technical_score=r["technical_score"],
                hr_score=r["hr_score"], final_score=Decimal(r["final_score"]),
                screening_score=r["screening_score"], applied_at=r["applied_at"],
                rank=r["rank"], recommendation=r["recommendation"],
            )
            for r in rows
        ]

    def _latest_technical_score(self, candidate_id: int) -> float | None:
        rows = self.db.read("interview_scores", {"candidate_id": candidate_id, "round": "Technical"})
        return rows[-1]["score"] if rows else None

    def _latest_hr_score(self, candidate_id: int) -> int | None:
        rows = self.db.read("interview_scores", {"candidate_id": candidate_id, "round": "HR"})
        return rows[-1]["score"] if rows else None

    def _latest_screening_score(self, candidate_id: int) -> float:
        rows = self.db.read("screening_results", {"candidate_id": candidate_id})
        return rows[-1]["screening_score"] if rows else 0.0

    def _applied_at(self, candidate_id: int) -> str:
        rows = self.db.read("candidates", {"id": candidate_id})
        return rows[0].get("applied_at", "") if rows else ""

    def _candidate_status(self, candidate_id: int) -> str | None:
        rows = self.db.read("candidates", {"id": candidate_id})
        return rows[0].get("status") if rows else None
