"""Ported unchanged (besides import paths) from
agent8_hr_interview_ranking/tests/test_confidence.py."""
from agents.agent8 import confidence


def test_no_flags_full_confidence():
    assert confidence.compute_confidence([], []) == 1.0


def test_cut_line_tie_reduces_confidence():
    # CUT_LINE_TIE alone (-0.25) lands at 0.75 - below full confidence but
    # NOT below the 0.70 escalation threshold on its own. Per §11 of the
    # spec, CUT_LINE_TIE is ALSO its own separate automatic escalation
    # trigger regardless of the confidence number - that trigger is the
    # agent workflow's job to check directly against the anomaly flags,
    # not something this function needs to encode redundantly.
    flags = [{"code": "CUT_LINE_TIE", "candidates": [101, 102]}]
    c = confidence.compute_confidence(flags, [])
    assert c == 0.75
    assert confidence.requires_escalation(c) is False


def test_unresolved_tie_forces_zero():
    c = confidence.compute_confidence([], [[101, 102]])
    assert c == 0.0
    assert confidence.requires_escalation(c) is True


def test_round_divergence_caps_deduction():
    flags = [{"code": "ROUND_DIVERGENCE", "candidate_id": i} for i in range(10)]
    c = confidence.compute_confidence(flags, [])
    assert c == 0.70  # 1.0 - min(10*0.15, 0.30) = 0.70, capped not -0.5
