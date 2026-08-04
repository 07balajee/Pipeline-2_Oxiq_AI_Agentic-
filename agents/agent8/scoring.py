"""Deterministic scoring, consolidation, and ranking — §8 of the prompt spec.

FIX #1 FROM REVIEW: this entire module is pure, deterministic arithmetic.
No LLM call happens anywhere in this file. The exact rounding mode
(ROUND_HALF_UP, not Python's default banker's rounding) is used exactly as
the spec requires: 82.5 -> 83, never 82. This module is what "compute locally"
in the prompt's MCP fallback table actually means — a code path, not the
model doing arithmetic in its own reasoning.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

# --- §8.1 HR composite weights ---
WEIGHT_COMMUNICATION = Decimal("0.35")
WEIGHT_CULTURE_FIT = Decimal("0.30")
WEIGHT_BEHAVIOUR = Decimal("0.20")
WEIGHT_MOTIVATION_OR_LEADERSHIP = Decimal("0.15")

# §16.9 — ratings/scores must never be influenced by these; kept here only
# as a constant list other modules (e.g. a future LLM-output scanner) can
# check rationale text against.
PROTECTED_ATTRIBUTES = (
    "age", "gender", "caste", "religion", "marital status",
    "nationality", "disability", "pregnancy", "health",
)


def _round_half_up(value: Decimal, decimals: int) -> Decimal:
    quant = Decimal(1).scaleb(-decimals)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def compute_hr_score(
    communication_rating: int,
    culture_fit_rating: int,
    behaviour_rating: int,
    motivation_rating: int | None,
    leadership_rating: int | None,
    is_leadership_track: bool,
) -> int:
    """§8.1 — HR composite. Ratings are 1-5 integers; output is an integer 0-100."""
    for name, r in [
        ("communication_rating", communication_rating),
        ("culture_fit_rating", culture_fit_rating),
        ("behaviour_rating", behaviour_rating),
    ]:
        if not (1 <= r <= 5):
            raise ValueError(f"{name}={r} out of range 1-5")

    fourth = leadership_rating if is_leadership_track else motivation_rating
    if fourth is None:
        raise ValueError(
            "leadership_rating required for leadership-track grades, "
            "otherwise motivation_rating is required"
        )
    if not (1 <= fourth <= 5):
        raise ValueError(f"fourth rating={fourth} out of range 1-5")

    weighted = (
        WEIGHT_COMMUNICATION * Decimal(communication_rating)
        + WEIGHT_CULTURE_FIT * Decimal(culture_fit_rating)
        + WEIGHT_BEHAVIOUR * Decimal(behaviour_rating)
        + WEIGHT_MOTIVATION_OR_LEADERSHIP * Decimal(fourth)
    )
    normalized = (weighted - 1) / Decimal(4) * 100
    return int(_round_half_up(normalized, 0))


def compute_sub_score(rating: int) -> int:
    """comm_score / culture_score written to candidate_details — same 1-5 -> 0-100 scale."""
    if not (1 <= rating <= 5):
        raise ValueError(f"rating={rating} out of range 1-5")
    return int(_round_half_up((Decimal(rating) - 1) / Decimal(4) * 100, 0))


def compute_final_score(technical_score: float, hr_score: int, weights: dict) -> Decimal:
    """§8.2 — consolidated final score. Kept to ONE decimal place, never
    rounded to an integer — ranking precision depends on it."""
    tech_w = Decimal(str(weights["technical"]))
    hr_w = Decimal(str(weights["hr"]))
    if tech_w + hr_w != Decimal("1"):
        raise ValueError(f"weights must sum to 1.0, got {tech_w + hr_w}")
    final = tech_w * Decimal(str(technical_score)) + hr_w * Decimal(str(hr_score))
    return _round_half_up(final, 1)


@dataclass
class CandidateScore:
    candidate_id: int
    technical_score: float
    hr_score: int
    final_score: Decimal
    screening_score: float = 0.0
    applied_at: str = ""  # ISO8601, earlier sorts first as a tie-break
    rank: int | None = field(default=None)
    recommendation: str | None = field(default=None)


def rank_cohort(candidates: list[CandidateScore]) -> tuple[list[CandidateScore], list[list[int]]]:
    """§8.3 — sort desc by final_score; tie-break: technical -> hr -> screening -> applied_at.
    Ranks are dense and gapless starting at 1. Returns (ranked_list, unresolved_ties)
    where unresolved_ties is a list of candidate_id groups still tied after all
    four tie-breakers — the caller MUST escalate these, never coin-flip."""

    def sort_key(c: CandidateScore):
        return (-c.final_score, -c.technical_score, -c.hr_score, -c.screening_score, c.applied_at)

    ordered = sorted(candidates, key=sort_key)
    for i, c in enumerate(ordered):
        c.rank = i + 1

    unresolved_ties: list[list[int]] = []
    i = 0
    while i < len(ordered) - 1:
        a, b = ordered[i], ordered[i + 1]
        if (
            a.final_score == b.final_score
            and a.technical_score == b.technical_score
            and a.hr_score == b.hr_score
            and a.screening_score == b.screening_score
            and a.applied_at == b.applied_at
        ):
            unresolved_ties.append([a.candidate_id, b.candidate_id])
        i += 1

    return ordered, unresolved_ties


def recommend(
    rank: int,
    final_score: Decimal,
    positions_available: int,
    technical_score: float,
    hr_score: int,
) -> str:
    """§8.4 — recommendation bands. A recommendation, never an action."""
    if technical_score < 40 or hr_score < 40:
        return "Rejected"
    if final_score < 60:
        return "Rejected"
    if rank <= positions_available and final_score >= 70:
        return "Selected"
    return "Waitlist"


def detect_anomalies(ranked: list[CandidateScore], positions_available: int) -> list[dict]:
    """§8.4 anomaly flags — surfaced, never auto-corrected."""
    flags: list[dict] = []

    for c in ranked:
        if abs(c.technical_score - c.hr_score) > 40:
            flags.append({"code": "ROUND_DIVERGENCE", "candidate_id": c.candidate_id})

    if len(ranked) > positions_available >= 1:
        at_cut = ranked[positions_available - 1]
        past_cut = ranked[positions_available]
        if abs(float(at_cut.final_score) - float(past_cut.final_score)) <= 2:
            flags.append({
                "code": "CUT_LINE_TIE",
                "candidates": [at_cut.candidate_id, past_cut.candidate_id],
            })

    selected_count = sum(1 for c in ranked if c.recommendation == "Selected")
    if selected_count < positions_available:
        flags.append({"code": "INSUFFICIENT_POOL", "selected": selected_count,
                       "positions_available": positions_available})

    if ranked:
        scores = [float(c.final_score) for c in ranked]
        if (max(scores) - min(scores)) < 10:
            flags.append({"code": "COMPRESSED_DISTRIBUTION", "range": max(scores) - min(scores)})

    return flags
