"""Envelope schemas for Agent 8 - Universal Request Envelope (§4) and Response
Envelope (§13) of the prompt spec. Ported unchanged from the standalone
agent8_hr_interview_ranking reference implementation.

Documentation of the contract only: agents/agent8/core.py and agent.py work
with plain dicts rather than these models directly, matching the standalone
implementation's own behavior (see its CLAUDE.md: "not yet enforced at the
Agent8 boundary")."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any


# ---------------------------------------------------------------- Request (§4)
class CandidateRef(BaseModel):
    id: int
    name: str
    email: str
    status: str


class JobRef(BaseModel):
    id: int
    title: str
    department: str


class RequisitionRef(BaseModel):
    id: str
    count: int
    grade: str
    estimated_ctc: float


class PriorRound(BaseModel):
    round: str
    score: float
    evaluator: str
    evaluated_at: str


class InterviewRef(BaseModel):
    interview_id: int
    scheduled_at: str
    interviewer: str
    mode: str
    meeting_link: str | None = None
    link_source: str  # "host_supplied" | "agent_generated"


class Context(BaseModel):
    candidate: CandidateRef
    job: JobRef
    requisition: RequisitionRef
    prior_rounds: list[PriorRound]
    cohort: list[int]
    interview: InterviewRef
    positions_available: int


class Attendance(BaseModel):
    candidate_joined: bool | None = None
    interviewer_joined: bool | None = None


class Evaluation(BaseModel):
    communication_rating: int | None = None
    behaviour_rating: int | None = None
    culture_fit_rating: int | None = None
    leadership_rating: int | None = None
    motivation_rating: int | None = None
    overall_comments: str | None = None
    evaluator: str | None = None
    attendance: Attendance = Field(default_factory=Attendance)


class HumanDecisions(BaseModel):
    scale_confirmed: bool = False
    weights: dict = Field(default_factory=lambda: {"technical": 0.60, "hr": 0.40})
    evaluation: Evaluation = Field(default_factory=Evaluation)
    final_decision: dict | None = None
    additional_round_requested: bool | None = None


class Constraints(BaseModel):
    max_retries: int = 3
    timeout_ms: int = 30000
    dry_run: bool = False


class RequestEnvelope(BaseModel):
    trace_id: str
    idempotency_key: str
    candidate_id: int
    job_id: int
    round_number: int
    round_type: str = "HR"
    context: Context
    human_decisions: HumanDecisions = Field(default_factory=HumanDecisions)
    constraints: Constraints = Field(default_factory=Constraints)


# --------------------------------------------------------------- Response (§13)
class Handoff(BaseModel):
    candidate_id: int
    job_id: int
    current_agent: str


class HumanEscalation(BaseModel):
    required: bool
    reason: str | None = None
    question: str | None = None
    options: list[dict] | None = None
    ranking_preview: list[dict] | None = None
    flags: list[str] | None = None


class DbWrite(BaseModel):
    table: str
    op: str
    id: Any
    fields: dict


class McpCall(BaseModel):
    tool: str
    status: str
    latency_ms: int


class Warning(BaseModel):
    code: str
    message: str


class ResponseEnvelope(BaseModel):
    trace_id: str
    agent: str = "Agent8_HRInterviewRanking"
    status: str  # "needs_human" | "success" | "error"
    handoff: Handoff | None = None
    data: dict = Field(default_factory=dict)
    db_writes: list[DbWrite] = Field(default_factory=list)
    mcp_calls: list[McpCall] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    warnings: list[Warning] = Field(default_factory=list)
    human_escalation: HumanEscalation = Field(default_factory=lambda: HumanEscalation(required=False))
    confidence: float = 1.0
    completed_at: str | None = None
