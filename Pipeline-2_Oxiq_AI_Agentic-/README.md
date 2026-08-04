# OxiqAI HRMS – Recruitment Pipeline-2

OxiqAI HRMS is an enterprise-grade, agentic AI-powered Human Resource Management System. This repository houses the development of **Pipeline-2 (Interview Management Pipeline)**, which manages candidate evaluation loops, automatic interview scheduling, technical and HR assessments, pool re-ranking, and orchestrates candidate selection pipelines.

---

## Overview

Pipeline-2 sits at the core of the OxiqAI recruitment lifecycle.
*   **Trigger:** Pipeline-2 begins execution after the Screening Pipeline (Pipeline-1) shortlists a candidate and pushes their context.
*   **Execution:** Coordinates candidate schedules, parses technical and HR assessment logs, and dynamically re-ranks candidate pools based on real-time evaluation data.
*   **Handoff:** Pipeline-2 ends when a candidate's evaluation loop is finalized, handshaking details to the Offer Pipeline (Pipeline-3).

This repository focuses entirely on agentic orchestration and interview lifecycle management.

---

## Pipeline Scope

The following architectural components are in-scope for development within this repository:

*   **Master Agent:** The central orchestrator routing candidate workflows.
*   **Agent 6 (Interview Invitation & Scheduling):** Manages calendar resources, sends email/chat notifications, and generates event links.
*   **Agent 7 (Technical Interview):** Evaluates technical metrics and standardizes technical scorecards.
*   **Agent 8 (HR Interview & Candidate Re-ranking):** Handles soft-skill evaluations and calculates dynamic candidate pool rankings.
*   **Shared MCP Layer:** Standardized Model Context Protocol servers exposing database and external tool endpoints.
*   **Database Contracts:** SQL schemas and transaction definitions.
*   **Workflow Contracts:** Payloads governing pipeline handoffs and worker communication.
*   **Prompt Definitions:** Isolated LLM system instructions, templates, and guardrails.
*   **Testing Suite:** Automated mock frameworks and integration test harnesses.

---

## High-Level Architecture

Pipeline-2 utilizes a strict Master-Agent topology. Workers are fully isolated from each other; all flow coordination is routed through the central Master Orchestrator.

```
       ┌────────────────────────┐
       │ Pipeline-1 (Screening) │
       └───────────┬────────────┘
                   │ Candidate Shortlist Push
                   ▼
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
                               ▼
                       ┌────────────────────────┐
                       │   Pipeline-3 (Offer)   │
                       └────────────────────────┘
```

> [!IMPORTANT]
> **Orchestration Rule:** Workers NEVER communicate directly (e.g., A6 to A7 is forbidden). The Master Agent is the sole coordinator, ensuring central audit logs and strict state transitions.

---

## Repository Structure

The planned folder structure is organized to isolate logic, prompts, and interfaces:

```
Pipeline-2/
├── agents/             # Sub-agent packages (master, agent6, agent7, agent8)
├── contracts/          # Workflow, database, and MCP contract definitions
├── prompts/            # Isolated prompt template text files (.txt / .json)
├── schemas/            # Pydantic models for request/response serialization
├── mcp/                # Local MCP server configurations and custom tools
├── shared/             # Shared utilities (logging, decorators, exceptions)
├── tests/              # Unit, integration, and mock test suites
└── docs/               # System and API design specifications
```

---

## Development Phases

We follow a strict, non-skipping software development lifecycle:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Phase 1 │───>│ Phase 2 │───>│ Phase 3 │───>│ Phase 4 │───>│ Phase 5 │───>┐
│ Freeze  │    │ Freeze  │    │ Master  │    │ Agent 6 │    │ Agent 7 │    │
│  Arch   │    │Contracts│    │  Agent  │    │(Sched)  │    │ (Tech)  │    │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘    │
                                                                           │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐                   │
│ Phase 9 │<───│ Phase 8 │<───│ Phase 7 │<───│ Phase 6 │<──────────────────┘
│  Prod   │    │ Testing │    │ Integr- │    │ Agent 8 │
│         │    │         │    │  ation  │    │  (HR)   │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

1.  **Phase 1: Freeze Architecture:** Setup system boundary definitions and project constraints (Current Phase).
2.  **Phase 2: Freeze Contracts:** Validate database schemas, MCP schemas, and event flow structures.
3.  **Phase 3: Master Agent:** Build the core FastAPI endpoint structure and orchestrator routing loop.
4.  **Phase 4: Build Agent 6:** Implement scheduling workflow tools and calendar synchronization.
5.  **Phase 5: Build Agent 7:** Implement technical assessment parsing and scorecards.
6.  **Phase 6: Build Agent 8:** Implement HR screening evaluation and candidate pool re-ranking algorithms.
7.  **Phase 7: Integration:** Connect Master Agent to worker agents and verify workflow loops.
8.  **Phase 8: Testing:** End-to-end simulation runs, load tests, and edge-case validations.
9.  **Phase 9: Production:** Final deployment.

---

## Technology Stack

*   **Core:** Python 3.11+ / FastAPI
*   **Database:** PostgreSQL (transactional states)
*   **Interface Protocols:** Model Context Protocol (MCP) SDK
*   **LLM Engine:** Claude (Anthropic API / Bedrock)
*   **Environment & Tooling:** Git, GitHub, Docker (planned containerization)

---

## Core Design Principles

*   **Master-Agent Architecture:** Strict centralization of logic workflows.
*   **Event-Driven Workflow:** Workflows trigger based on explicit transaction events.
*   **Contract-First Development:** Interface boundaries are defined as code types before logic implementation.
*   **MCP-First Integration:** All agent actions use standardised MCP tool calls.
*   **Human-in-the-Loop:** Sensitive lifecycle choices require manual approval suspension.
*   **Loose Coupling:** Minimal assumptions made between individual system components.
*   **Scalable Design:** Straightforward extension paths for future interview modules.
*   **Observability:** Uniform log telemetry across all agents.

---

## Repository Rules

1.  **No Peer Agent Communication:** Sub-agents must never call or pass messages directly to other sub-agents.
2.  **DB Access Isolation:** Direct client calls or SQL bypasses are forbidden. All database tasks go through the Database MCP.
3.  **Contract Immutability:** Changes to files under `contracts/` require formal design review.
4.  **Documentation-First Development:** No feature code or prompts may be changed without updating corresponding architectural specifications.

---

## Documentation Index

| Document | Purpose |
| :--- | :--- |
| **[project_context.md](file:///Users/neemaysmac/Desktop/Pipeline-2/project_context.md)** | Root context, rules, boundaries, and system boundaries. |
| **`architecture.md`** | Master sequence diagrams, routing states, and system topology. |
| **`folder_structure.md`** | File organization rules and namespace definitions. |
| **`team_roles.md`** | Owner assignment by agent component and codebase review rights. |
| **`development_rules.md`** | Git branching, testing expectations, styling, and checklist templates. |
| **`database_contracts.md`** | Strict database CRUD maps, column allowances, and transactions. |
| **`mcp_contracts.md`** | System input/output schemas for internal and external MCP tools. |
| **`workflow_contracts.md`** | Serialization schemas for orchestration handoffs. |
| **`agent_contracts.md`** | Input, output, triggers, and boundary conditions for agents 6, 7, and 8. |
| **`master_agent.md`** | Routing logical flow, classification prompts, and orchestration error handlers. |

---

## Getting Started

This repository is currently in the **Phase 1: Architecture & Contract Freeze** stage. 

*   Implementation will begin only after all documentation index files are frozen.
*   Check the [project_context.md](file:///Users/neemaysmac/Desktop/Pipeline-2/project_context.md) file to understand the developer boundaries before proposing updates.

---

## Future Roadmap

*   [ ] Complete the architecture documentation freeze (Phase 1)
*   [ ] Finalize contract definitions for the Database and MCP interfaces (Phase 2)
*   [ ] Setup and launch the Master Orchestrator shell endpoints
*   [ ] Deploy the custom Database and Calendar MCP servers
*   [ ] Integrate worker agents with the central router
*   [ ] Execute full end-to-end mock dry runs and test validations
