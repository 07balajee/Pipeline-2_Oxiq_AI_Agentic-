# OxiqAI HRMS - Recruitment Pipeline-2
## DEVELOPMENT RULES & ENGINEERING STANDARDS

---

## 1. Purpose

The engineering and collaboration standards are frozen prior to implementation. Establishing these rules:
- **Ensures Development Consistency:** Guarantees all developers write code that looks, feels, and operates as if authored by a single engineer.
- **Enforces Predictable Architecture:** Prevents random design modifications and maintains the hub-and-spoke Master-Agent paradigm.
- **Simplifies Onboarding:** Clarifies testing, logging, and coding standards, helping new contributors write production-ready code from day one.
- **Minimizes Merge Conflicts:** Restricts developer activities to designated workspaces.
- **Improves Maintainability:** Establishes standards for logging, testing, and error handling, making bugs easier to locate.
- **Locks in Enterprise Standards:** Adheres to strict software engineering practices required for high-availability systems.

---

## 2. General Development Principles

All contributions must adhere to the following principles:

*   **Architecture-First Development:** Documentation, flowcharts, and HLD specifications must be updated and approved before mutating code directories.
*   **Contract-First Development:** Interface boundaries, validation schemas, and database CRUD paths must be defined before implementing agent logic.
*   **Modular Design:** Code must be split into isolated, swappable components with clear interfaces.
*   **Loose Coupling:** Components must remain independent and communicate with minimal assumptions about other modules.
*   **High Cohesion:** Each module, script, and agent must focus on a single, well-defined domain.
*   **Event-Driven Design:** System state transitions must be triggered by discrete, observable events rather than direct agent-to-agent commands.
*   **MCP-First Integration:** Direct API calls and raw SQL executions are forbidden. All integrations use the Model Context Protocol.
*   **Human-in-the-Loop Respect:** AI-driven decisions must be auditable, reviewable, and subject to override by human operators at defined checkpoints.
*   **Single Responsibility Principle (SRP):** Every class, function, and agent must have one, and only one, reason to change.

---

## 3. Coding Standards

-   **Explicit Naming:** Variables, classes, and function names must be descriptive and self-documenting. Use full names (e.g., `candidate_evaluation_score` instead of `cand_eval_sc`).
-   **Narrow Scope Functions:** Functions must be small, focused, and perform a single logical task.
-   **DRY (Don't Repeat Yourself):** Common utilities, decorators, and helper scripts must be centralized in `shared/`.
-   **Consistent Formatting:** Follow standard style guidelines (such as PEP 8 for Python).
-   **Comprehensive Docstrings:** Every public function and class must include docstrings explaining parameters, returns, and raised exceptions.
-   **Readability over Cleverness:** Avoid highly condensed inline logic, complex nested comprehensions, or obscure language features that increase cognitive load for other maintainers.

---

## 4. Folder Discipline

-   **Namespace Rules:** Developers must restrict their coding changes to their owned directories (e.g., `agents/agent7/`).
-   **No Custom Directories:** Creating top-level folders not registered in `folder_structure.md` is forbidden.
-   **Shared Folder Cleanliness:** Code inside `shared/` must remain generic and helper-focused. Do not place candidate scheduling rules, scoring logic, or custom routing parameters in shared utilities.
-   **Prompt Isolation:** Prompt files must live under `prompts/` and remain version controlled. Do not hardcode prompts inside Python strings.
-   **Contract Immutability:** Interface contracts under `contracts/` and Pydantic files under `schemas/` are read-only. Modifying them requires approval.

---

## 5.  Agent Development & Service Isolation Rules

Every sub-agent (A6, A7, A8) must comply with these guidelines:

1.  **Single Duty Focus:** Sub-agents must execute their single assigned task (e.g., scheduling an interview or scoring a transcript) and exit. They must not manage routing or direct other agents.
2.  **Strict Statelessness:** Agents must not store context locally or rely on in-memory history between execution runs.
3.  **Context-Driven Execution:** All inputs, profile values, and criteria parameters must be passed directly to the worker by the Master Agent.
4.  **Forbidden Worker Imports:** Worker services cannot import other worker services. The Master Agent **must not** import any worker implementation classes. Communication must proceed strictly via FastAPI HTTP boundaries using Pydantic JSON serialization contracts.
5.  **No Direct APIs:** Worker agents must not call external APIs directly. All connections (e.g., Google Calendar, Slack notifications) must route through an MCP server tool adapter.
6.  **Structured HTTP Returns:** Worker outputs must return validated Pydantic models defined in `schemas/`.
7.  **Fault Tolerance:** Implement retry mechanisms and error handling, returning clean failure records to the Master Agent instead of crashing.
8.  **Trace Logging:** Every agent step, tool call, and completion state must emit structured logs.
9.  **Single-Purpose LangGraph Nodes:** Nodes inside a LangGraph workflow should be scoped to a single logical operation, mirroring the reference scheduler steps.
10. **Preserve Determinism (No Replacing Logic with LLMs):** Keep business rules deterministic. Standard Pydantic validations, database constraints, scoring formulas, hard eligibility filters, idempotency matching, and retry counters must remain standard python code. LangChain/LLM calls must only be used where reasoning, synthesis, or interpretation is required.
11. **Transport vs. Business Error Isolation:** Transport failures (e.g., HTTP 503/504) must be handled differently from business failures (HTTP 200 with `execution_status="FAILED"`).
12. **Backward Compatibility:** All schemas and validation engines must remain backward compatible with Phase 4 baseline tests during migration.

---

## 5b. Worker Agent Reference Pattern

Every worker agent folder (e.g., `agents/agent6/`, `agents/agent7/`, `agents/agent8/`) should follow this standard, modular architectural design:

*   **`agent.py`:** The public worker interface. Implements the base `Agent` class and defines `run(context: WorkflowContext) -> AgentResponse`. Captures exceptions and reports status back to the Master Orchestrator.
*   **`validator.py`:** Handles pre-flight input and domain boundary validation for the input `WorkflowContext`.
*   **`scheduler.py` (or business logic executor):** Houses the core sequential workflow steps. Manages idempotency checkpoints via `context.step_data` to ensure re-entrancy and idempotency under retry execution.
*   **`tools.py`:** Adapter mapping raw MCP tool registry client calls into clean, typed Python interfaces.
*   **`compensation.py` (Optional):** Required only when the worker performs external side-effecting operations (such as booking appointments or writing to calendars) that may require rollback or compensating actions on database commit failure.

### Shared Patterns vs. Agent-Specific Business Logic

*   **Shared Patterns (Centralized):**
    *   Unified `WorkflowContext` data structures.
    *   `AgentResponse` output schemas and `ResponseBuilder` utilities.
    *   Centralized `event_bus`, `state_manager`, and `tool_registry`.
*   **Agent-Specific Business Logic (Localized):**
    *   Interviewer selection rules and roster search filters.
    *   Transcript scoring parsers, soft skills scorecards, and ranking weight formulas.

---

## 6. Master Agent Rules

The Master Agent (Orchestrator) is governed by these rules:

-   **Orchestration Ownership:** The Master Agent manages the pipeline state machine and determines transition logic.
-   **Workflow State Maintenance:** It updates database state flags when events occur (e.g., transitioning candidate state from `Screened` to `Scheduled`).
-   **Centralized Dispatch:** It formats task parameters, triggers worker agents, and validates worker outputs.
-   **Validation Checkpoints:** Validates inputs from external systems (Pipeline-1) and worker outputs before proceeding to next pipeline stages.
-   **MCP Management:** Serves as the central caller for shared database and security tools.
-   **Retry & Fallback Orchestration:** Manages retry limits and fallback paths (e.g., redirecting scheduling issues to human queues).
-   **HITL Suspensions:** Coordinates human-in-the-loop steps by saving current progress, suspending the workflow, and resuming upon approval.
-   **No Domain Logic:** The Master Agent must not contain scoring logic, scheduling heuristics, or resume analysis rules. It acts strictly as an orchestrator.

---

## 7. MCP Development Rules

-   **Integrate via MCP:** Direct HTTP requests or SDK integrations with external services (like Google Calendar API or SMTP mailers) are forbidden. All access must use MCP.
-   **Clean Interfaces:** MCP tools must declare clear input validation schemas and return predictable output structures.
-   **Robust Error Handling:** MCP servers must handle API outages gracefully, returning clean, typed error responses to the caller agent.
-   **Exponential Retry Support:** MCP tools that communicate with external web endpoints must support retry limits and backoff schedules.
-   **Reusable Tools:** Design MCP tools (e.g., database insert/updates) to be generic enough for reuse by different agents, while respecting defined access limits.

---

## 8. Database Rules

-   **Access via MCP:** Agents cannot instantiate PostgreSQL clients or run raw SQL statements. All database reads/writes must use Database MCP tools.
-   **No Raw SQL in Agents:** Agents consume abstract methods (e.g., `fetch_candidate_history`), keeping database engine specifics isolated inside the MCP server.
-   **Atomic Operations:** Multi-table writes must occur in single database transactions to prevent partial state updates.
-   **Contract Enforcement:** All CRUD operations must respect the limits defined in `database_contracts.md`.
-   **Access Permissions:** Worker agents must only call database tools they have explicit permission to access.
-   **Mutation Auditing:** Every database insert, update, or deletion must log the initiator (Master Agent, Agent 6, etc.) and candidate trace ID.

---

## 9. Logging Standards

To ensure observability, the following events must be logged using structured JSON logs:
-   **Workflow Lifecycle:** Start and completion of candidate pipelines.
-   **Agent Invocations:** Worker inputs, start times, completion times, and output statuses.
-   **MCP Tool Executions:** Tool name, parameters, execution status, and call latency.
-   **Validation Failures:** Payload verification mismatches, incomplete details, or incorrect schemas.
-   **Retries and Fallbacks:** Details of failed operations and fallback transitions.
-   **Human Interventions:** Handoff to human review queues, wait durations, and approval outputs.
-   **System Errors:** Exceptions, traceback alerts, and API outages.
-   **Trace ID Propagation:** Every log message must include the unique `trace_id` associated with the candidate.

> [!CAUTION]
> **No PII Logging:** Never log sensitive candidate details (such as personal phone numbers, salary expectations, or cleartext passwords) in plain text logs.

---

## 10. Error Handling Standards

Errors must be handled systematically using a structured escalation path:

```
  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
  │  Validation  ├──────>│ Retry Loop   ├──────>│ Fallback Path│
  │ Check Schemas│       │ (Exponential)│       │ (Alternative)│
  └──────────────┘       └──────────────┘       └──────┬───────┘
                                                       │
                                                       ▼
  ┌──────────────┐       ┌──────────────┐       ┌──────┴───────┐
  │    Resume    │<──────┤ Human Review ├<──────┤  Escalation  │
  │  Workflow    │       │ (HITL Queue) │       │ (Alert Admin)│
  └──────────────┘       └──────────────┘       └──────────────┘
```

1.  **Validation:** Input payloads are checked immediately. If schemas are invalid, execution is halted, and an alert is logged.
2.  **Retry:** Transient network or API errors trigger standard retry attempts with exponential backoff.
3.  **Fallback:** If retries fail, the agent executes an alternative action (e.g., sending a reschedule mail if automated calendar booking fails).
4.  **Escalation:** If fallbacks fail, the Master Agent alerts the recruiter and places the task in the human review queue.
5.  **Resume:** Once resolved or approved, the Master Agent resumes the workflow state.

---

## 11. Testing Standards

-   **Code Completeness:** No feature branch will be merged without corresponding test coverage.
-   **Unit Tests:** Must validate parsing functions, schema definitions, and helper tools in isolation.
-   **Integration Tests:** Must verify multi-step workflows (e.g., Master Agent receiving candidate details and triggering scheduling).
-   **Contract Tests:** Must verify that database inputs/outputs and MCP JSON payloads adhere to specifications.
-   **Mock MCP Tests:** External services and LLM completions must be mocked in test environments to ensure tests run reliably and quickly.
-   **Scenario Validation:** Test plans must cover success scenarios, failure scenarios, and human review pauses.

---

## 12. Documentation Rules

-   **Documentation-First:** Architectural, contract, or schema updates must be reviewed and merged into documentation files before modifying code.
-   **Synchronization:** Schema files (`schemas/`) and contracts (`contracts/`) must be kept in sync with the repository markdown documents.
-   **Status Transparency:** Maintain `README.md` to reflect the active development phase and configuration requirements.
-   **Single Source of Truth:** `architecture.md` is the final authority on system topology. Do not deploy code that deviates from this architecture.

---

## 13. Git & Version Control Rules

-   **Branch Protection:** Pushing directly to `main` or `develop` is forbidden. All development must occur on feature branches (e.g., `feature/agent7`).
-   **Commit Discipline:** Commits must be small, self-contained, and document a single change.
-   **Descriptive Commits:** Use structured messages (e.g., `feat(agent7): add resume analysis prompt templates`).
-   **Mandatory Pull Requests:** Merges into `develop` or `main` must go through a PR process.
-   **Collaborative Review:** PRs require reviews and approvals from designated owners before merge.

---

## 14. AI-Assisted Development Rules

When developing with the assistance of AI tools (e.g., Claude Code, Antigravity):
-   **Check Context Documents:** AI agents must read `project_context.md`, `architecture.md`, and `folder_structure.md` before writing code.
-   **No Custom Architecture:** AI tools must not create new architecture patterns, unapproved folders, or bypass orchestrator rules.
-   **Respect Contracts:** Generated code must strictly adhere to the schemas defined under `contracts/` and `schemas/`.
-   **Directory Isolation:** AI tools must only modify files in the folder assigned to the target task.
-   **Review Requirements:** All AI-generated code must undergo human review before merging.

---

## 15. Future Scalability

These guidelines ensure the project remains scalable:
-   **Modular Workers:** New interview stages are added by implementing a new stateless agent and registering it to the Master Agent.
-   **Decoupled Interfaces:** New integrations are added by implementing new MCP tools, keeping existing agent implementations unchanged.
-   **Model Independence:** Prompts are stored in text files, allowing developers to optimize templates for different LLM backends without altering code files.

---

## 16. Summary

This `DEVELOPMENT_RULES.md` document serves as the repository's development constitution. Every developer and AI assistant must comply with these guidelines before writing, reviewing, or merging code. Adhering to these rules ensures the consistency, maintainability, and long-term stability of the Recruitment Pipeline.
