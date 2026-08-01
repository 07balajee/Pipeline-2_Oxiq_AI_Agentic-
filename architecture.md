# OxiqAI HRMS - Recruitment Pipeline-2
## HIGH-LEVEL DESIGN (HLD): INTERVIEW MANAGEMENT ARCHITECTURE

---

## 1. Introduction

### Purpose
The purpose of **Pipeline-2 (Interview Management)** is to govern, coordinate, and evaluate the candidate interview lifecycle. It automates interview scheduling, evaluation review, and re-ranking while maintaining absolute data integrity and auditability.

### Process Boundaries
- **Entry Trigger:** Pipeline-2 begins when a candidate is shortlisted by **Pipeline-1 (Screening)**. The screening system emits a candidate handoff signal containing profile metadata, resumes, and initial evaluation scores.
- **Exit Trigger:** Pipeline-2 concludes when a candidate successfully completes all evaluation loops (or is rejected/withdrawn) and the orchestrator triggers **Pipeline-3 (Offer Management)** for final negotiations and onboarding steps.

### Architectural Paradigm
Pipeline-2 utilizes an **Agentic AI master-worker approach** combined with the **Model Context Protocol (MCP)**. A single Master Agent handles workflow state and orchestration, delegating all domain-specific tasks to specialized, stateless worker agents.

---

## 2. Architecture Overview

Pipeline-2 enforces a centralized hub-and-spoke orchestration pattern.

```
       ┌────────────────────────┐
       │ Pipeline-1 (Screening) │
       └───────────┬────────────┘
                   │
                   ▼ [Handoff Event]
       ┌────────────────────────┐
       │      Master Agent      │◄────────────────────────┐
       └─────┬───────────┬──────┴─┐                       │
             │           │        │                       │
     Trigger │   Trigger │        │ Trigger               │
             ▼           ▼        ▼                       │
         ┌──────┐    ┌──────┐     ┌──────┐                │
         │  A6  │    │  A7  │     │  A8  │                │
         └──┬───┘    └──┬───┘     └──┬───┘                │
            │           │            │                    │
            └───────────┴────────────┴────────────────────┘
                       Execution Results Handback
                               │
                               ▼ [Trigger Event]
                       ┌────────────────────────┐
                       │   Pipeline-3 (Offer)   │
                       └────────────────────────┘
```

### Centralization and Isolation
*   **The Master Agent is the sole orchestrator:** It holds the state machine, evaluates transition logic, handles human feedback triggers, and coordinates handoffs.
*   **Worker Agents are isolated processors:** Agent 6, Agent 7, and Agent 8 act as modular units. They operate on request-response parameters provided by the Master Agent.
*   **No Worker Peer-to-Peer Communication:** Sub-agents never invoke or communicate with other sub-agents. Agent 6 has no awareness of Agent 7 or Agent 8.
*   **Centralized Handoff:** All inputs, execution logs, and outputs must return to the Master Agent for verification and validation before moving to the next pipeline state.

---

## 3. Architectural Principles

| Principle | Description | Rationale |
| :--- | :--- | :--- |
| **Single Master Orchestrator** | A single central agent manages the global execution state and execution flow. | Eliminates distributed state complexity, guarantees execution consistency, and simplifies audit logging. |
| **Event-Driven Workflow** | System transitions are triggered by explicit, observable transaction events. | Provides highly testable and loosely coupled state handshakes between stages. |
| **Stateless Agents** | Worker agents do not persist candidate history, local caches, or pipeline state between cycles. | Simplifies horizontal scaling, allows easy agent restarts, and eliminates race conditions. |
| **Contract-First Development** | All schemas, database tables, and API boundaries are defined and frozen before writing code. | Enforces strict compile-time/type verification and prevents breaking changes across team boundaries. |
| **MCP-First Integration** | All external resources and shared databases are accessed exclusively through MCP interfaces. | Abstracts underlying system connections, allows local testing via mock servers, and provides strict permission control. |
| **Human-in-the-Loop (HITL)** | Critical decisions (approvals, overrides, scheduling conflicts) require manual human authorizations. | Mitigates AI hallucinations, ensures legal compliance, and aligns decisions with organizational goals. |
| **Loose Coupling** | Components assume minimal details about other components' implementations. | Allows independent development, testing, and hot-swapping of specific agents without affecting others. |
| **High Cohesion** | Each agent focus is narrowed to a single, tightly defined domain (e.g., scheduling, HR evaluation). | Simplifies agent prompts, reduces token usage, and increases target task performance. |
| **Fault Tolerance** | Standardized retries, fallbacks, and escalation policies are built into every level of interaction. | Prevents transient network errors or LLM API outages from stalling the entire recruitment pipeline. |
| **Observability** | Every LLM call, tool call, and state transition emits structured telemetry logs. | Critical for debugging complex multi-agent flows, tracking execution costs, and performing security audits. |

---

## 4. System Components

### Master Agent (Orchestrator)
- **Purpose:** Coordinates candidate state progression, manages workflow status, validates sub-agent inputs and outputs, and oversees transitions between Pipeline-1 and Pipeline-3.
- **Responsibilities:**
  - Standardizes handshakes with Pipeline-1.
  - Classifies candidate status and maps out necessary steps.
  - Dispatches execution tasks to Agent 6, Agent 7, or Agent 8.
  - Evaluates worker outputs and marks workflow checkpoints.
  - Pauses execution for human review and triggers resume events.
- **Inputs:** Candidate data packets (from Pipeline-1), worker outcomes, human approvals.
- **Outputs:** State updates, task payloads for workers, triggering events for Pipeline-3.
- **System Interaction:** Direct communication link to all worker agents, Database MCP, and human approval queues.

### Agent 6 (Interview Invitation & Scheduling)
- **Purpose:** Automates and coordinates the interview scheduling and booking workflow.
- **Responsibilities:**
  - Evaluates candidate and interviewer availability windows.
  - Generates meeting invites and schedules calendars.
  - Coordinates re-scheduling events and tracks cancellations.
- **Inputs:** Candidate contact metadata, interviewer list, preferred timeline windows.
- **Outputs:** Booking status, scheduled timeslot, meeting link, notification tracking details.
- **System Interaction:** Interacts with Google Calendar, Google Meet, and SMTP Mail MCP tools. Reports results back to the Master Agent.

### Agent 7 (Technical Interview Assessment)
- **Purpose:** Manages the technical evaluation stage and consolidates scorecard results.
- **Responsibilities:**
  - Retrieves candidate's technical profile and assessment benchmarks.
  - Processes interviewer feedback scorecards and parses notes.
  - Generates standard, structured evaluations of candidate capabilities.
- **Inputs:** Job description technical criteria, candidate resume, interviewer scorecards, interview transcripts.
- **Outputs:** Structured technical score card, calculated competency indices, recommendation flag (Pass/Fail).
- **System Interaction:** Pulls evaluation criteria via MCP, processes candidate documents, and reports standardized scorecards to the Master Agent.

### Agent 8 (HR Interview & Candidate Re-ranking)
- **Purpose:** Coordinates soft-skill evaluations and updates global candidate pool rankings.
- **Responsibilities:**
  - Summarizes HR interview feedback.
  - Analyzes overall candidate scoring matrices (combining screening, tech, and HR outputs).
  - Computes candidate ranking metrics across current active cohorts.
- **Inputs:** Final HR interview transcript/notes, technical evaluation summary, historical screening scorecards.
- **Outputs:** Structured HR scorecard, consolidated candidate scorecard, updated global pool ranking matrix.
- **System Interaction:** Reads historical records via DB MCP and returns final rankings to the Master Agent.

---

## 5. Communication Architecture

### Communication Flow Constraints

```
┌────────────────────────────────────────────────────────┐
│                      ALLOWED FLOWS                     │
├────────────────────────────────────────────────────────┤
│  Pipeline-1     ───>  Master Agent (Handoff trigger)    │
│  Master Agent   <──>  Worker Agents (A6 / A7 / A8)     │
│  Master Agent   ───>  Pipeline-3 (Completion trigger)   │
│  Master Agent   ───>  MCP Servers (Database / Shared)   │
│  Worker Agents  ───>  MCP Servers (Scoped permissions)  │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                    FORBIDDEN FLOWS                     │
├────────────────────────────────────────────────────────┤
│  Worker Agent   ──x──  Worker Agent                     │
│  Worker Agent   ──x──  Direct Database client connection│
│  Worker Agent   ──x──  Direct HTTP API / HTTP endpoints │
│  Pipeline-1     ──x──  Pipeline-3                       │
└────────────────────────────────────────────────────────┘
```

### Rationales for Communication Rules
1.  **Isolation (No Worker-to-Worker):** Prevents recursive loops, side-effects, and code dependencies between agents. Changes to Agent 7's interface cannot break Agent 6.
2.  **Security & Abstraction (No Direct DB/API):** Enforcing MCP access routes guarantees that data access permissions, token encryption, and audit logs are managed centrally.
3.  **Process Separation (No Cross-Pipeline talk):** Decoupling Pipeline-1, Pipeline-2, and Pipeline-3 ensures changes to sourcing platforms or payroll schemas do not disrupt the core evaluation logic.

---

## 6. Event-Driven Workflow

The status and flow transitions of a candidate within Pipeline-2 are driven entirely by system events. 

```
                                 CandidateShortlisted (Pipeline-1)
                                                 │
                                                 ▼
                                        ┌────────────────┐
                                        │  Master Agent  │
                                        └───────┬────────┘
                                                │
                                                ▼
                                         [State: Scheduled]
                                        InterviewScheduled (A6)
                                                │
                                                ▼
                                         [State: Tech Eval]
                                    TechnicalInterviewCompleted (A7)
                                                │
                                                ▼
                                         [State: HR Eval]
                                       HRInterviewCompleted (A8)
                                                │
                                                ▼
                                       ┌────────────────┐
                ┌─────────────────────>│  Master Agent  ├──────────────────────┐
                │                      └────────────────┘                      │
                │ CandidateSelected                                            │ CandidateRejected
                ▼                                                              ▼
        ┌───────────────┐                                              ┌───────────────┐
        │  Pipeline-3   │                                              │ Archived State│
        └───────────────┘                                              └───────────────┘
```

-   **`CandidateShortlisted`:** Emitted by Pipeline-1. Signals the Master Agent to register the candidate in Pipeline-2 and initiate scheduling.
-   **`InterviewScheduled`:** Emitted by Agent 6. Details the confirmed slot, meeting URLs, and lists the interviewers.
-   **`TechnicalInterviewCompleted`:** Emitted by Agent 7. Provides technical score metrics and triggers the next state transition logic.
-   **`HRInterviewCompleted`:** Emitted by Agent 8. Delivers soft-skill feedback and triggers re-ranking evaluation.
-   **`CandidateSelected`:** Emitted by the Master Agent. Marks final hiring committee approval and signals Pipeline-3.
-   **`CandidateRejected`:** Emitted by the Master Agent. Halts processing and archives the candidate record.
-   **`OfferPipelineTriggered`:** Emitted by the Master Agent. Transmits the candidate selection context to Pipeline-3.

---

## 7. Model Context Protocol (MCP) Layer

The **Model Context Protocol (MCP)** defines the interface standard for resource access and tool invocation. 

```
                 ┌────────────────────────────────┐
                 │          Master Agent          │
                 └───────────────┬────────────────┘
                                 │ Standardized MCP JSON-RPC
                                 ▼
                 ┌────────────────────────────────┐
                 │           MCP Router           │
                 └───────────────┬────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│  Database MCP  │      │  Resume MCP    │      │  Calendar MCP  │
└────────────────┘      └────────────────┘      └────────────────┘
```

### Internal MCP Servers
*   **Database MCP:** Performs CRUD actions on candidates, schedules, evaluations, and rankings. No raw SQL flows outside this server.
*   **Resume MCP:** Secure parser to retrieve, search, and extract elements from resumes.
*   **Notification MCP:** Standardized system messages sent via email or Slack.
*   **Document MCP:** Generates PDF evaluation cards and hiring templates.
*   **Analytics MCP:** Logs system latency, tool performance, and candidate progression funnels.
*   **Company Policy MCP:** Exposes current hiring guidelines and background criteria.
*   **Salary Band MCP:** Retrieves approved compensation ranges for target positions.

### External MCP Servers
*   **Google Calendar MCP:** Integrates with Workspace API to query calendars and insert bookings.
*   **Google Meet MCP:** Generates virtual conferencing rooms and access tokens.
*   **SMTP Mail Service:** Dispatches formal schedules, updates, and templates to candidates.

---

## 8. Database Layer

Pipeline-2 reads and writes to a shared PostgreSQL database. Access is strictly controlled.

-   **Shared Schema, Segregated Views:** Databases contain multiple schemas, but Pipeline-2 agents are only allowed to see tables explicitly declared in their contracts.
-   **MCP Abstraction:** SQL logic, indexing queries, and pool managers live inside the Database MCP server. Agents consume abstract functions (e.g., `insert_scheduled_interview`).
-   **Transaction & Rollback Policies:** Multi-table writes must happen inside transactional blocks managed by the Database MCP to prevent partial data writes (e.g., scheduling a date without recording the relation).

---

## 9. Human-in-the-Loop (HITL)

AI agents guide candidates, compile evaluations, and suggest rankings, but human authority is required at critical checkpoints:

1.  **Interviewer Selection:** The Master Agent suggests qualified interviewers based on skill mapping, but scheduling requires a recruiter's confirmation.
2.  **Technical Interview Validation:** Recommending a pass/fail outcome requires review by the technical interviewer before finalizing.
3.  **HR Interview Verification:** HR personnel confirm the soft-skill metrics suggested by Agent 8.
4.  **Hiring Manager Review:** The hiring manager must confirm candidate re-ranking prior to triggering the offer.
5.  **Final Recommendation Override:** Hiring managers can override agent recommendations, which pauses the pipeline and registers the manual intervention.

---

## 10. Error Handling & Fallback Strategy

The system is designed with a fault-tolerant structure to handle potential failures gracefully:

-   **Validation Failure:** Incorrect payloads from external pipelines or worker agents trigger validation alerts, blocking transition states and keeping the candidate in their current state.
-   **Tool/API Outage:** If external APIs (e.g., Google Calendar) are down, the MCP server queues request retry patterns using exponential backoff.
-   **LLM Low Confidence:** When an agent returns confidence scores below acceptable thresholds, the Master Agent suspends automation and creates a task in the human review queue.
-   **Human Approval Timeout:** If approvals stall beyond a configured period (e.g., 48 hours), the Master Agent alerts the recruiter and escalates the issue.
-   **State Recovery:** In-flight crashes trigger state rollbacks to the last verified database checkpoint.

---

## 11. Logging & Observability

Observability is integrated directly into the core design:
-   **Workflow Traces:** Each candidate is assigned a unique `trace_id` that is passed through every event, tool call, and agent cycle.
-   **Agent Telemetry:** Executions log:
  - Timestamp, input schema, output schema, agent classification confidence.
  - LLM token usage metrics (prompt vs completion).
-   **MCP Audit Logs:** Database reads/writes, calendar updates, and emails are logged with execution latency.
-   **Alerting Integration:** Unhandled worker exceptions or validation failures trigger immediate DevOps alerts.

---

## 12. Future Scalability

The hub-and-spoke Master-Worker model simplifies scaling:
-   **New Interview Rounds:** To insert a "Coding Assessment" round, developers create Agent 9, register its contract, and update the Master Agent's state transition map. No other agent code is touched.
-   **Multiple LLM Backends:** Switching technical evaluations from Claude to OpenAI requires only updating the configuration within Agent 7's prompts or runner setup.
-   **Multi-tenant Calendars:** Support for Outlook calendar integration is added by implementing a Microsoft Calendar MCP server, keeping the agent layer unchanged.

---

## 13. Architecture Summary

In summary, Pipeline-2 defines a highly decoupled, modular environment where the Master Agent handles routing and worker agents execute discrete tasks. By abstracting external databases and services via MCP, enforcing database contracts, and incorporating human reviews, the architecture balances automation efficiency with enterprise-grade stability and security.
