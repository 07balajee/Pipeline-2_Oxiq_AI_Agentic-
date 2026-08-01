# OxiqAI HRMS - Recruitment Pipeline-2
## REPOSITORY BLUEPRINT & FOLDER STRUCTURE SPECIFICATION

---

## 1. Purpose

The repository layout is frozen prior to execution to establish a consistent codebase structure. A formal blueprint:
- **Prevents Merge Conflicts:** Multiple developers can work on distinct agents simultaneously in isolated namespaces.
- **Enforces Separation of Concerns:** Segregates system configuration, raw inputs (prompts), typing definitions (schemas), interfaces (contracts), and implementation logic.
- **Ensures Agent Modularity:** Forces workers to remain stateless and self-contained.
- **Facilitates Onboarding:** Standardizes file discovery so new developers can locate code, prompts, and tests easily.
- **Guarantees Scalability:** Simplifies adding new agents, MCP servers, or test categories without structural changes.

---

### 2. Target Repository Tree (Migration Specification)

Below is the planned target layout of the **Pipeline-2** codebase to support distributed FastAPI microservices and LangGraph graphs. 

> [!NOTE]
> During Phase 5.0, these folders are documented as target paths only and must NOT be created physically.

```
Pipeline-2/
│
├── README.md                 # Project landing page and onboarding portal
├── project_context.md        # Global boundaries and system rules
├── architecture.md           # HLD, topology, and flow transitions
├── api_contracts.md          # Authoritative Master/Worker HTTP API contracts
├── folder_structure.md       # Directory layout and path rules (this file)
├── team_roles.md             # Code ownership and merge access permissions
├── development_rules.md      # Coding style, branches, and PR checklists
├── database_contracts.md     # SQL schema limits and read/write mappings
├── mcp_contracts.md          # Input/output schemas for all MCP tools
├── workflow_contracts.md     # Sequence mappings and orchestration formats
├── agent_contracts.md        # Worker-specific triggers, duties, and APIs
├── master_agent.md           # Orchestrator routing loops and state trees
│
├── services/                 # FastAPI Service Boundary Controllers (Planned)
│   ├── master_api/           # Entry point and API routes for Master Agent
│   ├── agent6_api/           # HTTP API wrappers for Agent 6 Scheduling
│   ├── agent7_api/           # HTTP API wrappers for Agent 7 Tech Assessment
│   └── agent8_api/           # HTTP API wrappers for Agent 8 HR Re-ranking
│
├── agents/                   # LangGraph and LLM Orchestration logic
│   ├── master/               # Master orchestrator graphs and nodes
│   │   └── graph/            # Master state-machine LangGraph flow
│   ├── agent6/               # Invitation & scheduling worker
│   │   └── graph/            # Scheduling LangGraph local execution nodes
│   ├── agent7/               # Technical scorecard evaluator
│   │   └── graph/            # Scoring assessment LangGraph nodes
│   └── agent8/               # HR evaluator and ranking compiler
│       └── graph/            # Re-ranking calculation LangGraph nodes
│
├── contracts/                # Executable interface declarations (JSON/YAML/code)
├── prompts/                  # System and user prompt templates (.txt/.json)
├── schemas/                  # Pydantic validation models
├── mcp/                      # Custom MCP server scripts and drivers
├── shared/                   # Common helper code, logs, and exceptions
│   ├── clients/              # Reusable clients (e.g. Agent Client HTTP helper)
│   └── config/               # Settings and constants
├── tests/                    # Unit, integration, and mock suites
└── .env.example              # Local environment configuration template

---

## 3. Root-Level Files

| File | Purpose | Update Triggers | Owner |
| :--- | :--- | :--- | :--- |
| **README.md** | Repository intro, pipeline phases, and quick setup instructions. | Setup changes, new dependencies. | Shared |
| **project_context.md** | High-level system goals, scope limits, and stack specifications. | Changes to system architecture phases. | Shared |
| **architecture.md** | Central design, topology, state models, and HLD boundaries. | Changes in system topology. | Shared |
| **api_contracts.md** | Authoritative Master/Worker HTTP API contracts. | Endpoint changes, schema additions. | Neemay Gupta |
| **folder_structure.md** | File paths, folder blueprints, and structure rules. | Restructuring directory namespaces. | Shared |
| **team_roles.md** | Code owners, branch rights, and PR sign-off assignments. | Team restructuring or new assignments. | Neemay Gupta |
| **development_rules.md** | Naming styles, Git standards, and testing policies. | Changes in linting or branch limits. | Neemay Gupta |
| **database_contracts.md** | Segregated SQL limits, allowed tables, and transaction patterns. | Schema additions or changes. | Neemay Gupta |
| **mcp_contracts.md** | System parameters, inputs, outputs, and timeout details for MCP tools. | MCP API mutations. | Shared |
| **workflow_contracts.md** | Phase handshakes and transitions between agents. | Workflow sequence updates. | Neemay Gupta |
| **agent_contracts.md** | Task bounds, expected variables, and limits for agents. | Agent behavior modifications. | Agent Owners |
| **master_agent.md** | Logical orchestration flow design and routing guidelines. | Orchestration logic modifications. | Neemay Gupta |

---

## 4. Folder Descriptions

### `agents/`
Contains Python code for the system agents. Sub-folders are isolated namespaces:
- **`master/`:** Orchestration loop runtime and routing endpoints.
- **`agent6/`:** Logic to check calendars and invite candidates.
- **`agent7/`:** Logic to read transcript files and analyze tech scorecards.
- **`agent8/`:** Logic to evaluate soft skills and compile re-rank tables.

> [!CAUTION]
> **No Peer Imports:** Code inside `agents/agent6/` must **never** import modules from `agents/agent7/` or `agents/agent8/`. Cross-agent references are strictly forbidden.

---

### `contracts/`
Houses physical, machine-readable validation contracts (such as JSON Schema or YAML) representing interfaces defined in database, MCP, and workflow contract documents.

---

### `prompts/`
Stores plain text (`.txt`) system and user prompts used by agents. Prompts are kept separate from Python code to allow prompt versioning and direct prompt audits without mutating code files.

---

### `schemas/`
Stores Pydantic validation models.
- Exposes request/response structures for FastAPI interfaces.
- Standardizes event objects for pipeline handshakes.
- Declares data models for database records mapping.

---

### `mcp/`
Exposes custom Model Context Protocol servers. Sub-directories house individual Python-based MCP servers (e.g., Google Calendar driver, candidate profile resume parser). Each MCP server should run as an isolated process.

---

### `shared/`
Contains reusable helper libraries. This directory holds:
- Custom logging configs and instrumentation hooks.
- Constants and global enums (e.g., status codes, error codes).
- Standard exception definitions.
- Resilient request execution tools (retry loops, backoff code).

> [!IMPORTANT]
> **No Business Logic:** Shared modules must remain generic and helper-focused. No candidate routing or evaluation decisions belong here.

---

### `tests/`
Houses validation suites.
- **`unit/`:** Checks parsing, state switches, and schema logic in isolation.
- **`integration/`:** Validates sequential executions (e.g., Master Agent executing flow steps).
- **`mock/`:** Mocks out MCP servers, external APIs, and LLM responses.

---

### `docs/`
Houses design artifacts, system sequence charts, meeting records, research notes, and architectural decision records (ADRs).

---

## 5. Ownership Rules

To prevent code overlap, directory ownership is strictly enforced:

*   **`agents/master/` Ownership:**
    *   **Lead:** Neemay Gupta
    *   **Rules:** No other team member may push updates or bypass PR approval.
*   **`agents/agent6/` Ownership:**
    *   **Lead:** Agent 6 Developer (Interview Invitation)
    *   **Rules:** Primary developer designs prompts and tools; changes require review from Neemay Gupta.
*   **`agents/agent7/` Ownership:**
    *   **Lead:** Agent 7 Developer (Technical Evaluation)
    *   **Rules:** Responsible for scorecard templates and parsing prompts.
*   **`agents/agent8/` Ownership:**
    *   **Lead:** Agent 8 Developer (HR Evaluation & Ranking)
    *   **Rules:** Owns ranking math and soft-skill processing models.
*   **Shared Modules (`shared/`, `contracts/`, `schemas/`):**
    *   **Rules:** Shared folders require review and sign-off from Neemay Gupta and the affected agent developers.

---

## 6. Dependency Rules

Allowed imports and dependencies between components are strictly constrained:

```
┌────────────────────────────────────────────────────────┐
│                  ALLOWED DEPENDENCIES                  │
├────────────────────────────────────────────────────────┤
│  Master Agent    ───>  Worker Agent interfaces          │
│  Worker Agents   ───>  MCP Client layers                │
│  All Agents      ───>  Shared utility code              │
│  Master Agent    ───>  Pydantic Schemas                 │
│  Master Agent    ───>  Contracts definitions            │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                 FORBIDDEN DEPENDENCIES                 │
├────────────────────────────────────────────────────────┤
│  Worker Agent    ──x──  Worker Agent (A6 ──x── A7)     │
│  Worker Agent    ──x──  Direct DB queries / Raw SQL     │
│  Worker Agent    ──x──  Direct HTTP API client calls    │
│  Master Agent    ──x──  Domain-specific business logic  │
└────────────────────────────────────────────────────────┘
```

### Rationales for Dependency Restrictions
1.  **Isolation (No Worker-to-Worker):** Prevents compile-time coupling and circular dependency errors.
2.  **Encapsulation (No direct DB/API inside workers):** Forces workers to interact with the database and external APIs through the Database MCP and Calendar/Mail MCPs, simplifying test mocking.
3.  **Clean Architecture (No Domain Logic in Master):** The Master Agent orchestrates the flow based on status parameters; it does not process resumes, assess candidate technical skills, or calculate candidate scores.

---

## 7. Future Scalability

This directory layout simplifies future pipeline changes:
-   **Adding New Agents:** To add a Coding Test Agent, create `agents/agent9/`, define its prompts under `prompts/agent9/`, and implement tests under `tests/unit/agent9/`. No other agent code is modified.
-   **Adding Custom MCPs:** Add a server directory under `mcp/` (e.g., `mcp/slack/`) and map its schema to `contracts/mcp_contracts.md`.
-   **Switching LLMs:** LLM clients are configured in the orchestrator shell or `shared/config/`. Individual prompts can be modified under `prompts/` without code changes.

---

## 8. Repository Guidelines

-   **Location Rule:** All new code, configuration, or documentation files must reside within the folder structure defined above. Do not create unstructured root-level folders.
-   **Generic Shared Tools:** Files inside `shared/` must remain generic. If a function is specific to scheduling, it belongs in `agents/agent6/`.
-   **Version Controlled Contracts:** Interface contracts under `contracts/` are the definitive specs for the pipeline. Changes to these contracts require team approval.
-   **Architecture Documentation First:** Any modifications to the directory structure or namespaces require updating `folder_structure.md` first.
