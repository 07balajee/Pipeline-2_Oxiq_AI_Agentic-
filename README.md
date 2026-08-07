# OxiqAI HRMS – Recruitment Pipeline-2

OxiqAI HRMS is an enterprise-grade, agentic AI-powered Human Resource Management System. This repository houses **Pipeline-2 (Interview Management Pipeline)**, which manages candidate evaluation loops, automatic interview scheduling, technical and HR assessments, pool re-ranking, and orchestrates candidate selection.

---

## Overview

Pipeline-2 sits at the core of the OxiqAI recruitment lifecycle, between the screening and offer stages.
*   **Trigger:** Pipeline-2 begins execution after the Screening Pipeline (Pipeline-1) shortlists a candidate and pushes their context (`CandidateShortlisted` event, `POST /v1/workflow/start`).
*   **Execution:** Coordinates candidate schedules, parses technical and HR assessment logs, and dynamically re-ranks candidate pools based on real-time evaluation data.
*   **Handoff:** Pipeline-2 ends when a candidate's evaluation loop is finalized, handshaking selection details to the Offer Pipeline (Pipeline-3) via an `OfferRequested` event.

This repository focuses entirely on agentic orchestration and interview lifecycle management. The exact request/response payloads and event names for both handoffs are defined in [`api_contracts.md`](api_contracts.md) and [`workflow_contracts.md`](workflow_contracts.md).

---

## Pipeline Scope

The following architectural components are in-scope for this repository:

*   **Master Agent:** The central orchestrator routing candidate workflows.
*   **Agent 6 (Interview Invitation & Scheduling):** Manages calendar resources, sends email/chat notifications, and generates event links.
*   **Agent 7 (Technical Interview):** Evaluates technical metrics and standardizes technical scorecards.
*   **Agent 8 (HR Interview & Candidate Re-ranking):** Handles soft-skill evaluations and calculates dynamic candidate pool rankings.
*   **Shared MCP Layer:** Standardized Model Context Protocol clients/servers exposing database and external tool endpoints.
*   **Testing Suite:** Automated mock frameworks, contract tests, and distributed integration harnesses.

---

## High-Level Architecture

Pipeline-2 utilizes a strict Master-Agent topology as four independent FastAPI microservices. Workers are fully isolated from each other; all flow coordination is routed through the central Master Orchestrator.

```
       ┌────────────────────────┐
       │ Pipeline-1 (Screening) │
       └───────────┬────────────┘
                   │ Candidate Shortlist Push
                   ▼
       ┌────────────────────────┐
       │  Master Agent  (:8000) │◄────────────────────────┐
       └─────┬───────────┬──────┴─┐                       │
             │           │        │                       │
     Trigger │   Trigger │        │ Trigger               │
             ▼           ▼        ▼                       │
         ┌──────┐    ┌──────┐     ┌──────┐                │
         │  A6  │    │  A7  │     │  A8  │                │
         │:8001 │    │:8002 │     │:8003 │                │
         └──┬───┘    └──┬───┘     └──┬───┘                │
            │           │            │                    │
            └───────────┴────────────┴────────────────────┘
                       Execution Results Handback
                               │
                               ▼
                       ┌────────────────────────┐
                       │   Pipeline-3 (Offer)   │
                       └────────────────────────┘
```

> [!IMPORTANT]
> **Orchestration Rule:** Workers NEVER communicate directly (e.g., A6 to A7 is forbidden). The Master Agent is the sole coordinator, ensuring central audit logs and strict state transitions.

See [`architecture.md`](architecture.md) for the per-service component breakdown and [`master_agent.md`](master_agent.md) for the Master's internal orchestration logic (retry/fallback engine, HITL manager, event routing).

---

## Repository Structure

```
Pipeline-2/
├── agents/                # Sub-agent domain logic (master, agent6, agent7, agent8) + LangGraph graphs
├── services/               # Process-isolated FastAPI microservices (master_api, agent{6,7,8}_api)
├── mcp/                     # MCP clients/servers (database, calendar, meet, document, notification, resume)
├── mcp_server_extracted/    # Vendored real Recruitment DB MCP server (used when MCP_DB_MODE=real)
├── schemas/                 # Shared Pydantic request/response models
├── shared/                  # Cross-cutting utilities (config, context, events, logging, registries)
├── scripts/                 # Operational scripts (e.g. live 4-service smoke test)
└── tests/                   # Unit, contract, graph, API, and distributed integration tests
```

---

## Status

Master, Agent 6, Agent 7, and Agent 8 are all implemented as independent FastAPI + LangGraph services, wired together through the Master's HTTP dispatcher, with a real (non-mock) Database MCP integration available alongside the mock. The automated test suite (contract, graph, API, and distributed end-to-end/failure tests) is green.

Remaining before this is production-ready:
- End-to-end validation against the live Pipeline-1 intake and Pipeline-3 handoff (currently only exercised via mocks/tests).
- CI pipeline and containerized deployment (not yet set up).

---

## Technology Stack

*   **Core:** Python 3.11+ / FastAPI
*   **Orchestration:** LangGraph (per-service state graphs, Master-level checkpointing)
*   **Database:** PostgreSQL (transactional states), via Recruitment DB MCP
*   **Interface Protocols:** Model Context Protocol (MCP)
*   **LLM Engine:** Claude (Anthropic API)

---

## Core Design Principles

*   **Master-Agent Architecture:** Strict centralization of logic workflows.
*   **Event-Driven Workflow:** Workflows trigger based on explicit transaction events.
*   **Contract-First Development:** Interface boundaries are defined as code types before logic implementation.
*   **MCP-First Integration:** All agent actions use standardised MCP tool calls.
*   **Human-in-the-Loop:** Sensitive lifecycle choices require manual approval suspension.
*   **Loose Coupling:** Minimal assumptions made between individual system components.
*   **Observability:** Uniform log telemetry across all agents.

---

## Repository Rules

1.  **No Peer Agent Communication:** Sub-agents must never call or pass messages directly to other sub-agents.
2.  **DB Access Isolation:** Direct client calls or SQL bypasses are forbidden. All database tasks go through the Database MCP.
3.  **Contract Stability:** Changes to the documents below require review, since Pipeline-1 and Pipeline-3 integrate against them.

---

## Documentation Index

| Document | Purpose |
| :--- | :--- |
| **[`architecture.md`](architecture.md)** | System topology, per-service component breakdown, architectural isolation rules. |
| **[`master_agent.md`](master_agent.md)** | Master orchestrator internals: routing, retry/fallback, HITL, sequence & decision diagrams. |
| **[`api_contracts.md`](api_contracts.md)** | REST endpoints for the Master and worker services — the surface Pipeline-1/Pipeline-3 integrate against. |
| **[`workflow_contracts.md`](workflow_contracts.md)** | State machine, idempotency tokens, and failure-category mapping for orchestration handoffs. |
| **[`agent_contracts.md`](agent_contracts.md)** | Input/output contracts, triggers, and boundary conditions for Agents 6, 7, and 8. |
| **[`database_contracts.md`](database_contracts.md)** | Database CRUD maps, column allowances, and transaction rules. |
| **[`mcp_contracts.md`](mcp_contracts.md)** | Input/output schemas for internal and external MCP tools. |
| **`CLAUDE.md`** | AI-assisted engineering memory for this repo (conventions, gotchas, decisions). |

---

## Getting Started

1.  Copy `.env.example` to `.env` and adjust service URLs / `MCP_DB_MODE` (`mock` for local dev, `real` for a live DB).
2.  `pip install -r requirements.txt`
3.  Run the test suite: `pytest -q`
4.  For a live multi-process smoke test across all four services, see `scripts/smoke_test_4services.py`.
