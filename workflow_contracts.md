# Pipeline-2 Workflow Contracts Reference (Phase 5.8 Frozen Baseline)

## State Machine & Routing Specification

```
CandidateShortlisted ──[CandidateShortlisted]──► InterviewScheduling (Agent 6)
                                                        │
InterviewScheduled ◄──────────[InterviewCreated]────────┘
       │
       ├──[InterviewStarted]──► TechnicalInterviewPending (Agent 7)
       │                               │
TechnicalInterviewCompleted ◄──[TechnicalScoreSubmitted]┘
       │
       ├──[TriggerHRRound]──► HRInterviewPending (Agent 8)
       │                              │
HRInterviewCompleted ◄────────[HRScoreSubmitted]────────┘
```

---

## Idempotency Tokens

- **Agent 6**: `context.step_data["interview_scheduled_committed"]`
- **Agent 7**: `context.step_data["technical_scores_committed"]`
- **Agent 8**: `context.step_data["hr_scores_committed"]`

---

## Failure Category & Transport Mapping

| Failure Type | Error Category | Behavior |
|--------------|----------------|----------|
| Worker connection failure / service down | `CONNECTION_ERROR` | Master catches `AgentTransportError`, logs error, increments workflow retry counter, pauses if retries exhausted. |
| HTTP request timeout | `TIMEOUT` | Master catches `AgentTransportError`, initiates bounded operational retry. |
| Worker HTTP 500 | `HTTP_SERVICE_ERROR` | Master logs HTTP error status and initiates retry/fallback. |
| Malformed response | `INVALID_RESPONSE` | Master catches parsing error, triggers retry or pause. |
| Schema validation failure | `CONTRACT_ERROR` | Master invalidates worker response, increments retry counter. |
| Worker business execution failure | `execution_status="FAILED"` | Worker returns HTTP 200 with error details; Master evaluates fallback/pause policy. |
