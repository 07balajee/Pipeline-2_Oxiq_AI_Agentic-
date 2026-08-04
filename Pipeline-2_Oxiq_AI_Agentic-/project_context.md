# OxiqAI HRMS - Recruitment Module (Pipeline-2: Interview Management)
## PROJECT CONTEXT & SYSTEM BOUNDARIES

---

## 1. Project Overview

### OxiqAI HRMS
**OxiqAI HRMS** is an enterprise-grade, agentic AI-powered Human Resource Management System designed to automate, optimize, and scale HR workflows. By employing advanced LLM-backed specialized agents and the Model Context Protocol (MCP), OxiqAI HRMS minimizes operational overhead while maintaining top-tier data consistency, security, and human oversight.

### Recruitment Module
The **Recruitment Module** manages the candidate lifecycle from job requisition creation to final onboarding. Due to the high complexity, diverse integrations, and distinct phases of the recruitment process, it is divided into three independent, decoupled pipelines. This division ensures:
- **Modular Stability:** Failures or changes in scheduling do not impact job posting or background screening.
- **Isolated Testing:** Each pipeline can be simulated, stubbed, and validated independently.
- **Clear Ownership:** Multi-tenant developers can work on specialized agent sets without code conflicts.

### Pipeline-2 Scope
This repository is exclusively responsible for **Pipeline-2 (Interview Management)**. It handles the orchestration of candidate interview loops, scheduling, technical assessments, HR evaluations, and re-ranking. All other operations (candidate screening, offer generation, background checks) are external dependencies.

---

## 2. Overall Recruitment Pipeline

The recruitment lifecycle is structured into three consecutive pipelines. Pipeline-2 sits in the center and behaves as the core transition engine.

```
┌─────────────────────────────────┐
│     Pipeline-1 (External)       │
│  Job Creation → Screening Round  │
└────────────────┬────────────────┘
                 │
                 │ (Candidate Context Handoff)
                 ▼
┌─────────────────────────────────┐
│     Pipeline-2 (Current Scope)  │
│      Interview Management       │
└────────────────┬────────────────┘
                 │
                 │ (Selection Context Handoff)
                 ▼
┌─────────────────────────────────┐
│     Pipeline-3 (External)       │
│  Offer Letter → BG Verification  │
└─────────────────────────────────┘
```

### Pipeline Overview Table

| Pipeline | Phase | Major Responsibilities | Boundary Status |
| :--- | :--- | :--- | :--- |
| **Pipeline-1** | Candidate Sourcing & Screening | Job Requisition, Approvals, Multi-channel Posting, Career Portal, AI Resume Screening | **External Dependency** |
| **Pipeline-2** | **Interview Management** | **Orchestration, Scheduling (A6), Technical Evaluation (A7), HR Evaluation & Candidate Re-ranking (A8)** | **Current Workspace Scope** |
| **Pipeline-3** | Candidate Closing & Onboarding | Offer Letter Generation, Acceptance Workflow, Background Verification (BGV), Campus Drive | **External Dependency** |

---

## 3. Current Scope

To maintain loose coupling and architectural stability, the boundaries of development in this repository are strictly enforced.

### Allowed
- **Master Orchestration Agent:** The brain of Pipeline-2, coordinating candidate progression.
- **Agent 6 (Interview Invitation & Scheduling):** Manages calendar availability, invites, and notifications (Frozen Reference Implementation).
- **Agent 7 (Technical Interview):** Evaluates technical assessments, parses interviewer scorecards, and summarizes results (Active Development).
- **Agent 8 (HR Interview & Re-ranking):** Conducts HR screening reviews and recalculates ranking metrics across candidates (Active Development).
- **Shared Contracts:** Declarative schemas and handshake models between components.
- **Prompt Definitions:** System and user prompt templates for agents.
- **Workflow / Database / MCP Contracts:** Stable specifications detailing internal and external operations.

### Not Allowed
- **Pipeline-1 Operations:** Job requisition forms, resume parsing engines, or career site scraping.
- **Pipeline-3 Operations:** Offer template builder, background verification API integrations.
- **Frontend / HRMS UI:** Any UI development, screens, or dashboard assets (handled by a separate frontend team).
- **Core HRMS Services:** Authentication (Auth0/OAuth), Payroll processing, Learning Management System (LMS), Attendance tracking.

---

## 4. Current Development Status

The platform core and reference workers are fully established. We are currently in **Phase 5: Architecture Re-Freeze** to support a distributed, FastAPI-connected agent communication framework orchestrated by **LangGraph + LangChain**.

### Migration Direction
Pipeline-2 is migrating from in-process python worker execution to:
`Master Agent LangGraph` -> `FastAPI / HTTP` -> `Worker Agent LangGraph`

*   **Behavioral Reference Baseline:** The Phase 4 core business logic, matching heuristics, and database mock setups are fully functional and serve as our verified reference baseline (37 tests green). The existing code is the source of truth for agent behavior and is being adapted (not replaced or rewritten) to run as isolated services.

### Completed Milestones
*   **Phase 1 & 2 (Foundations & Contracts):** Repository structure, development guidelines, team code ownership policies, and core Pydantic schemas are fully frozen.
*   **Phase 3 (Master Agent Orchestration):** The orchestrator skeleton, Event Bus, State Manager, and dynamic Registries (Agent/Tool) are fully operational.
*   **Phase 4 (Agent 6 Implementation & Hardening):** Decision intelligence heuristics, slot ranking, online-to-offline fallback, idempotency checkpoints, transaction rollbacks, and contract freeze are complete (30 regression tests passing).

---

## 5. Verified Green Baseline

Before starting any new worker development, the codebase must pass all baseline verification checks.

*   **Test Command:**
    ```bash
    PYTHONPATH=. python3 -m pytest tests/ -v
    ```
*   **Expected Results:**
    *   **Total Tests:** 37 passed, 0 failed.
    *   **Workflow / Resiliency Tests (Agent 6):** 30 passed.
    *   **Core Contract / Routing Tests:** 7 passed.
*   **Note on Warnings:** There are deprecation warnings regarding `datetime.utcnow()` in dependencies and schemas. These are non-blocking technical debt. **Do not modify frozen core/shared schemas to resolve warnings** without integration lead review.

---

## 6. Architecture Philosophy

Pipeline-2 adheres to an **Agentic Master-Worker** paradigm:

*   **Single Orchestrator:** The Master Agent handles all decision-making and flow transitions. Worker agents do not maintain routing logic.
*   **Stateless Workers:** Sub-agents (Agent 6, 7, 8) process inputs, perform operations via tools, and return outputs. They do not persist state internally between cycles.
*   **Event-Driven Workflow:** Major status transitions are triggered by clear events (e.g., `InterviewCreated`, `TechnicalScoreSubmitted`).
*   **Contract-First Development:** Database interfaces, schemas, and communication payloads must be statically defined and frozen before execution logic is coded.
*   **Human-in-the-Loop (HITL):** Critical actions, such as scheduling changes or candidate selection overrides, must suspend the orchestrator and await manual approval.
*   **MCP-First Architecture:** Systems interact via the Model Context Protocol (MCP). Agents use tools exposed through standardized MCP servers.
*   **Loose Coupling & High Cohesion:** Sub-agents must be highly cohesive around their single responsibility and fully decoupled from each other. Worker agents **must never** communicate directly.

---

## 7. Event Routing Flow & Communication Rules

Communication flow is strictly hierarchical. Sub-agents do not call peer sub-agents.

```
Pipeline-1
    ↓
CandidateShortlisted (Event)
    ↓
MASTER AGENT
    ↓
Agent 6 — Interview Invitation/Scheduling (Triggered by CandidateShortlisted)
    ↓
InterviewCreated (Event)
    ↓
MASTER AGENT
    ↓
Agent 7 — Technical Assessment (Triggered by InterviewStarted)
    ↓
TechnicalScoreSubmitted (Event)
    ↓
MASTER AGENT
    ↓
Agent 8 — HR Evaluation/Re-ranking (Triggered by TriggerHRRound)
    ↓
HRScoreSubmitted / CandidateRanked (Events)
    ↓
MASTER AGENT
    ↓
CandidateSelected / OfferPipelineTriggered
    ↓
Pipeline-3
```

1.  **Pipeline-1 → Master Agent:** Pipeline-1 triggers Pipeline-2 by publishing a `CandidateShortlisted` event.
2.  **Orchestrator → Sub-Agent:** The Master Agent invokes Agent 6, Agent 7, or Agent 8 based on the candidate's current pipeline state.
3.  **Sub-Agent → Orchestrator:** Sub-agents execute their assigned tasks and return structured `AgentResponse` payloads.
4.  **No Peer-to-Peer Communication:** Agents **never** communicate directly. Agent 6 cannot invoke Agent 7; Agent 7 cannot invoke Agent 8.
5.  **Master Agent → Pipeline-3:** Once all evaluations are complete and candidate selection is frozen, the Master Agent transitions the candidate state, triggering the Pipeline-3 offer generation.

---

## 8. Worker Agent Reference Pattern

Every worker agent folder (`agents/agent6/`, `agents/agent7/`, `agents/agent8/`) must follow the standardized structure proven by Agent 6:
*   `agent.py`: Public entrypoint implementing the `Agent` interface.
*   `validator.py`: Handles pre-flight input and validation on the `WorkflowContext`.
*   `scheduler.py` (or business logic runner): Coordinates the sequential business steps, retry logs, and idempotency checkpoints.
*   `tools.py`: Adapts standard MCP client calls into clean, typed Python interfaces.
*   `compensation.py` (**Optional**): Required only when the worker performs external side-effecting operations (like booking appointments) that need rollback or compensating actions on database commit failure.

---

## 9. Team Development & Code Ownership Rules

To ensure safety and avoid merge conflicts, code ownership boundaries are strictly enforced:

*   **Neemay Gupta (System Lead):** Owns `agents/master/**`, core schemas, contracts, and PR merges.
*   **Piyush (Agent 7 Developer):** Owns `agents/agent7/**` and related assessment tests. Must not modify Master Agent or shared schemas.
*   **Haris (Agent 8 Developer):** Owns `agents/agent8/**` and related re-ranking tests. Must not modify Master Agent or shared schemas.

### Contract Mismatch Policy
If a developer discovers that a shared schema, contract, or registry must change:
1. **STOP.** Do not modify the shared files.
2. Document the current contract, required changes, reason for changes, and the impact across all other agents (6, 7, 8) and the Master Agent.
3. Request integration review and obtain approval from Neemay Gupta before proceeding.

---

## 10. MCP Boundaries

*   **Agent 6:** Resume MCP, Database MCP, Calendar MCP, Meet MCP, Document MCP, Notification MCP.
*   **Agent 7:** Database MCP, Resume MCP (transcript context), Meet MCP (where required), Document MCP, Notification MCP (where required).
*   **Agent 8:** Database MCP, Resume MCP (cohort history), Document MCP, Analytics MCP, Notification MCP, Company Policy MCP, Salary Band MCP.

---

## 11. Mandatory Developer Startup Instructions

Before performing any implementation work, every developer or AI coding CLI entering this repository must:

1.  Read these onboarding files in order:
    *   `project_context.md`
    *   `README.md`
    *   `architecture.md`
    *   `development_rules.md`
    *   `agent_contracts.md`
    *   `workflow_contracts.md`
    *   `mcp_contracts.md`
    *   `database_contracts.md`
    *   `team_roles.md`
    *   `folder_structure.md`
2.  Inspect the existing Master Agent interfaces and Agent 6 only to understand the established worker-agent pattern.
3.  **Run the baseline checks:**
4.  **Current state:** Master Agent and Agent 6 are fully orchestrated using Compiled LangGraph and exposed via HTTP FastAPI service boundaries.
    ```bash
    PYTHONPATH=. python3 -m pytest tests/ -v
    ```
    Confirm that all 76 tests pass. If baseline tests fail, do not start worker implementation.
5.  **Confirm your understanding** of your assigned agent, file permissions, input/output events, and MCP boundaries to the coordinator before writing any code.
