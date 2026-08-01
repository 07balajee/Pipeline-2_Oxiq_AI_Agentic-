# OxiqAI HRMS - Recruitment Pipeline-2
## AGENT INTERFACE CONTRACTS

---

## 1. Purpose

The **Agent Contract** defines the behavior, responsibilities, boundaries, and interfaces for every AI agent in Pipeline-2. Enforcing this specification:
- **Enables Parallel Development:** Allows developers to implement and test agents independently.
- **Ensures Stable Integration:** Guarantees that agent implementations match expected communication payloads and routing rules.
- **Protects Boundaries:** Prevents agents from performing unauthorized tasks or accessing restricted database tables.
- **Defines Error Budgets:** Standardizes input/output schemas, logging requirements, and failure modes across the system.

---

## 2. Agent Architecture

Pipeline-2 utilizes a hub-and-spoke Master-Worker topology:

```
  ┌────────────────────────────────────────────────────────┐
  │                 Master Orchestrator                    │
  └──────────┬───────────────┬───────────────┬─────────────┘
             │               │               │
             ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │Agent 6  │     │Agent 7  │     │Agent 8  │
        │(Invite) │     │ (Tech)  │     │  (HR)   │
        └─────────┘     └─────────┘     └─────────┘
```

-   **The Master Agent is the sole orchestrator:** Worker agents do not manage state transitions or coordinate other workers.
-   **No Worker Peer Communication:** Worker agents never call or communicate directly with other worker agents.
-   **Centralized Handshake:** All inputs, outputs, and status updates route exclusively through the Master Agent.

---

## 3. Common Rules (Applicable to Every Agent)

All agents (Master, A6, A7, A8) must comply with these guidelines:
-   **Stateless Execution:** Do not store candidate history or pipeline states in memory between execution cycles.
-   **Single Responsibility:** Focus exclusively on the single domain assigned to the agent.
-   **Structured Inputs:** Accept input payloads structured as validated Pydantic models.
-   **Structured Outputs:** Return output payloads structured as validated Pydantic models.
-   **No Direct DB Access:** Use the Database MCP to query or modify data.
-   **No Direct External API Access:** Use the approved Google Workspace and Mail MCP tools for external services.
-   **Return Execution Status:** Every execution must output a status indicator (`SUCCESS` or `FAILED`).
-   **Standardized Error Payload:** Return clear error messages and tracking codes if execution fails.
-   **Audit Logging:** Log execution start, MCP tool invocations, and completion states.

---

## 4. Master Agent Contract

-   **Purpose:** Coordinates candidate progression, evaluates state transitions, and manages pipeline handoffs.
-   **Responsibilities:**
  - Standardizes the intake handshake from Pipeline-1.
  - Formats worker inputs and triggers Agent 6, Agent 7, or Agent 8 based on candidate state.
  - Validates worker outputs before transitioning states.
  - Manages human-in-the-loop approvals.
  - Handles system-wide retries and escalations.
-   **Inputs:** Pipeline-1 triggers, worker output payloads, and human approval events.
-   **Outputs:** Worker task payloads and handoff signals for Pipeline-3.
-   **Allowed MCPs:** Database MCP, Resume MCP, Document MCP, Notification MCP, Policy MCP, Salary Band MCP.
-   **Allowed DB Access:** Read/Write access to `candidates` and `interviews` status flags, read access to scorecards, write access to `transition_logs`.
-   **Events Consumed:** `CandidateShortlisted`, `InterviewCreated`, `TechnicalScoreSubmitted`, `HRScoreSubmitted`, `CandidateRanked`, `WorkflowResumed`.
-   **Events Produced:** `OfferRequested`, `WorkflowPaused`, `WorkflowFailed`, worker task triggers.
-   **Workflow Responsibilities:** Manages the state machine. The Master Agent **must not** perform scoring calculations, schedule interviews, or evaluate transcripts.

---

## 5. Agent 6 Contract (Interview Invitation)

-   **Purpose:** Coordinates and automates the interview scheduling and booking workflow.
-   **Responsibilities:**
  - Identifies availability windows for candidates and interviewers.
  - Generates Google Calendar invites and Google Meet links.
  - Dispatches invitation emails via SMTP mail.
  - Processes reschedule and cancellation requests.
-   **Trigger Event:** Master Agent scheduling dispatch.
-   **Prerequisites:** Candidate state is `Shortlisted` or `RescheduleRequested`.
-   **Expected Input Context:** `candidate_id` and `job_id` (encapsulated in candidate context). Roster details are retrieved dynamically via Database MCP.
-   **Expected Output:** Confirmed scheduled time, calendar event ID, meeting URL, and notification status.
-   **Allowed MCPs:** Database MCP, Google Calendar MCP, Google Meet MCP, SMTP Mail MCP, Analytics MCP.
-   **Allowed DB Operations:** Read access to candidates and jobs, read/write access to `interviews` and `schedule_roster`.
-   **Human-in-the-Loop:** Pauses execution if scheduling conflicts occur or manual slot overrides are requested.
-   **Failure Handling:** If automated booking attempts fail, notifies the recruiter and transitions to the manual scheduling queue.

---

## 6. Agent 7 Contract (Technical Interview)

-   **Purpose:** Processes technical interview transcripts and generates evaluations.
-   **Responsibilities:**
  - Parses interview transcripts and notes against technical criteria.
  - Generates competency scores and performance summaries.
  - Recommends a pass/fail outcome for the technical round.
-   **Trigger Event:** Master Agent technical assessment dispatch.
-   **Prerequisites:** Interview state is `Scheduled` and transcript files are uploaded.
-   **Expected Input Context:** `interview_id`, `transcript_text`, `technical_criteria`.
-   **Expected Output:** Competency scorecard JSON, summary notes, and evaluation recommendations.
-   **Allowed MCPs:** Database MCP, Resume MCP, Analytics MCP.
-   **Allowed DB Operations:** Read access to candidates, jobs, and interviews; read/write access to `technical_evaluations`.
-   **Human-in-the-Loop:** Requires interviewer review and approval of the generated scorecard draft.
-   **Failure Handling:** If transcript parsing confidence falls below thresholds, escalates the evaluation task to human review.

---

## 7. Agent 8 Contract (HR Interview & Candidate Re-ranking)

-   **Purpose:** Evaluates soft skills and updates candidate pool rankings.
-   **Responsibilities:**
  - Evaluates soft-skill competencies based on HR interview notes.
  - Generates consolidated scorecards by combining screening, technical, and HR evaluations.
  - Computes updated ranking positions for candidate pools.
-   **Trigger Event:** Master Agent HR assessment dispatch.
-   **Prerequisites:** Candidate has completed technical evaluation; HR transcript is uploaded.
-   **Expected Input Context:** `candidate_id`, `hr_transcript_text`, `technical_scorecard`.
-   **Expected Output:** Structured HR scorecard, consolidated candidate score, and updated cohort ranking matrix.
-   **Allowed MCPs:** Database MCP, Policy MCP, Salary Band MCP, Analytics MCP.
-   **Allowed DB Operations:** Read access to evaluations and candidates, read/write access to `hr_evaluations` and `candidate_rankings`.
-   **Human-in-the-Loop:** Requires hiring manager review and approval of the updated pool rankings before selection.
-   **Failure Handling:** If score calculations contain anomalies, pauses execution and alerts the hiring manager.

---

## 8. Agent Input Contract

Every worker agent (A6, A7, A8) must accept the standardized `WorkflowContext` class (Pydantic model) transmitted as a JSON request body over HTTP (`POST /agents/agent{N}/execute`) containing:
-   **`workflow_id`:** Unique identifier / trace correlation ID of the pipeline run (`context.workflow_id`).
-   **`candidate`:** Nested candidate profile data object (`context.candidate`):
    - `candidate_id` (Required)
    - `name` (Required)
    - `email` (Required)
    - `job_id` (Required)
    - `screening_score` (Required)
    - `resume_url` (Required)
    - `pipeline_state` (Required)
-   **`current_state`:** Current active candidate pipeline phase (`context.current_state`).
-   **`previous_state`:** Previous candidate pipeline phase (`context.previous_state`).
-   **`step_data`:** Key-value map storing execution task variables and checkpoints (`context.step_data`).
-   **`history`:** Chronological history of transition events in Pipeline-2 (`context.history`).
-   **`metadata`:** Diagnostic metrics and interactive configuration flags (`context.metadata`).

---

## 9. Agent Output Contract

Every agent must return a standardized output payload schema (`AgentResponse` Pydantic model) serialized as a JSON response body over HTTP (HTTP 200 OK) containing:
-   **`execution_status`:** `SUCCESS` or `FAILED` string.
-   **`generated_event`:** State machine completion event name (String).
-   **`updated_state`:** Target next state flag (String).
-   **`summary`:** Narrative summary of completed steps.
-   **`errors`:** Standardized list of failure messages, if applicable.
-   **`warnings`:** Standardized list of warnings, if applicable.
-   **`suggested_action`:** Next execution recommendation.
-   **`metadata`:** Diagnostic details (e.g., token usage, duration, trace ID).

Both schemas are serialized and validated at endpoint boundaries using standard Pydantic models. Any serialization conflict must be escalated to the systems lead before code modifications are made.

---

## 10. Agent Ownership Matrix

| Agent Component | Developer Lead | Core Duties | Allowed DB Actions | Allowed MCP Tools | Produced Events | Consumed Events |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Master Agent** | Neemay Gupta | Workflow orchestration, event routing, handoffs | `candidates` (Write state), `transition_logs` | DB, Resume, Document, Notification, Policy, Salary Band | `OfferRequested`, `WorkflowPaused`, `WorkflowFailed` | `CandidateShortlisted`, `InterviewCreated`, `TechnicalScoreSubmitted`, `HRScoreSubmitted`, `CandidateRanked`, `WorkflowResumed` |
| **Agent 6** | [TBD] | Interview scheduling and calendar invites | `interviews` (Write), `schedule_roster` (Write) | DB, Google Calendar, Google Meet, SMTP Mail, Analytics | `InterviewCreated`, `InterviewRescheduled` | Master Agent trigger |
| **Agent 7** | Piyush | Technical evaluation and scorecard parsing | `technical_evaluations` (Write) | DB, Resume, Analytics | `TechnicalScoreSubmitted` | Master Agent trigger |
| **Agent 8** | Haris | HR evaluation and cohort pool ranking | `hr_evaluations` (Write), `candidate_rankings` (Write) | DB, Policy, Salary Band, Analytics | `HRScoreSubmitted`, `CandidateRanked` | Master Agent trigger |

---

## 11. Agent State Rules

-   **Stateless Design:** Worker agents must execute like mathematical functions: given the same inputs, tools, and mock data, they must produce predictable outputs.
-   **State Isolation:** Do not store workflow states locally in agents. Workflow memory is persisted exclusively in the PostgreSQL database.
-   **Lifecycle Rule:** Workers terminate immediately after returning their outputs to the Master Agent.

---

## 12. Agent Failure Rules

-   **Deterministic Execution:** Agents do not retry indefinitely. 
-   **State Preservation:** If execution fails, the worker logs the error details, reports a `FAILED` execution status, and exits.
-   **Master-Led Retries:** The Master Agent evaluates failure outputs and determines if a retry is warranted.
-   **HITL Escalation:** If retries are exhausted, the Master Agent pauses execution and alerts the recruiter.

---

## 13. Agent Logging

Every agent execution must log:
-   **`execution_start` / `execution_end`:** Timestamp signatures.
-   **`workflow_id` / `trace_id`:** Trace indicators.
-   **`agent_name`:** Executing agent (A6, A7, A8).
-   **`mcp_calls`:** Tool execution logs.
-   **`validation_results`:** Mismatch warnings.
-   **`execution_time`:** Execution latency.
-   **`errors` / `warnings`:** Failure messages.
-   **`generated_event`:** State machine completion event.

---

## 14. Future Agent Expansion

To scale the system:
-   **Adding Agents:** Add the new agent folder (e.g., `agents/agent9/`), register its inputs and outputs, and update the Master Agent's event routing map.
-   **No Restructuring:** Adding or modifying sub-agents must not impact existing agent configurations.

---

## 15. Summary

This `agent_contracts.md` document defines the interface specifications for Pipeline-2 agents. All agent implementations must comply with these guidelines. The Master Agent manages global state routing, while worker agents execute isolated business tasks, ensuring system stability and clean boundaries as the project scales.
