"""Ported unchanged (besides import paths) from
agent8_hr_interview_ranking/tests/test_validation.py."""
import pytest
from agents.agent8 import validation
from agents.agent8.errors import AgentError, ErrorCode


def test_missing_technical_score_blocks():
    with pytest.raises(AgentError) as e:
        validation.validate_pre_round(
            candidate={"status": "Interview"}, interviews=[{"round": "HR", "status": "Scheduled"}],
            technical_scores=[],
        )
    assert e.value.code == ErrorCode.TECHNICAL_SCORE_MISSING


def test_policy_block_stops_persist():
    with pytest.raises(AgentError) as e:
        validation.validate_pre_persist(policy_allowed=False, selected_count=1,
                                         positions_available=2, overselection_override=False)
    assert e.value.code == ErrorCode.POLICY_VIOLATION


def test_overselection_blocked_without_override():
    with pytest.raises(AgentError) as e:
        validation.validate_pre_persist(policy_allowed=True, selected_count=3,
                                         positions_available=2, overselection_override=False)
    assert e.value.code == ErrorCode.OVERSELECTION


def test_overselection_allowed_with_override():
    validation.validate_pre_persist(policy_allowed=True, selected_count=3,
                                     positions_available=2, overselection_override=True)


def test_missing_ranking_snapshot_blocks_persist():
    with pytest.raises(AgentError) as e:
        validation.validate_ranking_snapshot_current(None, {})
    assert e.value.code == ErrorCode.RANKING_SNAPSHOT_MISSING


def test_unchanged_cohort_passes():
    snapshot_ranked = [
        {"candidate_id": 101, "technical_score": 85, "hr_score": 83, "status": "Interview"},
        {"candidate_id": 102, "technical_score": 78, "hr_score": 62, "status": "Interview"},
    ]
    current = {
        101: {"technical_score": 85, "hr_score": 83, "status": "Interview"},
        102: {"technical_score": 78, "hr_score": 62, "status": "Interview"},
    }
    validation.validate_ranking_snapshot_current(snapshot_ranked, current)


def test_score_drift_blocks_persist():
    snapshot_ranked = [
        {"candidate_id": 101, "technical_score": 85, "hr_score": 83, "status": "Interview"},
        {"candidate_id": 102, "technical_score": 78, "hr_score": 62, "status": "Interview"},
    ]
    current = {
        101: {"technical_score": 85, "hr_score": 83, "status": "Interview"},
        102: {"technical_score": 90, "hr_score": 62, "status": "Interview"},  # technical score changed
    }
    with pytest.raises(AgentError) as e:
        validation.validate_ranking_snapshot_current(snapshot_ranked, current)
    assert e.value.code == ErrorCode.COHORT_DRIFT
    assert e.value.details["drifted_candidates"] == [102]


def test_withdrawn_candidate_blocks_persist():
    snapshot_ranked = [
        {"candidate_id": 101, "technical_score": 85, "hr_score": 83, "status": "Interview"},
        {"candidate_id": 102, "technical_score": 78, "hr_score": 62, "status": "Interview"},
    ]
    current = {
        101: {"technical_score": 85, "hr_score": 83, "status": "Interview"},
        102: {"technical_score": 78, "hr_score": 62, "status": "Withdrawn"},  # candidate withdrew
    }
    with pytest.raises(AgentError) as e:
        validation.validate_ranking_snapshot_current(snapshot_ranked, current)
    assert e.value.code == ErrorCode.COHORT_DRIFT
    assert e.value.details["drifted_candidates"] == [102]
