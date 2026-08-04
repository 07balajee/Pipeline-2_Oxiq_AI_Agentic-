# OxiqAI Recruitment Pipeline-2 — AI Engineering Memory

> **IMPORTANT MEMORY MAINTENANCE RULES FOR AI AGENTS**
> 1. **Read CLAUDE.md** before modifying the repository.
> 2. For architecture-sensitive work, also read the authoritative documents referenced in Section 14.
> 3. After completing a **SIGNIFICANT** implementation phase, update CLAUDE.md if any of these changed:
>    - architecture, service boundaries, contracts, agent responsibilities, MCP integrations, configuration, testing baseline, known limitations, current task/status.
> 4. Do **NOT** update CLAUDE.md for trivial code edits, formatting changes, or temporary debugging.
> 5. **NEVER store secrets**: API keys, passwords, Supabase service keys, access tokens, or personal credentials.
> 6. Keep CLAUDE.md concise. Do not allow it to become a chronological development diary.
> 7. **Replace** outdated information rather than endlessly appending historical notes.
> 8. When changing an architectural fact, update the authoritative documentation **AND** CLAUDE.md.
> 9. **Never** use CLAUDE.md as justification to violate current code/contracts. Verify important assumptions against the repository.

---

## 1. Project Purpose

**OxiqAI Recruitment Pipeline-2** is the middle-stage automated candidate interviewing and evaluation engine within the OxiqAI HRMS ecosystem. It sits between:
- **Pipeline-1**: Top-of-funnel intake, screening, and candidate shortlisting.
- **Pipeline-3**: Offer generation, compensation benchmarking, and onboarding.

Pipeline-2 receives shortlisted candidates, orchestrates interview scheduling (Agent 6), technical assessment scoring (Agent 7), and HR evaluation / candidate pool re-ranking (Agent 8), returning structured evaluation results and state transitions.

---

## 2. Current Architecture

Pipeline-2 uses a **frozen 4-microservice distributed architecture** (Phase 5.8 baseline):

```
External Client / Pipeline-1
        │
        ▼
Master FastAPI :8000
        │
Master LangGraph
        │
HTTP Dispatcher (AgentServiceClient)
        │
  ┌─────┼─────┐
  │     │     │
  ▼     ▼     ▼
Agent6 Agent7 Agent8
:8001  :8002  :8003
  │      │      │
Worker-local LangGraph engines
  │      │      │
MCP abstraction layer / services (ToolRegistry)
  │
External systems / Recruitment DB / Supabase
```

### Architectural Principles & Invariants
- **Master -> Worker Communication**: Strictly HTTP via REST APIs using `AgentServiceClient`.
- **Master Orchestration**: Managed by process-isolated Master LangGraph state engine (`agents/master/graph/`) with `MemorySaver` checkpointer and HITL interrupt support.
- **Worker Internal Orchestration**: Driven by worker-local stateless LangGraph state engines (`agents/agent6/graph/`, `agents/agent7/graph/`, `agents/agent8/graph/`).
- **Worker Tool Access**: Workers interact with external systems exclusively via MCP abstractions (`shared/registry/tool_registry.py`).
- **Worker Peer Isolation**: Workers MUST NOT directly import or call peer workers.
- **Master Isolation**: Master MUST NOT directly import worker implementations or sub-agent packages (`agents.agent6`, `agents.agent7`, `agents.agent8`).

---

## 3. Service Map

| Service | Port | Base URL | Endpoints | Primary Responsibilities |
|---|---|---|---|---|
| **Master API** | `:8000` | `http://127.0.0.1:8000` | `GET /v1/health`<br>`GET /v1/readiness`<br>`POST /v1/workflow/start`<br>`POST /v1/workflow/event`<br>`POST /v1/workflow/resume`<br>`GET /v1/workflow/{id}` | Pipeline orchestration, state routing, HITL approval interrupts, worker dependency monitoring. |
| **Agent 6 API** | `:8001` | `http://127.0.0.1:8001` | `GET /v1/agents/agent6/health`<br>`POST /v1/agents/agent6/execute` | Candidate interview scheduling, interviewer slot selection, calendar invite generation. |
| **Agent 7 API** | `:8002` | `http://127.0.0.1:8002` | `GET /v1/agents/agent7/health`<br>`POST /v1/agents/agent7/execute` | Technical assessment parsing, skill criteria scoring, technical scorecard generation. |
| **Agent 8 API** | `:8003` | `http://127.0.0.1:8003` | `GET /v1/agents/agent8/health`<br>`POST /v1/agents/agent8/execute` | HR soft-skills evaluation, candidate score consolidation, cohort re-ranking. |

---

## 4. Worker Responsibilities

### Agent 6 — InterviewInvitationAgent
- **Domain**: Interview scheduling & booking workflow.
- **Tasks**: Deterministic input validation, interviewer availability matching/scoring, calendar slot selection, Google Meet/Calendar invite creation, notification dispatch, cancellation/reschedule processing, and Online -> Offline scheduling fallback.
- **Isolation**: Manages only scheduling data and roster tables.

### Agent 7 — TechnicalInterviewAgent
- **Domain**: Technical interview evaluation.
- **Tasks**: Parses technical transcripts/notes, evaluates candidates against job technical criteria, computes competency scores, generates technical scorecards.
- **Isolation**: Modifies only technical evaluation records.

### Agent 8 — HRInterviewAgent
- **Domain**: HR soft skills & cohort pool re-ranking.
- **Tasks**: Assesses communication and cultural fit, merges technical + HR evaluations into a consolidated score, re-ranks candidates in the job cohort pool.
- **Isolation**: Modifies only HR evaluations and pool ranking matrices.

---

## 5. Agent 6 Reference Status

**Agent 6 is the frozen reference worker implementation.** All future worker implementations (Agent 7 and Agent 8) must follow Agent 6's structural patterns.

### Completed Reference Capabilities
- **Deterministic Validation**: Strict input boundary validation.
- **Interviewer Selection & Scoring**: Algorithmic matching based on skills and capacity.
- **Slot Selection**: Optimal window reservation (Online / Offline modes).
- **HITL Approval**: Thread pause & resume mechanism for human slot overrides.
- **Rejection & Recommendation Retry**: Built-in operational fallback loops.
- **Operation-Level Retry & Idempotency Checkpoints**: Prevents duplicate scheduling actions via step data keys (`interview_scheduled_committed`).
- **Compensation Handling**: Rollback of prepared state upon execution failures.
- **Online -> Offline Fallback Proposal**: Graceful fallback when video conference availability is restricted.
- **FastAPI Service Boundary**: Clean REST wrapper around worker execution.
- **Internal LangGraph Execution**: Local graph handling node transitions.
- **MCP-Based Tool Architecture**: Decoupled tool integration using `ToolRegistry`.

> [!IMPORTANT]
> Do **NOT** rewrite or redesign Agent 6 unless a task explicitly requires it.

---

## 6. MCP Architecture

MCP (Model Context Protocol) abstraction layer isolates worker business logic from external infrastructure.

### Tool Architecture Abstractions
Workers access external capabilities via `shared/registry/tool_registry.py` and `shared/interfaces/tool.py`:
- **Database MCP**: `RealRecruitmentDBMCPClient` / `DatabaseMCPClient` (`mcp/database/`)
- **Resume MCP**: `ResumeMCPClient` (`mcp/resume/`)
- **Calendar MCP**: `CalendarMCPClient` (`mcp/calendar/`)
- **Meet MCP**: `MeetMCPClient` (`mcp/meet/`)
- **Document MCP**: `DocumentMCPClient` (`mcp/document/`)
- **Notification MCP**: `NotificationMCPClient` (`mcp/notification/`)

### Integration Verification Status
- **Recruitment Database MCP**: Verified live stdio transport client (`RealRecruitmentDBMCPClient`) calling the FastMCP server (`mcp_server_extracted/MCP_recruitementDB_Server/server.py`) connected to live Supabase PostgreSQL (with automatic JSON twin fallback when DB is unreachable). Controlled via `MCP_DB_MODE` ("mock" | "real").
- **Calendar, Meet, Resume, Document, Notification MCPs**: Local mock/in-memory MCP client implementations verified for unit & integration testing.

```
Agent Worker
    │
    ▼
ToolRegistry
    │
    ▼
RealRecruitmentDBMCPClient  (when MCP_DB_MODE="real")
    │
    ▼  (stdio transport via official mcp Python SDK)
Common Recruitment DB MCP Server (server.py)
    │
    ▼
Supabase PostgreSQL DB
```

> [!NOTE]
> **MCP vs. LLM Independence**: MCP is an infrastructure protocol and tool abstraction layer. It does **NOT** require an LLM API (Groq/OpenAI/Anthropic). LLM provider configuration and MCP tool connectivity are entirely separate concerns.

---

## 7. Recruitment DB MCP Notes

### Verified FastMCP Tool Operations
- `query_resource`: Reads table rows (`candidates`, `jobs`, `interviews`, `technical_evaluations`, `hr_evaluations`) with ACL checks.
- `write_resource`: Executes insert/update operations (`op="insert"` or `op="update"`).
- `transition_status`: Safely executes state transitions on entity tables with transition auditing.

### Compatibility Layer Note
Pipeline-2 workers use a `prepare` -> `commit` interface (`prepare_interview`, `prepare_update`, `prepare_insert`, `commit`, `rollback`). In `RealRecruitmentDBMCPClient`, `prepare_*` queues operation descriptors in memory (`_prepared_descriptors`) and `commit()` executes them sequentially via `write_resource` and `transition_status`. This is a **client-side compatibility adapter**, NOT a native 2-Phase Commit (2PC) distributed database transaction.

### Agent Access Control List (ACL) Identifiers
- **Agent 6**: `agent_6` (access to `candidates`, `jobs`, `interviews`, `schedule_roster`)
- **Agent 7**: `agent_7` (access to `candidates`, `jobs`, `interviews`, `technical_evaluations`)
- **Agent 8**: `agent_8` (access to `candidates`, `jobs`, `technical_evaluations`, `hr_evaluations`, `candidate_rankings`)

### Key Schema Mappings & Differences
- Candidate `status` in database is mapped to `pipeline_state` in Pipeline-2's `CandidateContext`.
- Job `title` in database is mapped to `job_title` in Pipeline-2's `JobData`.
- Candidate/Job primary keys `id` map to `candidate_id` / `job_id`.

---

## 8. Core Contracts

All service and worker boundaries communicate using standardized Pydantic models:

- **Input Contract**: `WorkflowContext` (`shared/context/workflow_context.py`) containing `workflow_id`, `candidate`, `current_state`, `previous_state`, `step_data`, `history`, and `metadata`.
- **Output Contract**: `AgentResponse` (`schemas/agent_response.py`) containing `execution_status` (`SUCCESS` | `FAILED`), `generated_event`, `updated_state`, `summary`, `errors`, `warnings`, `suggested_action`, and `metadata`.

### Authoritative Contract References
- `agent_contracts.md`: Detailed agent input/output models and ownership matrix.
- `api_contracts.md`: REST API endpoint schemas and status codes.
- `workflow_contracts.md`: State machine event map and idempotency keys.

---

## 9. Failure Model

Pipeline-2 employs a strict **two-level failure recovery model**:

```
 Level 1: Worker Operational Recovery (Local)
   ├── MCP / Tool retries (transient network failures)
   ├── Internal node retry counters (operation loop bounds)
   └── Idempotency protection (step_data token checks)

 Level 2: Master Workflow Recovery (Global Orchestrator)
   ├── Transport retries (AgentTransportError handling in HTTP Dispatcher)
   ├── Workflow fallback routing (e.g. Online -> Offline scheduling)
   ├── Human-in-the-Loop escalation (workflow pause & alert)
   └── Execution halt & state preservation
```

- **Level 1** handles worker-local retries, MCP re-connection, and step-level idempotency without escalating to Master.
- **Level 2** handles microservice transport failures, HTTP timeouts, contract invalidations, and workflow-level pauses/resumes.
- **Rule**: Workers must never attempt global workflow recovery; Master must never handle local tool retries.

---

## 10. Configuration

Runtime configuration is centralized in `shared/config/settings.py` (`Settings` class) backed by `.env`:

### Key Configuration Parameters
- `master_service_url`: `http://127.0.0.1:8000`
- `agent6_service_url`: `http://127.0.0.1:8001`
- `agent7_service_url`: `http://127.0.0.1:8002`
- `agent8_service_url`: `http://127.0.0.1:8003`
- `agent_http_timeout_seconds`: `30.0`
- `health_http_timeout_seconds`: `3.0`
- `max_retry_attempts`: `3`
- `mcp_db_mode`: `"mock"` (default unit testing) or `"real"` (live Supabase integration)
- `mcp_db_server_path`: `"mcp_server_extracted/MCP_recruitementDB_Server/server.py"`
- `mcp_db_transport`: `"stdio"`

> [!CAUTION]
> Never place actual API keys, passwords, or database secrets in `CLAUDE.md` or git-committed files. Use `.env`.

---

## 11. Architecture Rules — MUST NOT VIOLATE

1. **Master Isolation**: Master (`agents/master/**`, `services/master_api/**`) MUST NOT import worker classes or packages (`agents.agent6`, `agents.agent7`, `agents.agent8`).
2. **Worker Peer Isolation**: Worker agents MUST NOT import peer worker modules.
3. **Worker Master Isolation**: Workers MUST NOT import Master modules.
4. **HTTP Transport Boundary**: Master -> Worker communication MUST use HTTP via `AgentServiceClient`.
5. **MCP Tool Access**: Worker -> external tools MUST use approved MCP abstractions via `ToolRegistry`.
6. **Contract Integrity**: `WorkflowContext` and `AgentResponse` schemas MUST remain strictly compatible across service boundaries.
7. **No Unrequested Logic Modifications**: Do NOT modify frozen business logic unless explicitly requested.
8. **Centralized Configuration**: All settings MUST be driven by `shared/config/settings.py`.
9. **No Hardcoded Credentials**: Secrets must be loaded from environment variables.
10. **Preserve Idempotency**: External side effects (database writes, calendar reservations) MUST check idempotency keys before execution.
11. **Deterministic Business Logic**: Keep deterministic validation and selection logic deterministic; do NOT introduce unnecessary LLM calls where structured algorithms suffice.

> Enforced automatically by AST invariant tests in `tests/test_architecture_invariants.py`.

---

## 12. Testing Baseline

Current verified automated test baseline (Run date: August 2026):

```
====================== 165 passed, 400 warnings in 38.97s ======================
```

### Core Focused Test Suites
- `tests/test_architecture_invariants.py`: AST validation enforcing Master and worker isolation.
- `tests/test_agent6.py`: Agent 6 domain unit logic tests.
- `tests/test_agent6_graph.py`: Agent 6 local LangGraph workflow tests.
- `tests/test_agent6_api.py`: Agent 6 FastAPI service endpoint tests.
- `tests/test_agent7_graph.py` & `tests/test_agent7_api.py`: Agent 7 graph and FastAPI tests.
- `tests/test_agent8_graph.py` & `tests/test_agent8_api.py`: Agent 8 graph and FastAPI tests.
- `tests/test_master_graph.py` & `tests/test_master_api.py`: Master LangGraph and FastAPI tests.
- `tests/test_real_db_mcp_adapter.py`: `RealRecruitmentDBMCPClient` FastMCP stdio client adapter tests.
- `tests/test_distributed_failures.py`: Cross-service network error & recovery tests.
- `tests/test_distributed_e2e.py`: End-to-end 4-service pipeline integration tests.

---

## 13. Common Development Commands

### Run Full Test Suite
```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

### Run Microservices (Separate Terminals)
```bash
# Terminal 1: Master API (:8000)
PYTHONPATH=. uvicorn services.master_api.app:app --port 8000 --reload

# Terminal 2: Agent 6 API (:8001)
PYTHONPATH=. uvicorn services.agent6_api.app:app --port 8001 --reload

# Terminal 3: Agent 7 API (:8002)
PYTHONPATH=. uvicorn services.agent7_api.app:app --port 8002 --reload

# Terminal 4: Agent 8 API (:8003)
PYTHONPATH=. uvicorn services.agent8_api.app:app --port 8003 --reload
```

### Check Master Service Readiness
```bash
curl http://127.0.0.1:8000/v1/readiness
```

### Live 4-Service Network Smoke Test
```bash
PYTHONPATH=. python3 scripts/smoke_test_4services.py
```

### Live Real Recruitment DB MCP Verification
```bash
PYTHONPATH=. python3 scripts/verify_real_db_mcp.py
```

---

## 14. Authoritative Documentation

`CLAUDE.md` is an operational index and high-level memory file. For detailed specifications, refer to:

- `project_context.md`: Project architecture freeze status & phase history.
- `architecture.md`: Full architectural breakdown & system topologies.
- `agent_contracts.md`: Complete Pydantic schemas, ownership matrix, and payload details.
- `api_contracts.md`: REST API endpoint specification.
- `workflow_contracts.md`: State machine transitions, event definitions, and transport error mappings.
- `development_rules.md`: Detailed architectural rules and coding constraints.
- `folder_structure.md`: Complete repository layout index.
- `team_roles.md`: Developer ownership boundaries, branch strategies, and PR workflow.

---

## 15. Current Project Status

### Completed Architecture Milestones
- [x] **Phase 5.8 Distributed Architecture Freeze**: 4 process-isolated microservices (:8000, :8001, :8002, :8003).
- [x] **Master Orchestration**: Master LangGraph engine with zero worker imports.
- [x] **Worker Microservices**: Independent FastAPI servers for Agents 6, 7, and 8.
- [x] **Worker Local Graphs**: LangGraph state machine engines in each worker.
- [x] **Recruitment DB MCP Integration**: `RealRecruitmentDBMCPClient` connected via stdio transport to `MCP_recruitementDB_Server/server.py` with live Supabase PostgreSQL verification.
- [x] **Automated Test Baseline**: 100% pass rate across 165 unit, integration, invariant, and failure tests.

---

## 16. Current Work / Next Task

- **Current task**: Root `CLAUDE.md` memory file creation and freeze maintenance
- **Status**: Completed baseline audit & file creation
- **Last verified test baseline**: 165 passed / 0 failed (165 total tests)
- **Known blockers**: None
- **Next action**: Maintain `CLAUDE.md` upon subsequent architecture or contract modifications

---

> **IMPORTANT MEMORY MAINTENANCE RULES FOR AI AGENTS**
> 1. **Read CLAUDE.md** before modifying the repository.
> 2. For architecture-sensitive work, also read the authoritative documents referenced in Section 14.
> 3. After completing a **SIGNIFICANT** implementation phase, update CLAUDE.md if any of these changed:
>    - architecture, service boundaries, contracts, agent responsibilities, MCP integrations, configuration, testing baseline, known limitations, current task/status.
> 4. Do **NOT** update CLAUDE.md for trivial code edits, formatting changes, or temporary debugging.
> 5. **NEVER store secrets**: API keys, passwords, Supabase service keys, access tokens, or personal credentials.
> 6. Keep CLAUDE.md concise. Do not allow it to become a chronological development diary.
> 7. **Replace** outdated information rather than endlessly appending historical notes.
> 8. When changing an architectural fact, update the authoritative documentation **AND** CLAUDE.md.
> 9. **Never** use CLAUDE.md as justification to violate current code/contracts. Verify important assumptions against the repository.
