# OxiqAI HRMS Recruitment Pipeline-2 — Project Context

## Current Architectural Phase: PHASE 5.8 (DISTRIBUTED ARCHITECTURE FROZEN)

OxiqAI HRMS Recruitment Pipeline-2 has completed Phase 5.8 (Distributed Integration, Observability & Architecture Freeze).

### Baseline Status
- **Architecture**: Distributed 4-Microservice Microservice Architecture (Master API :8000, Agent 6 API :8001, Agent 7 API :8002, Agent 8 API :8003).
- **Orchestration**: Process-isolated Master LangGraph state engine + worker-local stateless LangGraph state engines (`agents/agent6/graph/`, `agents/agent7/graph/`, `agents/agent8/graph/`).
- **Master Isolation**: Master runtime (`agents/master/**` & `services/master_api/**`) contains **ZERO worker class imports**.
- **Observability & Readiness**: Master readiness endpoint `GET /v1/readiness` monitors dependency health and latency across all three worker microservices.
- **Contract Boundary**: All Master -> Worker communications exchange `WorkflowContext` (HTTP POST) -> `AgentResponse`.
- **Automated Test Baseline**: 100% green automated test suite enforcing AST architecture invariants, cross-service failure modes, and end-to-end integration flows.

---

## Distributed Service Topology

| Service | Port | Base URL | LangGraph Engine | Responsibilities |
|---------|------|----------|------------------|------------------|
| **Master Service** | 8000 | `http://127.0.0.1:8000` | Master LangGraph | Pipeline orchestration, state management, event routing, human approval interrupts, readiness monitoring |
| **Agent 6 Service** | 8001 | `http://127.0.0.1:8001` | Agent 6 LangGraph | Interview scheduling, candidate invitation, calendar slot reservation |
| **Agent 7 Service** | 8002 | `http://127.0.0.1:8002` | Agent 7 LangGraph | Technical evaluation, resume keyword parsing, technical scoring |
| **Agent 8 Service** | 8003 | `http://127.0.0.1:8003` | Agent 8 LangGraph | Soft skills HR assessment, candidate pool cohort re-ranking |
