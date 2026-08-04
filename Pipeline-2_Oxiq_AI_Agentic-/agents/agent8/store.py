"""Module-level singleton wiring Agent 8's core against its (mocked) MCPs.

Mirrors the singleton pattern already used by shared/registry/agent_registry.py
and agents/master/state_manager.py: the Dispatcher instantiates a fresh
HRInterviewAgent() on every dispatch, so state that must survive across Turn
1 -> Turn 2 -> Turn 3 (which are separate dispatches, possibly hours apart
while a human fills a form or reviews a ranking) has to live here rather than
on the agent instance.

All MCPs except the LLM rationale drafter are in-memory mocks, same "mocked
for now" posture as the rest of Pipeline-2 (see shared/config/settings.py).
"""
from __future__ import annotations

from .core import Agent8
from .mcp.mocks import (
    MockDatabaseMCP, MockAnalyticsMCP, MockPolicyMCP, MockSalaryBandMCP,
    MockResumeMCP, MockDocumentMCP, MockNotificationMCP, MockMeetMCP,
)
from .mcp.llm_mcp import StubLLMRationaleMCP

db = MockDatabaseMCP()
analytics = MockAnalyticsMCP(always_degraded=True)
policy = MockPolicyMCP(allowed=True)
salary_band = MockSalaryBandMCP()
resume = MockResumeMCP()
document = MockDocumentMCP()
notification = MockNotificationMCP()
meet = MockMeetMCP()
llm = StubLLMRationaleMCP()

agent8_core = Agent8(
    db=db, analytics=analytics, policy=policy, salary_band=salary_band,
    resume=resume, document=document, notification=notification, meet=meet,
    llm=llm,
)

_id_counters: dict[str, int] = {}
_id_map: dict[tuple, int] = {}


def to_internal_id(namespace: str, external_id: str) -> int:
    """Agent 8's core operates on integer candidate_id/job_id (its spec's DB
    schema); Pipeline-2's CandidateContext carries opaque string ids
    (e.g. "CAND-001"). Assigns and remembers a stable int per (namespace,
    external_id) pair for the lifetime of this process."""
    key = (namespace, str(external_id))
    if key not in _id_map:
        _id_counters[namespace] = _id_counters.get(namespace, 0) + 1
        _id_map[key] = _id_counters[namespace]
    return _id_map[key]


def seed_candidate_demo_data(candidate_id: int, job_id: int, technical_score: float,
                              applied_at: str) -> None:
    """Best-effort demo seeding so a single-candidate Pipeline-2 run has enough
    rows for Agent 8's validation gate to pass, without a real Pipeline-1/
    Agent-6/Agent-7 database behind it yet. No-ops for fields already present
    (idempotent across repeated Turn 1 dispatches / retries)."""
    existing_candidates = db.read("candidates", {"id": candidate_id})
    if not existing_candidates:
        db.tables["candidates"].append({
            "id": candidate_id, "status": "Interview", "applied_at": applied_at,
        })

    existing_interviews = db.read("interviews", {"candidate_id": candidate_id})
    has_technical = any(i.get("round") == "Technical" for i in existing_interviews)
    has_hr = any(i.get("round") == "HR" for i in existing_interviews)
    if not has_technical:
        db.tables["interviews"].append({
            "candidate_id": candidate_id, "round": "Technical", "status": "Completed",
        })
    if not has_hr:
        db.tables["interviews"].append({
            "candidate_id": candidate_id, "round": "HR", "status": "Scheduled",
            "interview_id": candidate_id,
        })

    existing_technical_scores = db.read(
        "interview_scores", {"candidate_id": candidate_id, "round": "Technical"}
    )
    if not existing_technical_scores:
        db.tables["interview_scores"].append({
            "candidate_id": candidate_id, "round": "Technical", "score": technical_score,
        })
