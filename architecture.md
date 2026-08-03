# Pipeline-2 Architecture Reference (Phase 5.8 Frozen Baseline)

## High-Level System Diagram

```
Pipeline-1 / External Client
          │
          ▼
 Master FastAPI :8000
          │
     Master LangGraph
          │
     HTTP Dispatcher
     ┌────┼────┐
     ▼    ▼    ▼
   :8001 :8002 :8003
 Agent6 Agent7 Agent8
 Graph  Graph  Graph
     \    │    /
        MCP Layer (Database, Calendar, Resume, Document, Notification, Meet)
```

---

## Service Component Breakdown

### 1. Master Agent & Service (:8000)
- **Role**: Central orchestrator.
- **Components**: `services/master_api/` (FastAPI), `agents/master/master_agent.py` (Facade), `agents/master/graph/` (LangGraph `StateGraph`).
- **Dependencies**: Dispatches to Agent 6, 7, and 8 over HTTP via `AgentServiceClient`. Contains **ZERO direct imports** of `InterviewInvitationAgent`, `TechnicalInterviewAgent`, or `HRInterviewAgent`.
- **Checkpointing**: MemorySaver checkpointer for workflow state persistence and human approval resumes.

### 2. Agent 6 — Interview Invitation Agent (:8001)
- **Role**: Candidate interview scheduling.
- **Components**: `services/agent6_api/` (FastAPI), `agents/agent6/graph/` (LangGraph).
- **Dependencies**: Interacts with Calendar MCP, Meet MCP, Notification MCP, Database MCP.

### 3. Agent 7 — Technical Evaluation Agent (:8002)
- **Role**: Technical score evaluation.
- **Components**: `services/agent7_api/` (FastAPI), `agents/agent7/graph/` (LangGraph).
- **Dependencies**: Interacts with Resume MCP, Database MCP.

### 4. Agent 8 — HR Assessment & Candidate Re-ranking Agent (:8003)
- **Role**: HR soft skills evaluation and cohort re-ranking.
- **Components**: `services/agent8_api/` (FastAPI), `agents/agent8/graph/` (LangGraph).
- **Dependencies**: Interacts with Database MCP.

---

## Architectural Rules

1. **Master Isolation**: Master code (`agents/master/**` and `services/master_api/**`) communicates with worker agents exclusively via HTTP (`AgentServiceClient`). Worker class imports are strictly forbidden.
2. **Worker Peer Isolation**: Worker agents are strictly isolated. No worker imports peer worker modules.
3. **MCP Layer Boundaries**: Workers interact with external systems via MCP clients (`shared/registry/tool_registry.py`). Workers never call Master or peer worker APIs.
4. **Configuration Drive**: Service URLs, timeouts, and retry parameters are driven by `Settings` (`shared/config/settings.py`).
