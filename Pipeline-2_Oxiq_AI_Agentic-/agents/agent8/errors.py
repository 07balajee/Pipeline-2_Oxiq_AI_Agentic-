"""Error codes and the standard error envelope used across Agent 8.

Matches the failure-code vocabulary in §7 (Validation Gate) and §10
(Failure Handling & Fallback) of the prompt spec.
"""
from __future__ import annotations
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    # Validation gate (§7)
    TECHNICAL_SCORE_MISSING = "TECHNICAL_SCORE_MISSING"
    TECHNICAL_ROUND_INCOMPLETE = "TECHNICAL_ROUND_INCOMPLETE"
    INVALID_STATE = "INVALID_STATE"
    HR_INTERVIEW_NOT_SCHEDULED = "HR_INTERVIEW_NOT_SCHEDULED"
    TEMPLATE_MISSING = "TEMPLATE_MISSING"
    CANDIDATE_NO_SHOW = "CANDIDATE_NO_SHOW"
    INTERVIEWER_NO_SHOW = "INTERVIEWER_NO_SHOW"
    SCORE_MISSING = "SCORE_MISSING"
    SCORE_OUT_OF_RANGE = "SCORE_OUT_OF_RANGE"
    EVALUATOR_MISSING = "EVALUATOR_MISSING"
    DUPLICATE_SCORE = "DUPLICATE_SCORE"
    MISSING_COHORT = "MISSING_COHORT"
    COHORT_INCOMPLETE = "COHORT_INCOMPLETE"
    WEIGHTS_INCONSISTENT = "WEIGHTS_INCONSISTENT"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    OVERSELECTION = "OVERSELECTION"
    RANKING_SNAPSHOT_MISSING = "RANKING_SNAPSHOT_MISSING"
    COHORT_DRIFT = "COHORT_DRIFT"

    # Failure handling (§10)
    ANALYTICS_DEGRADED = "ANALYTICS_DEGRADED"
    ANALYTICS_MISMATCH = "ANALYTICS_MISMATCH"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    TRANSCRIPT_UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    POLICY_UNVERIFIED = "POLICY_UNVERIFIED"
    BAND_MISMATCH = "BAND_MISMATCH"
    CUT_LINE_TIE = "CUT_LINE_TIE"
    PARTIAL_RANK = "PARTIAL_RANK"
    NOTIFICATION_FAILED = "NOTIFICATION_FAILED"
    DB_TIMEOUT = "DB_TIMEOUT"
    SCHEMA_GAP = "SCHEMA_GAP"
    PARTIAL_PERSIST = "PARTIAL_PERSIST"
    LINK_UNVALIDATED = "LINK_UNVALIDATED"


class AgentError(Exception):
    """Raised for any condition that must stop the workflow and return
    a structured error rather than proceed. Never caught-and-guessed past."""

    def __init__(self, code: ErrorCode, message: str, retryable: bool = False,
                 details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        super().__init__(f"{code.value}: {message}")

    def to_envelope(self) -> dict[str, Any]:
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }
