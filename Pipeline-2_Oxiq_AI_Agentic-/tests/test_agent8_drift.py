"""End-to-end COHORT_DRIFT guard scenarios (score changes after Turn 2
approval, candidate withdraws after approval, unchanged cohort persists
normally). Ported unchanged (besides import paths - Agent8 lives in
agents/agent8/core.py in Pipeline-2, not agents/agent8/agent.py, which is the
WorkflowContext/AgentResponse adapter) from
agent8_hr_interview_ranking/tests/test_agent_drift.py.

Each test builds its own isolated MockDatabaseMCP/Agent8 instance rather than
using agents/agent8/store.py's shared singleton, so these are unaffected by
other tests' state."""
import pytest

from agents.agent8.core import Agent8
from agents.agent8.errors import AgentError, ErrorCode
from agents.agent8.mcp.mocks import (
    MockDatabaseMCP, MockAnalyticsMCP, MockPolicyMCP, MockSalaryBandMCP,
    MockResumeMCP, MockDocumentMCP, MockNotificationMCP, MockMeetMCP,
)
from agents.agent8.mcp.llm_mcp import StubLLMRationaleMCP


def _build_agent(db):
    return Agent8(
        db=db, analytics=MockAnalyticsMCP(always_degraded=True),
        policy=MockPolicyMCP(allowed=True), salary_band=MockSalaryBandMCP(),
        resume=MockResumeMCP(), document=MockDocumentMCP(),
        notification=MockNotificationMCP(), meet=MockMeetMCP(),
        llm=StubLLMRationaleMCP(),
    )


def _seed_db():
    db = MockDatabaseMCP()
    db.seed("candidates", [
        {"id": 101, "status": "Interview", "applied_at": "2026-06-01"},
        {"id": 102, "status": "Interview", "applied_at": "2026-06-02"},
        {"id": 103, "status": "Interview", "applied_at": "2026-06-03"},
    ])
    db.seed("interviews", [
        {"candidate_id": 101, "round": "Technical", "status": "Completed"},
        {"candidate_id": 101, "round": "HR", "status": "Scheduled", "interview_id": 61},
        {"candidate_id": 102, "round": "Technical", "status": "Completed"},
        {"candidate_id": 103, "round": "Technical", "status": "Completed"},
    ])
    db.seed("interview_scores", [
        {"candidate_id": 101, "round": "Technical", "score": 85},
        {"candidate_id": 102, "round": "Technical", "score": 78},
        {"candidate_id": 102, "round": "HR", "score": 62},
        {"candidate_id": 103, "round": "Technical", "score": 74},
        {"candidate_id": 103, "round": "HR", "score": 88},
    ])
    return db


def _envelope():
    return {
        "trace_id": "tr-drift-test",
        "idempotency_key": "idem-drift-test",
        "candidate_id": 101,
        "job_id": 12,
        "round_number": 2,
        "round_type": "HR",
        "context": {
            "candidate": {"id": 101, "name": "Aarav Mehta", "email": "aarav@example.com", "status": "Interview"},
            "job": {"id": 12, "title": "Backend Engineer", "department": "Engineering"},
            "requisition": {"id": "req-1", "count": 2, "grade": "L3", "estimated_ctc": 1800000},
            "prior_rounds": [],
            "cohort": [101, 102, 103],
            "interview": {"interview_id": 61, "scheduled_at": "2026-08-12T15:00:00+05:30",
                          "interviewer": "H. Khan", "mode": "online",
                          "meeting_link": "https://meet.example.com/abc", "link_source": "host_supplied"},
            "positions_available": 2,
        },
        "human_decisions": {
            "weights": {"technical": 0.60, "hr": 0.40},
            "evaluation": {
                "communication_rating": 4, "behaviour_rating": 4, "culture_fit_rating": 5,
                "motivation_rating": 4, "overall_comments": "Strong communicator.",
                "evaluator": "H. Khan",
            },
            "final_decision": None,
        },
        "constraints": {"max_retries": 3, "timeout_ms": 30000, "dry_run": False},
    }


def test_turn3_blocks_when_cohort_score_changes_after_turn2_approval():
    db = _seed_db()
    agent = _build_agent(db)
    envelope = _envelope()

    t2 = agent.turn2_compute_and_rank(envelope)
    ranked = t2.pop("_internal_ranked")

    # Simulate a new Technical score landing for candidate 103 while HR
    # approval was pending (a day later, per the scenario).
    db.tables["interview_scores"].append(
        {"candidate_id": 103, "round": "Technical", "score": 95, "id": 999}
    )

    envelope["human_decisions"]["final_decision"] = {"approved_by": "hr.manager@example.com"}
    with pytest.raises(AgentError) as e:
        agent.turn3_persist(envelope, ranked)
    assert e.value.code == ErrorCode.COHORT_DRIFT
    assert 103 in e.value.details["drifted_candidates"]

    # Nothing should have been written - the whole point of the guard.
    assert db.read("interview_scores", {"candidate_id": 101, "round": "HR"}) == []
    assert db.read("candidates", {"id": 101})[0]["status"] == "Interview"


def test_turn3_blocks_when_cohort_member_withdraws_after_turn2_approval():
    db = _seed_db()
    agent = _build_agent(db)
    envelope = _envelope()

    t2 = agent.turn2_compute_and_rank(envelope)
    ranked = t2.pop("_internal_ranked")

    for row in db.tables["candidates"]:
        if row["id"] == 102:
            row["status"] = "Withdrawn"

    envelope["human_decisions"]["final_decision"] = {"approved_by": "hr.manager@example.com"}
    with pytest.raises(AgentError) as e:
        agent.turn3_persist(envelope, ranked)
    assert e.value.code == ErrorCode.COHORT_DRIFT
    assert 102 in e.value.details["drifted_candidates"]


def test_turn3_succeeds_when_cohort_unchanged():
    db = _seed_db()
    agent = _build_agent(db)
    envelope = _envelope()

    t2 = agent.turn2_compute_and_rank(envelope)
    ranked = t2.pop("_internal_ranked")

    envelope["human_decisions"]["final_decision"] = {"approved_by": "hr.manager@example.com"}
    t3 = agent.turn3_persist(envelope, ranked)

    assert t3["status"] == "success"
    assert t3["data"]["recommendation"] == "Selected"
    assert db.read("interview_scores", {"candidate_id": 101, "round": "HR"})[0]["score"] == 83
