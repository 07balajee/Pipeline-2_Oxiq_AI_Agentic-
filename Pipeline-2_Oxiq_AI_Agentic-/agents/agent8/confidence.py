"""Grounded confidence scoring.

FIX #2 FROM REVIEW: the prompt spec uses `confidence < 0.70` as a hard
escalation trigger (§11) but never defines what the number measures. Rather
than an LLM self-reported confidence (soft, inconsistent, hard to audit),
this derives confidence from the SAME anomaly flags scoring.py already
computes deterministically. Every deduction is documented and reproducible —
identical inputs always yield the identical confidence value.
"""
from __future__ import annotations

BASE_CONFIDENCE = 1.0

# Each present flag reduces confidence by a fixed, documented amount.
# Deductions are additive and clamped to [0.0, 1.0].
DEDUCTIONS = {
    "CUT_LINE_TIE": 0.25,
    "ROUND_DIVERGENCE": 0.15,     # per occurrence, capped below
    "COMPRESSED_DISTRIBUTION": 0.20,
    "INSUFFICIENT_POOL": 0.10,
}
MAX_ROUND_DIVERGENCE_DEDUCTION = 0.30  # cap even if many candidates diverge


def compute_confidence(anomaly_flags: list[dict], unresolved_ties: list[list[int]]) -> float:
    """Returns a value in [0.0, 1.0]. Anything below 0.70 should trigger the
    automatic escalation defined in §11 of the prompt spec."""
    confidence = BASE_CONFIDENCE
    divergence_deduction = 0.0

    for flag in anomaly_flags:
        code = flag.get("code")
        if code == "ROUND_DIVERGENCE":
            divergence_deduction = min(
                divergence_deduction + DEDUCTIONS["ROUND_DIVERGENCE"],
                MAX_ROUND_DIVERGENCE_DEDUCTION,
            )
        elif code in DEDUCTIONS:
            confidence -= DEDUCTIONS[code]

    confidence -= divergence_deduction

    # An unresolved tie after all four tie-breakers is a hard-stop condition,
    # not a partial deduction — the workflow must escalate regardless.
    if unresolved_ties:
        confidence = min(confidence, 0.0)

    return max(0.0, min(1.0, round(confidence, 2)))


def requires_escalation(confidence: float, threshold: float = 0.70) -> bool:
    return confidence < threshold
