"""Validation Gate — §7 of the prompt spec, split across the two turns
it actually applies to (checks 1-6 before the round, 7-14 before ranking)."""
from __future__ import annotations
from .errors import AgentError, ErrorCode


def validate_pre_round(candidate: dict, interviews: list[dict], technical_scores: list[dict]) -> None:
    """§7 checks 1-6, run in Turn 1."""
    if not any(s.get("round") == "Technical" for s in technical_scores):
        raise AgentError(ErrorCode.TECHNICAL_SCORE_MISSING,
                          "No Technical round score exists for this candidate.")

    technical_interview = next((i for i in interviews if i.get("round") == "Technical"), None)
    if not technical_interview or technical_interview.get("status") != "Completed":
        raise AgentError(ErrorCode.TECHNICAL_ROUND_INCOMPLETE,
                          "Technical interview is not marked Completed.")

    if candidate.get("status") != "Interview":
        raise AgentError(ErrorCode.INVALID_STATE,
                          f"candidates.status is '{candidate.get('status')}', expected 'Interview'.")

    hr_interview = next((i for i in interviews if i.get("round") == "HR"), None)
    if not hr_interview or hr_interview.get("status") != "Scheduled":
        raise AgentError(ErrorCode.HR_INTERVIEW_NOT_SCHEDULED,
                          "No HR interview row exists in 'Scheduled' status.")


def validate_pre_rank(
    evaluation: dict,
    cohort_technical_scores: dict[int, float | None],
    weights_used_elsewhere: dict | None,
    weights: dict,
    existing_hr_score: dict | None,
) -> None:
    """§7 checks 7-12, run in Turn 2."""
    required = ["communication_rating", "culture_fit_rating", "behaviour_rating", "evaluator"]
    for field in required:
        if evaluation.get(field) in (None, ""):
            raise AgentError(ErrorCode.SCORE_MISSING if field != "evaluator" else ErrorCode.EVALUATOR_MISSING,
                              f"Missing required field: {field}")

    for field in ["communication_rating", "culture_fit_rating", "behaviour_rating"]:
        v = evaluation[field]
        if not (1 <= v <= 5):
            raise AgentError(ErrorCode.SCORE_OUT_OF_RANGE, f"{field}={v} out of range 1-5")

    if existing_hr_score is not None:
        raise AgentError(ErrorCode.DUPLICATE_SCORE,
                          "An interview_scores row with round='HR' already exists for this candidate/round.")

    if not cohort_technical_scores:
        raise AgentError(ErrorCode.MISSING_COHORT, "context.cohort is empty or missing.")
    incomplete = [cid for cid, score in cohort_technical_scores.items() if score is None]
    if incomplete:
        raise AgentError(ErrorCode.COHORT_INCOMPLETE,
                          f"Cohort members missing a Technical score: {incomplete}")

    if weights_used_elsewhere is not None and weights_used_elsewhere != weights:
        raise AgentError(ErrorCode.WEIGHTS_INCONSISTENT,
                          f"weights {weights} differ from {weights_used_elsewhere} used elsewhere in this job.")


def validate_pre_persist(policy_allowed: bool, selected_count: int, positions_available: int,
                          overselection_override: bool) -> None:
    """§7 checks 13-14, run at the top of Turn 3."""
    if not policy_allowed:
        raise AgentError(ErrorCode.POLICY_VIOLATION,
                          "Company Policy MCP did not return allowed=true.", retryable=False)
    if selected_count > positions_available and not overselection_override:
        raise AgentError(ErrorCode.OVERSELECTION,
                          f"Selected count {selected_count} exceeds positions_available {positions_available} "
                          f"with no logged human override.")


def validate_ranking_snapshot_current(snapshot_ranked: list[dict] | None,
                                       current_by_candidate: dict[int, dict]) -> None:
    """§8.3 reproducibility guard, run at the top of Turn 3. The ranking a
    human approved in Turn 2 must be exactly what gets persisted - if the
    Turn 2 snapshot is missing, or if any cohort member's technical/HR score
    or status has changed underneath it (candidate withdrew, a new score
    landed) while the approval was pending, refuse to persist. The fix is a
    fresh Turn 2, never a silent recompute-and-hope."""
    if not snapshot_ranked:
        raise AgentError(ErrorCode.RANKING_SNAPSHOT_MISSING,
                          "No approved Turn 2 ranking snapshot found for this idempotency_key.",
                          retryable=False)

    drifted = []
    for row in snapshot_ranked:
        cid = row["candidate_id"]
        now = current_by_candidate.get(cid)
        if (now is None
                or now["technical_score"] != row["technical_score"]
                or now["hr_score"] != row["hr_score"]
                or now["status"] != row["status"]):
            drifted.append(cid)
    if drifted:
        raise AgentError(ErrorCode.COHORT_DRIFT,
                          f"Cohort data changed since the Turn 2 ranking was approved: candidates {drifted}. "
                          "Re-run Turn 2 to produce a fresh, human-approved ranking before persisting.",
                          retryable=False, details={"drifted_candidates": drifted})
