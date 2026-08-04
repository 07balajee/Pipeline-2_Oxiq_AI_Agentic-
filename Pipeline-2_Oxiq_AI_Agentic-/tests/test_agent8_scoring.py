"""Reproduces the worked example from §14 of the Agent 8 prompt spec and pins
the formula exactly - if this test ever fails after a code change, the change
broke reproducibility, which §16.14 explicitly forbids. Ported unchanged
(besides import paths) from agent8_hr_interview_ranking/tests/test_scoring.py."""
from decimal import Decimal
from agents.agent8 import scoring


def test_hr_score_matches_worked_example():
    # comm=4, culture=5, behaviour=4, motivation=4 -> weighted=4.30 -> 82.5 -> 83
    score = scoring.compute_hr_score(
        communication_rating=4, culture_fit_rating=5, behaviour_rating=4,
        motivation_rating=4, leadership_rating=None, is_leadership_track=False,
    )
    assert score == 83


def test_round_half_up_not_banker():
    # 82.5 must round to 83, never 82 (Python's round() would give 82)
    score = scoring.compute_hr_score(
        communication_rating=4, culture_fit_rating=5, behaviour_rating=4,
        motivation_rating=4, leadership_rating=None, is_leadership_track=False,
    )
    assert score == 83
    assert round(82.5) == 82  # documents WHY we don't use built-in round()


def test_final_score_matches_worked_example():
    weights = {"technical": 0.60, "hr": 0.40}
    assert scoring.compute_final_score(85, 83, weights) == Decimal("84.2")
    assert scoring.compute_final_score(74, 88, weights) == Decimal("79.6")
    assert scoring.compute_final_score(78, 62, weights) == Decimal("71.6")


def test_ranking_matches_worked_example():
    weights = {"technical": 0.60, "hr": 0.40}
    candidates = [
        scoring.CandidateScore(101, 85, 83, scoring.compute_final_score(85, 83, weights)),
        scoring.CandidateScore(102, 78, 62, scoring.compute_final_score(78, 62, weights)),
        scoring.CandidateScore(103, 74, 88, scoring.compute_final_score(74, 88, weights)),
    ]
    ranked, ties = scoring.rank_cohort(candidates)
    assert ties == []
    assert [c.candidate_id for c in ranked] == [101, 103, 102]
    assert [c.rank for c in ranked] == [1, 2, 3]


def test_recommendation_bands():
    assert scoring.recommend(1, Decimal("84.2"), 2, 85, 83) == "Selected"
    assert scoring.recommend(3, Decimal("71.6"), 2, 78, 62) == "Waitlist"
    assert scoring.recommend(5, Decimal("55.0"), 2, 60, 50) == "Rejected"
    assert scoring.recommend(1, Decimal("75.0"), 2, 39, 90) == "Rejected"  # sub-40 hard floor


def test_weights_must_sum_to_one():
    import pytest
    with pytest.raises(ValueError):
        scoring.compute_final_score(85, 83, {"technical": 0.5, "hr": 0.4})


def test_out_of_range_rating_rejected():
    import pytest
    with pytest.raises(ValueError):
        scoring.compute_hr_score(6, 5, 4, 4, None, False)
