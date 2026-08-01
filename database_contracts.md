# OxiqAI HRMS - Recruitment Pipeline-2
## DATABASE INTERACTION CONTRACTS

---

## 1. Purpose

The **Database Contract** is the single source of truth for all database queries and transactions in Pipeline-2. Enforcing this contract:
- **Ensures Interface Separation:** Agents do not query databases directly. All actions occur through the Database MCP server.
- **Enforces Access Control:** Restricts agent capabilities to the minimum set of tables and columns required for their tasks.
- **Validates Data Integrity:** Prevents agents from introducing bad states, corrupting other schemas, or performing unauthorized queries.
- **Standardizes System Operations:** Establishes transactional boundaries, rollbacks, and audit logging for all database mutations.

---

## 2. Database Architecture

Pipeline-2 utilizes a shared PostgreSQL instance. The schema spans tables populated by previous stages and updated during the interview lifecycle:

-   **Pipeline-1 Input:** Writes the candidate's core profile records and job requisition data.
-   **Pipeline-2 Scope:** Reads candidate/job criteria, schedules interview dates, registers scorecards, and computes pool rankings.
-   **Pipeline-3 Output:** Consumes finalized candidate evaluation summaries and ranking indices to initiate closing negotiations.

```
                  ┌──────────────────────┐
                  │ Pipeline-1 (Screen)  │
                  └──────────┬───────────┘
                             │ Writes Candidate & Job Requisitions
                             ▼
  ┌──────────────────────────────────────────────────────┐
  │              Shared PostgreSQL Database              │
  │                                                      │
  │   - Candidates  - Jobs               - Interviews    │
  │   - Roster      - Technical Scores   - HR Scores     │
  │   - Rankings    - Transitions Logs                   │
  └──────────────────────────┬───────────────────────────┘
                             │ Consumes Selection Context
                             ▼
                  ┌──────────────────────┐
                  │ Pipeline-3 (Offer)   │
                  └──────────────────────┘
```

---

## 3. Database Access Philosophy

-   **MCP Abstraction:** Direct SQL client objects are prohibited inside agent logic. All database actions use Database MCP tool definitions.
-   **Explicit Permissions:** Access to read or write columns must be declared in this contract. If a table or column is omitted, the MCP server must reject the call.
-   **Least Privilege:** Workers only access the subset of tables necessary to complete their task (e.g., Agent 7 cannot update schedule rosters).
-   **Transactional Safety:** State changes affecting multiple tables must execute within isolated, single-transaction boundaries.
-   **Audit Traceability:** Mutations must log the initiating agent, timestamp, target record ID, and candidate trace ID.

---

## 4. Master Agent Database Contract

The Master Agent coordinates workflow states and manages transitions. It does not perform domain evaluations.

| Target Table | Allowed Reads | Allowed Writes | Operation Purpose |
| :--- | :--- | :--- | :--- |
| **`candidates`** | `candidate_id`, `job_id`, `screening_status`, `pipeline_state` | `pipeline_state` | Updates the global pipeline phase of the candidate. |
| **`jobs`** | `job_id`, `status` | None | Validates if a job position remains active. |
| **`interviews`** | `interview_id`, `candidate_id`, `interviewer_id`, `status` | `status` | Updates interview lifecycle milestones. |
| **`technical_evaluations`** | `evaluation_id`, `interview_id`, `recommendation` | None | Evaluates technical assessment outcome for routing. |
| **`hr_evaluations`** | `evaluation_id`, `interview_id`, `recommendation` | None | Evaluates HR assessment outcome for routing. |
| **`candidate_rankings`** | `ranking_id`, `candidate_id`, `rank_index` | None | Checks if re-ranking is complete before handoff. |
| **`transition_logs`** | None | `log_id`, `candidate_id`, `from_state`, `to_state`, `transitioned_by` | Records historical state transitions for auditing. |

---

## 5. Agent 6 Database Contract (Interview Invitation)

Agent 6 coordinates interview schedules and updates calendars.

-   **Allowed READ Tables:**
    -   `candidates`: `candidate_id`, `name`, `email`, `pipeline_state`
    -   `jobs`: `job_id`, `job_title`
    -   `schedule_roster`: `roster_id`, `interviewer_id`, `interviewer_name`, `available_slots`
-   **Allowed WRITE Tables:**
    -   `interviews`: `interview_id`, `candidate_id`, `interviewer_id`, `scheduled_time`, `meeting_link`, `status`
    -   `schedule_roster`: `available_slots` (to reserve slots)
-   **Allowed Columns & Types:**
    -   `interviews.scheduled_time` (timestamp)
    -   `interviews.meeting_link` (text URL)
    -   `interviews.status` (varchar state: `SCHEDULED`, `PENDING_RESCHEDULE`, `CANCELLED`)
-   **Expected Output:** Confirmed schedule record in `interviews` and booked slot flag in `schedule_roster`.

---

## 6. Agent 7 Database Contract (Technical Interview)

Agent 7 processes technical feedback scorecards and generates scores.

-   **Allowed READ Tables:**
    -   `candidates`: `candidate_id`, `name`, `resume_url`
    -   `jobs`: `job_id`, `technical_criteria`
    -   `interviews`: `interview_id`, `candidate_id`, `scheduled_time`, `status`
-   **Allowed WRITE Tables:**
    -   `technical_evaluations`: `evaluation_id`, `interview_id`, `scores_json`, `evaluation_notes`, `recommendation`, `completed_at`
    -   `interviews`: `status` (sets status to `TECH_EVALUATED`)
-   **Allowed Columns & Types:**
    -   `technical_evaluations.scores_json` (JSONB - stores category scores)
    -   `technical_evaluations.evaluation_notes` (text summary)
    -   `technical_evaluations.recommendation` (varchar: `PASS`, `FAIL`)
-   **Expected Output:** Structured evaluation profile in `technical_evaluations`.

---

## 7. Agent 8 Database Contract (HR Interview & Re-ranking)

Agent 8 evaluates soft-skill scorecards and updates pool rankings.

-   **Allowed READ Tables:**
    -   `candidates`: `candidate_id`, `name`, `screening_score`
    -   `interviews`: `interview_id`, `status`
    -   `technical_evaluations`: `scores_json`, `recommendation`
    -   `hr_evaluations`: `evaluation_id`, `scores_json`, `recommendation`
-   **Allowed WRITE Tables:**
    -   `hr_evaluations`: `evaluation_id`, `interview_id`, `scores_json`, `evaluation_notes`, `recommendation`, `completed_at`
    -   `candidate_rankings`: `ranking_id`, `candidate_id`, `job_id`, `rank_index`, `normalized_score`, `updated_at`
    -   `interviews`: `status` (sets status to `HR_EVALUATED` / `RE_RANKED`)
-   **Allowed Columns & Types:**
    -   `hr_evaluations.scores_json` (JSONB)
    -   `hr_evaluations.evaluation_notes` (text)
    -   `candidate_rankings.rank_index` (integer ranking placement)
    -   `candidate_rankings.normalized_score` (numeric index)
-   **Expected Output:** Validated HR evaluation record and recalculated job cohort ranking row in `candidate_rankings`.

---

## 8. Shared Tables

This table lists shared schema boundaries:

| Table | Purpose | Owning Pipeline | Readable By | Writable By | Remarks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`candidates`** | Stores profile details, contact info, and pipeline phase status. | Pipeline-1 | Pipeline-1, Master, A6, A7, A8 | Pipeline-1 (All), Master (States only) | Read-only for worker agents. Master Agent updates lifecycle flags. |
| **`jobs`** | Contains active job descriptions and assessment criteria. | Pipeline-1 | Pipeline-1, Master, A6, A7, A8 | Pipeline-1 | Static read-only table for Pipeline-2. |
| **`interviews`** | Tracks scheduled events and interview states. | Pipeline-2 | Master, A6, A7, A8 | A6 (Creates/Reschedules), Master (State updates) | Core scheduling table for Pipeline-2. |
| **`schedule_roster`** | Tracks interviewer calendars and available slots. | Pipeline-2 | Master, A6 | A6 | Managed by the scheduling worker to prevent double-booking. |
| **`technical_evaluations`** | Technical scorecards and evaluation notes. | Pipeline-2 | Master, A7, A8 | A7 | Read-only for Agent 8 during pool re-ranking. |
| **`hr_evaluations`** | HR soft skill scores and evaluations. | Pipeline-2 | Master, A8 | A8 | Read-only for Master Agent orchestration check. |
| **`candidate_rankings`** | Global ranking indices for candidates. | Pipeline-2 | Master, A8, Pipeline-3 | A8 | Consumed by Pipeline-3 for offers. |

---

## 9. Database Ownership Matrix

| Database Table | Master Agent | Agent 6 (Invite) | Agent 7 (Tech) | Agent 8 (HR & Rank) |
| :--- | :--- | :--- | :--- | :--- |
| **`candidates`** | Read / Write (State only) | Read Only | Read Only | Read Only |
| **`jobs`** | Read Only | Read Only | Read Only | Read Only |
| **`interviews`** | Read / Write (State only) | Read / Write | Read Only | Read Only |
| **`schedule_roster`** | Read Only | Read / Write | No Access | No Access |
| **`technical_evaluations`**| Read Only | No Access | Read / Write | Read Only |
| **`hr_evaluations`** | Read Only | No Access | No Access | Read / Write |
| **`candidate_rankings`** | Read Only | No Access | No Access | Read / Write |
| **`transition_logs`** | Read / Write | No Access | No Access | No Access |

---

## 10. Transaction Guidelines

-   **Atomic State Changes:** Changing a candidate's pipeline phase (e.g., from `Tech Eval` to `HR Eval`) must execute within a database transaction to ensure changes are written successfully:
    1. Update candidate stage in `candidates`.
    2. Write transition entry in `transition_logs`.
-   **Rollback Scenarios:** If step 2 fails, step 1 must rollback to prevent state mismatch.
-   **No Partial Writes:** Writing a scorecard to `technical_evaluations` must happen atomically alongside updating the status flag in `interviews`.
-   **Concurrency Protection:** Use optimistic locking (or transaction isolation levels) when scheduling slots in `schedule_roster` to prevent double-booking.

---

## 11. Validation Rules

-   **Candidate Verification:** Verify candidate exists and their pipeline state is active before creating an interview.
-   **Job Requisition Check:** Validate that the associated job is active before booking slots.
-   **Double-Booking Check:** Ensure slots in `schedule_roster` are not reserved for another interview before writing to `interviews`.
-   **Unique Active Interviews:** Enforce database integrity constraints to ensure candidates do not have multiple active interviews simultaneously.
-   **Handoff Validation:** Candidates must have a complete scorecard record in `technical_evaluations` before transitioning to the HR round.

---

## 12. Audit & Logging

Every database write, update, or deletion must emit an audit event containing:
-   **`timestamp`:** ISO-8601 UTC timestamp.
-   **`initiator`:** Entity triggering the call (Master Agent, Agent 6, etc.).
-   **`trace_id`:** Unique identifier of the candidate workflow.
-   **`operation_type`:** `INSERT`, `UPDATE`, or `DELETE`.
-   **`table_name`:** Targeted database table.
-   **`transaction_id`:** DB transaction reference.
-   **`status`:** `SUCCESS` or `FAILED`.

---

## 13. Error Handling

-   **Missing Candidate:** Return a `CANDIDATE_NOT_FOUND` error to the Master Agent. Stop the workflow and trigger a warning.
-   **Job Requisition Inactive:** Return `JOB_INACTIVE`. Flag the exception and suspend scheduling.
-   **Interview Conflict:** Return `SLOT_UNAVAILABLE` to Agent 6 to request reschedule selection.
-   **Write Mismatch/Failure:** If database write failures occur, rollback transactions and raise a `DATABASE_WRITE_ERROR` notification.
-   **Connection Timeout:** MCP server queues queries and retries execution using exponential backoff before escalating.

---

## 14. Future Extensibility

-   **Adding Evaluations:** A new "Coding Round" requires adding a `coding_evaluations` table. Permissions are configured for the new agent, keeping existing agent tables unaffected.
-   **Updating Rank Models:** Adding ranking parameters (such as seniority weighting) only requires updating columns in `candidate_rankings`, leaving the core scheduling and evaluation tables unchanged.
-   **Third-Party Integrations:** Adding an external scheduling sync updates the backend Database MCP layer, while agent logic remains unchanged.

---

## 15. Summary

This `database_contracts.md` document defines the database access rules for Pipeline-2. Any changes to database access permissions or transaction flows must be updated in this contract first. Establishing these guidelines protects data integrity, ensures system trace logging, and simplifies the implementation of the Database MCP.
