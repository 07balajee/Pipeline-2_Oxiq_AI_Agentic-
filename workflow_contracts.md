# OxiqAI HRMS - Recruitment Pipeline-2
## WORKFLOW ORCHESTRATION & STATE MACHINE CONTRACTS

---

## 1. Purpose

The **Workflow Contract** defines the runtime state engine and transaction lifecycle for Pipeline-2. Establishing this specification:
- **Freezes State Transitions:** Prevents unauthorized pipeline leaps or state bypasses.
- **Defines Event Routing:** Governs how system events trigger specific agent tasks.
- **Validates Orchestration Steps:** Ensures Master Agent routing decisions follow predefined logical paths.
- **Manages Human Interactions:** Standardizes wait states, notifications, and workflow resumes for human-in-the-loop decisions.
- **Ensures Failure Isolation:** Declares retry limits, fallbacks, and escalations at the workflow layer.

---

## 2. Workflow Overview

Pipeline-2 handles candidate evaluation orchestration. The workflow transitions sequentially:

```
                  ┌──────────────────────┐
                  │ Pipeline-1 (Screen)  │
                  └──────────┬───────────┘
                             │ CandidateShortlisted Event
                             ▼
  ┌──────────────────────────────────────────────────────┐
  │                 Master Agent Router                  │
  └──────────┬───────────────┬───────────────┬───────────┘
             │               │               │
             ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │Agent 6  │     │Agent 7  │     │Agent 8  │
        │(Invite) │     │ (Tech)  │     │  (HR)   │
        └────┬────┘     └────┬────┘     └────┬────┘
             │               │               │
             └───────────────┼───────────────┘
                             │ Returns outputs & updates state
                             ▼
  ┌──────────────────────────────────────────────────────┐
  │                 Master Agent Router                  │
  └──────────┬───────────────────────────────┬───────────┘
             │                               │
             ▼ (If Selected)                 ▼ (If Rejected)
  ┌──────────────────────┐        ┌──────────────────────┐
  │ Pipeline-3 (Offer)   │        │     Archive State    │
  └──────────────────────┘        └──────────────────────┘
```

The Master Agent coordinates state transitions, invokes sub-agents based on pipeline status, and pauses execution when human decisions are required.

---

## 3. Workflow States

Below is the state configuration for Pipeline-2:

| State | Purpose | Entry Conditions | Exit Conditions | Owner | Possible Next States |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`CandidateShortlisted`** | Initial intake status. | Handoff payload received from Pipeline-1. | Master verifies payload and initiates scheduling request. | Master Agent | `InterviewScheduling`, `WorkflowFailed` |
| **`InterviewScheduling`** | Automated calendar slot matching. | State entered and target slot lists parsed. | Agent 6 confirms schedule or triggers retry limit. | Agent 6 | `InterviewScheduled`, `WorkflowPaused`, `WorkflowFailed` |
| **`InterviewScheduled`** | Confirmed calendar meeting locked. | Agent 6 successfully updates calendars. | Interview time is reached. | Master Agent | `TechnicalInterviewPending`, `InterviewScheduling` (if reschedule request) |
| **`TechnicalInterviewPending`** | Interview execution stage. | Scheduled date/time is reached. | Assessment transcript is uploaded. | Master Agent | `TechnicalInterviewCompleted`, `WorkflowFailed` |
| **`TechnicalInterviewCompleted`**| Technical scoring processing. | Assessment transcript is uploaded. | Agent 7 scorecard output is saved to database. | Agent 7 | `HRInterviewPending`, `CandidateRejected`, `WorkflowFailed` |
| **`HRInterviewPending`** | Soft skills evaluation prep. | Technical scorecard is validated and passed. | HR interview transcript is uploaded. | Master Agent | `HRInterviewCompleted`, `WorkflowFailed` |
| **`HRInterviewCompleted`** | HR scorecard analysis & sorting. | HR assessment notes are uploaded. | Agent 8 completes scorecard and re-ranks active candidate pool. | Agent 8 | `CandidateSelected`, `CandidateWaitlisted`, `CandidateRejected`, `WorkflowFailed` |
| **`CandidateSelected`** | Candidate approved by hiring lead. | Hiring manager approves pool re-ranking. | Master Agent signals Pipeline-3. | Master Agent | `OfferPipelineTriggered`, `WorkflowFailed` |
| **`CandidateRejected`** | Candidate failed assessment criteria. | Any agent returns a rejection result or the hiring manager overrides. | Candidate is moved to archive. | Master Agent | `WorkflowCompleted` |
| **`CandidateWaitlisted`** | Cohort sorting wait state. | Pool re-ranking places candidate below immediate select thresholds. | Manual override or position reopen. | Master Agent | `CandidateSelected`, `CandidateRejected` |
| **`OfferPipelineTriggered`** | Negotiation handoff state. | Selection payload is validated and sent to Pipeline-3. | Pipeline-3 registers intake. | Master Agent | `WorkflowCompleted` |
| **`WorkflowCompleted`** | Lifecycle archived successfully. | Entry to rejection archive or Pipeline-3 intake. | None (terminal state). | Master Agent | None |
| **`WorkflowPaused`** | HITL decision hold state. | Human review required or booking conflict occurs. | Human approves or override event is received. | Master Agent | Previously suspended state, `WorkflowFailed` |
| **`WorkflowFailed`** | System failure. | Exception retries exceeded or database write failure occurs. | Manual intervention or reset. | Master Agent | `InterviewScheduling`, `WorkflowCompleted` |

---

## 4. Workflow Events

The state machine is driven by these events:

| Event Name | Producer | Consumer | Trigger Condition | Expected Action |
| :--- | :--- | :--- | :--- | :--- |
| **`CandidateShortlisted`** | Pipeline-1 | Master Agent | Candidate passes screening stage. | Initialize record and trigger scheduling. |
| **`InterviewCreated`** | Agent 6 | Master Agent | Candidate slot booked. | Move state to `InterviewScheduled`. |
| **`InterviewRescheduled`**| Agent 6 / Recruiter| Master Agent | Calendar conflict or override request. | Move state to `InterviewScheduling`. |
| **`InterviewCancelled`** | Recruiter / Candidate| Master Agent | Cancellation notice received. | Cancel booking and alert team. |
| **`TechnicalScoreSubmitted`**| Agent 7 | Master Agent | Scorecard evaluation completed. | Save scorecard and route to HR round. |
| **`HRScoreSubmitted`** | Agent 8 | Master Agent | Soft skills scorecard completed. | Save scorecard and trigger pool re-ranking. |
| **`CandidateRanked`** | Agent 8 | Master Agent | Cohort sorting metrics updated. | Save rankings and trigger hiring manager review. |
| **`CandidateSelected`** | Hiring Manager | Master Agent | Hiring manager approves selection. | Update state and trigger Pipeline-3. |
| **`CandidateRejected`** | Evaluator / Manager | Master Agent | Scoring falls below minimum criteria. | Archive record and send rejection email. |
| **`OfferRequested`** | Master Agent | Pipeline-3 | Candidate selected and approved. | Send closing payload to Pipeline-3. |
| **`WorkflowPaused`** | Master Agent | Recruiter Queue | HITL decision required. | Suspend execution and queue review task. |
| **`WorkflowResumed`** | Recruiter / Admin | Master Agent | Human override or confirmation. | Resume execution flow. |
| **`RetryRequested`** | Master Agent | Worker Agent | Temporary tool or network failure. | Retry execution using backoff rules. |

---

## 5. Master Agent Orchestration Flow

The Master Agent processes events sequentially using this logical cycle:

```
  ┌────────────────────────────────────────────────────────┐
  │ 1. Receive Event (Intake schema check)                 │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 2. Retrieve & Validate Context (Load details from DB)  │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 3. Determine Current & Next Target State               │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 4. Select Worker Agent & Approved MCP Tools            │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 5. Validate Trigger Preconditions                      │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 6. Invoke Worker (Transmit context payload)            │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 7. Validate Output & Persist State                     │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │ 8. Emit Completion Event & Transition                  │
  └────────────────────────────────────────────────────────┘
```

1.  **Receive Event:** Intake event validation against defined schemas.
2.  **Retrieve Context:** Query candidate background and interview history.
3.  **Validate Context:** Ensure candidate details are consistent.
4.  **Determine States:** Map current state to target next state.
5.  **Select Agent/Tools:** Identify worker agent and allowed MCP tools.
6.  **Validate Preconditions:** Verify prerequisite tasks are completed.
7.  **Invoke Agent:** Send validation parameters and trigger worker task.
8.  **Process Output:** Parse results, write to database, and transition state.

---

## 6. Agent Invocation Rules

### Agent 6 (Interview Invitation)
-   **Trigger Event:** `CandidateShortlisted` or `RetryRequested`.
-   **Prerequisites:** State is `CandidateShortlisted` or `InterviewScheduling`.
-   **Expected Inputs:** `WorkflowContext` containing candidate context and job details.
-   **Expected Outputs:** `AgentResponse` containing `InterviewCreated` or `RetryRequested` event details, updated state, and metadata (`candidate_id`, `time_slot`, `interviewer_name`).
-   **Completion Event:** `InterviewCreated` (transitions to `STATE_INTERVIEW_SCHEDULED`).

### Agent 7 (Technical Assessment Evaluator)
-   **Trigger Event:** `InterviewStarted`.
-   **Prerequisites:** State is `STATE_TECHNICAL_INTERVIEW_PENDING` (after scheduling).
-   **Expected Inputs:** `WorkflowContext` containing `interview_id`, `candidate` details, and job requirements.
-   **Expected Outputs:** `AgentResponse` containing `TechnicalScoreSubmitted` event details, updated state (`STATE_TECHNICAL_INTERVIEW_COMPLETED`), and scorecard details.
-   **Completion Event:** `TechnicalScoreSubmitted`.

### Agent 8 (HR Assessment & Re-ranking)
-   **Trigger Event:** `TriggerHRRound`.
-   **Prerequisites:** State is `STATE_HR_INTERVIEW_PENDING` (after technical completion).
-   **Expected Inputs:** `WorkflowContext` containing technical scores and HR transcript.
-   **Expected Outputs:** `AgentResponse` containing `HRScoreSubmitted` or `CandidateRanked` event details, updated state (`STATE_HR_INTERVIEW_COMPLETED`), and ranking details.
-   **Completion Event:** `HRScoreSubmitted` (moves state to `STATE_HR_INTERVIEW_COMPLETED`), followed by `CandidateRanked` (moves state to `STATE_CANDIDATE_SELECTED`).

---

## 7. Human-in-the-Loop (HITL) Workflow

AI agents assist in screening and evaluation, but human authority is required at critical checkpoints:

-   **Interviewer Confirmation:**
    *   *Trigger:* Agent 6 suggests a schedule slot and interviewers.
    *   *Waiting State:* `WorkflowPaused` (recruiter confirmation pending).
    *   *Resume Event:* `InterviewRescheduled` or `WorkflowResumed` (confirmed).
    *   *Outcome:* Calendar invitation sent to candidate and interviewer.
-   **Technical Evaluation Review:**
    *   *Trigger:* Agent 7 submits a technical scorecard draft.
    *   *Waiting State:* `WorkflowPaused` (interviewer sign-off pending).
    *   *Resume Event:* `WorkflowResumed` (scorecard approved or updated).
    *   *Outcome:* Scorecard is frozen and saved to the database.
-   **Final Pool Re-ranking Approval:**
    *   *Trigger:* Agent 8 submits updated candidate rankings.
    *   *Waiting State:* `WorkflowPaused` (hiring manager selection pending).
    *   *Resume Event:* `CandidateSelected` or `CandidateRejected`.
    *   *Outcome:* State transitions to Pipeline-3 handoff or candidate archive.

---

## 8. MCP Interaction Flow

All database queries and external integrations (calendars, emails) are routed through MCP tools.

```
  ┌────────────────────────────────────────────────────────┐
  │                 Master Agent Router                  │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌────────────────────────────────────────────────────────┐
  │                     Worker Agent                       │
  └──────────────────────────┬──────────────────────────────┘
                             ▼ Standardized Tool Request
  ┌────────────────────────────────────────────────────────┐
  │                      MCP Server                        │
  └──────────────────────────┬──────────────────────────────┘
                             ▼ API execution / DB Query
  ┌────────────────────────────────────────────────────────┐
  │                Infrastructure Service                  │
  └────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Orchestration Rule:** MCP servers are interface tools only. They must not make orchestration decisions, trigger next steps, or modify candidate pipeline states.

---

## 9. Failure Handling Workflow

-   **Validation Failures:** If inputs do not match schemas, the Master Agent pauses execution and flags the record for administrator review.
-   **Calendar Conflicts:** If no matching calendar slots are found, Agent 6 alerts the recruiter to request manual slots.
-   **API Timeouts:** Tool connection errors trigger retries with exponential backoff before escalating.
-   **LLM Low Confidence:** If an agent's confidence score falls below set thresholds, the workflow pauses, and a manual review task is queued.
-   **Escalation Policy:** Stalled tasks (e.g., pending review for >24 hours) trigger email alerts to the operations team.

---

## 10. Retry Strategy

-   **Transient Errors Only:** Retries are reserved for transient network errors, API timeouts, or rate limits.
-   **No Retries for Business Errors:** Business logic failures (such as a candidate failing technical criteria or validation errors) must not trigger retries.
-   **Backoff Schedule:** Retries use exponential backoff (e.g., retrying after 2s, 4s, 8s).
-   **Max Attempts:** Limit tool execution to a maximum of 3 retries. If the tool still fails, trigger fallback logic.

---

## 11. Workflow Pause & Resume

Workflows pause under the following conditions:
-   **Awaiting approvals:** Waiting for interviewer, recruiter, or hiring manager confirmations.
-   **Schedule conflicts:** Automated scheduling attempts fail.
-   **API outages:** Critical external integrations are offline.

**Resuming Workflows:** Workflows resume when a verified user action triggers a resume event (e.g., `WorkflowResumed` or `CandidateSelected`), prompting the Master Agent to load candidate context and continue execution.

---

## 12. Pipeline Handoffs

Pipelines communicate exclusively through database records and transition events:

### Intake: Pipeline-1 → Pipeline-2
*   **Trigger Event:** `CandidateShortlisted`
*   **Handoff Payload:**
    *   `candidate_id` (UUID)
    *   `name` & `email` (Strings)
    *   `resume_url` (String)
    *   `screening_score` (Numeric)
    *   `job_id` (UUID)

### Output: Pipeline-2 → Pipeline-3
*   **Trigger Event:** `OfferPipelineTriggered`
*   **Handoff Payload:**
    *   `candidate_id` (UUID)
    *   `job_id` (UUID)
    *   `technical_scorecard` & `hr_scorecard` (JSON Summaries)
    *   `final_rank_index` (Integer)
    *   `recommendation` (PASS)

---

## 13. Workflow Logging

The system logs key workflow events separately from infrastructure logs:
-   **`Workflow Started`:** Pipeline-2 initialization.
-   **`Workflow State Changed`:** Details previous and target states.
-   **`Agent Invoked / Completed`:** Worker execution times and statuses.
-   **`Event Generated`:** Event name and target candidate ID.
-   **`Retry / Fallback Triggered`:** Failed tools and fallback routes.
-   **`Workflow Paused / Resumed`:** Approvals queue events and wait times.

---

## 14. Workflow Monitoring

Recruiters monitor the pipeline through these indicators:
-   **Active workflows:** Number of candidates currently in evaluation loops.
-   **Workflow status distribution:** Candidates in scheduling vs evaluation vs re-ranking.
-   **Average completion time:** Latency from intake to selection or rejection.
-   **Failure and retry metrics:** Tool failure frequencies and error trends.
-   **Pending approval durations:** Recruiter and hiring manager response times.

---

## 15. Future Workflow Extensions

-   **Adding Assessment Steps:** Add intermediate evaluation states (e.g., `CodingAssessmentPending`) and register them in the Master Agent's state map, keeping existing agent implementations unchanged.
-   **Alternative Selection Paths:** Add conditional paths (such as bypassing HR rounds for internal candidates) using state machine transitions.

---

## 16. Summary

This `workflow_contracts.md` document defines the runtime state engine and orchestration rules for Pipeline-2. All agent actions, state transitions, and external handoffs must comply with these guidelines. Enforcing these contracts ensures system observability and consistent execution throughout the recruitment lifecycle.
