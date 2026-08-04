from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger
from shared.config.constants import (
    STATE_HR_RANKING_PENDING,
    STATE_HR_INTERVIEW_COMPLETED,
    STATE_HR_EVALUATION_AWAITED,
    STATE_CANDIDATE_RANKING_AWAITED,
    EVENT_HR_EVALUATION_REQUESTED,
    EVENT_HR_SCORE_SUBMITTED,
    EVENT_CANDIDATE_RANKED,
)

from .store import agent8_core, db, seed_candidate_demo_data, to_internal_id
from .errors import AgentError, ErrorCode


def _derive_technical_score(context: WorkflowContext) -> float:
    """Turns Agent 7's 0-10 sub-scores (or their absence) into the 0-100
    technical_score Agent 8's scoring formula expects. Demo-stage bridge
    until a real technical_scorecard flows through step_data."""
    scores = context.step_data.get("technical_scores")
    if not scores:
        return 75.0
    values = [v for v in scores.values() if isinstance(v, (int, float))]
    if not values:
        return 75.0
    return round(sum(values) / len(values) * 10, 1)


def _build_envelope(context: WorkflowContext, human_decisions: dict | None = None) -> dict:
    """Translates Pipeline-2's WorkflowContext into Agent 8's Universal
    Request Envelope (§4). Requisition/cohort/interview details Pipeline-2
    doesn't natively carry yet are read from step_data if a prior step
    populated them, else default to single-candidate demo values - the same
    "mocked for now" posture already used throughout Pipeline-2."""
    candidate = context.candidate
    candidate_id = to_internal_id("candidate", candidate.candidate_id)
    job_id = to_internal_id("job", candidate.job_id)
    idem = f"{context.workflow_id}-hr"

    requisition = context.step_data.get("requisition") or {
        "id": f"req-{job_id}",
        "count": context.step_data.get("positions_available", 1),
        "grade": context.step_data.get("job_grade", "L3"),
        "estimated_ctc": context.step_data.get("estimated_ctc", 1800000),
    }
    cohort = context.step_data.get("cohort") or [candidate_id]
    interview = context.step_data.get("hr_interview") or {
        "interview_id": candidate_id,
        "scheduled_at": context.metadata.get("hr_scheduled_at", "2026-08-02T15:00:00+05:30"),
        "interviewer": context.step_data.get("hr_interviewer", "HR Panel"),
        "mode": context.step_data.get("interview_mode") or "online",
        "meeting_link": context.step_data.get("meeting_link") or "https://meet.example.com/hr",
        "link_source": "agent_generated",
    }

    return {
        "trace_id": context.workflow_id,
        "idempotency_key": idem,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "round_number": 2,
        "round_type": "HR",
        "context": {
            "candidate": {"id": candidate_id, "name": candidate.name, "email": candidate.email, "status": "Interview"},
            "job": {"id": job_id, "title": candidate.job_title, "department": context.step_data.get("job_department", "Engineering")},
            "requisition": requisition,
            "prior_rounds": [],
            "cohort": cohort,
            "interview": interview,
            "positions_available": requisition.get("count", 1),
        },
        "human_decisions": human_decisions or {
            "weights": {"technical": 0.60, "hr": 0.40}, "evaluation": {}, "final_decision": None,
        },
        "constraints": {"max_retries": 3, "timeout_ms": 30000, "dry_run": False},
    }


class HRInterviewAgent(Agent):
    """
    Agent 8: HR Interview & Candidate Re-ranking.
    Wires the real three-turn implementation (agents/agent8/core.py) into
    Pipeline-2's run(context) -> AgentResponse contract. Which turn executes
    is determined by context.current_state, since the master graph dispatches
    Agent 8 once per turn from a distinct state (see agents/master/router.py).
    """

    def run(self, context: WorkflowContext) -> AgentResponse:
        workflow_logger.info("Executing Agent 8 - HR Evaluator & Pool Re-ranking...", trace_id=context.workflow_id)
        try:
            if context.current_state == STATE_HR_RANKING_PENDING:
                return self._run_turn2(context)
            if context.current_state == STATE_HR_INTERVIEW_COMPLETED:
                return self._run_turn3(context)
            # STATE_HR_INTERVIEW_PENDING, and any other/unexpected state, runs Turn 1.
            return self._run_turn1(context)
        except AgentError as e:
            workflow_logger.logger.error(f"Agent 8 validation failure: {e.code.value} - {e.message}")
            return AgentResponse(
                execution_status="FAILED",
                summary=f"Agent 8 execution failed: {e.message}",
                errors=[f"{e.code.value}: {e.message}"],
                metadata={"agent_name": "agent8", "error_code": e.code.value, "retryable": e.retryable},
            )
        except Exception as e:
            workflow_logger.logger.error(f"Agent 8 unexpected failure: {str(e)}")
            return AgentResponse(
                execution_status="FAILED",
                summary="Unexpected exception inside Agent 8.",
                errors=[str(e)],
                metadata={"agent_name": "agent8"},
            )

    # ---------------------------------------------------------------- Turn 1
    def _run_turn1(self, context: WorkflowContext) -> AgentResponse:
        candidate = context.candidate
        candidate_id = to_internal_id("candidate", candidate.candidate_id)
        job_id = to_internal_id("job", candidate.job_id)
        seed_candidate_demo_data(
            candidate_id, job_id,
            technical_score=_derive_technical_score(context),
            applied_at=context.metadata.get("applied_at", "2026-01-01"),
        )

        envelope = _build_envelope(context)
        result = agent8_core.turn1_pre_round(envelope)

        context.step_data["hr_evaluation_form_url"] = result["data"]["evaluation_form_url"]
        context.step_data["hr_candidate_profile"] = result["data"]["profile"]

        return AgentResponse(
            execution_status="SUCCESS",
            generated_event=EVENT_HR_EVALUATION_REQUESTED,
            updated_state=STATE_HR_EVALUATION_AWAITED,
            summary=f"HR evaluation form generated for {candidate.name}; awaiting HR submission.",
            metadata={
                "agent_name": "agent8",
                "turn": 1,
                "evaluation_form_url": result["data"]["evaluation_form_url"],
                "human_escalation": result["human_escalation"],
            },
        )

    # ---------------------------------------------------------------- Turn 2
    def _run_turn2(self, context: WorkflowContext) -> AgentResponse:
        candidate = context.candidate
        evaluation = context.step_data.get("hr_evaluation", {})
        weights = context.step_data.get("hr_weights", {"technical": 0.60, "hr": 0.40})

        envelope = _build_envelope(context, human_decisions={
            "weights": weights, "evaluation": evaluation, "final_decision": None,
        })
        result = agent8_core.turn2_compute_and_rank(envelope)

        ranking_preview = result["human_escalation"]["ranking_preview"]
        context.step_data["hr_ranking_preview"] = ranking_preview
        context.step_data["hr_rationale"] = result["data"]["rationale"]
        context.step_data["hr_confidence"] = result["confidence"]
        context.step_data["hr_warnings"] = result["warnings"]

        return AgentResponse(
            execution_status="SUCCESS",
            generated_event=EVENT_HR_SCORE_SUBMITTED,
            updated_state=STATE_CANDIDATE_RANKING_AWAITED,
            summary=f"HR score computed and cohort ranked for {candidate.name}; awaiting hiring manager approval.",
            warnings=[w.get("message", "") for w in result["warnings"]],
            metadata={
                "agent_name": "agent8",
                "turn": 2,
                "ranking_preview": ranking_preview,
                "confidence": result["confidence"],
                "rationale": result["data"]["rationale"],
            },
        )

    # ---------------------------------------------------------------- Turn 3
    def _run_turn3(self, context: WorkflowContext) -> AgentResponse:
        candidate = context.candidate
        final_decision = context.step_data.get("hr_final_decision", {})

        envelope = _build_envelope(context, human_decisions={
            "weights": context.step_data.get("hr_weights", {"technical": 0.60, "hr": 0.40}),
            "evaluation": context.step_data.get("hr_evaluation", {}),
            "final_decision": final_decision,
        })
        idem = envelope["idempotency_key"]

        snapshot = db.read("turn2_snapshots", {"idempotency_key": idem})
        if not snapshot:
            raise AgentError(ErrorCode.RANKING_SNAPSHOT_MISSING,
                              "No Turn 2 ranking snapshot found for this workflow.")
        ranked = agent8_core._deserialize_ranked(snapshot[0]["ranked"])

        result = agent8_core.turn3_persist(envelope, ranked)

        context.step_data["hr_final_rank"] = result["data"]["final_rank"]
        context.step_data["hr_final_score"] = result["data"]["final_score"]
        context.step_data["hr_recommendation"] = result["data"]["recommendation"]

        return AgentResponse(
            execution_status="SUCCESS",
            generated_event=EVENT_CANDIDATE_RANKED,
            updated_state=STATE_HR_INTERVIEW_COMPLETED,
            summary=(
                f"HR outcome persisted for {candidate.name}: "
                f"rank #{result['data']['final_rank']}, recommendation {result['data']['recommendation']}."
            ),
            metadata={
                "agent_name": "agent8",
                "turn": 3,
                "final_rank": result["data"]["final_rank"],
                "final_score": result["data"]["final_score"],
                "recommendation": result["data"]["recommendation"],
                "handoff": result["handoff"],
            },
        )
