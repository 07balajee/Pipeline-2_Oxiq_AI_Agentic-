# OxiqAI HRMS - Recruitment Pipeline-2
## TEAM ROLES, CODE OWNERSHIP, & COLLABORATION POLICY

---

## 1. Purpose

To ensure smooth development in a multi-developer environment, ownership boundaries are frozen prior to implementation. Setting these boundaries:
- **Prevents Merge Conflicts:** Developers work in distinct directories without overlapping commits.
- **Enforces Independent Development:** Clear boundaries allow developers to build, test, and debug their assigned components in isolation.
- **Establishes Accountability:** Each team member is responsible for the performance, prompts, and contract compliance of their component.
- **Accelerates Code Reviews:** Reviewers know exactly who owns what, speeding up PR resolution cycles.
- **Simplifies Developer Onboarding:** New joiners can immediately identify subject matter experts for each module.
- **Ensures Controlled Integration:** Changes to integration paths are managed centrally to protect system stability.

---

## 2. Team Members

The Pipeline-2 project features a three-member core team and a developer slot reserved for scheduling agent features.

| Developer | Primary Responsibility | Owned Component | Owned Branch | Review Responsibility | Integration Responsibility |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Neemay Gupta** | System Lead, Orchestration & Handoffs | Master Agent, Architecture, Project Structure, Workflows | `feature/master-agent` | `contracts/`, `schemas/`, `shared/` | Repository Coordination, Handoffs, Final Merge to `main` |
| **[TBD / Placeholder]** | Scheduling Workflows | Agent 6 (Interview Invitation) | `feature/agent6` | Prompting & Scheduling Tools | Handoff to Master Agent |
| **Piyush** | Technical Assessment Processing | Agent 7 (Technical Interview) | `feature/agent7` | Scorecard Parsers & Prompts | Handoff to Master Agent |
| **Haris** | HR Evaluation & Candidate Sorting | Agent 8 (HR Assessment & Re-ranking) | `feature/agent8` | Soft Skills evaluation & Sorting | Handoff to Master Agent |

---

## 3. Code Ownership

Ownership boundaries define who is permitted to make modifications to code folders:

*   **Master Agent Namespace (`agents/master/`):** Owned exclusively by **Neemay Gupta**. No other developer may commit changes directly to this path.
*   **Agent 6 Namespace (`agents/agent6/`):** Owned by **Agent 6 Developer [TBD]**.
*   **Agent 7 Namespace (`agents/agent7/`):** Owned exclusively by **Piyush**.
*   **Agent 8 Namespace (`agents/agent8/`):** Owned exclusively by **Haris**.
*   **Shared Resources (`shared/`):** Changes require a pull request reviewed by Neemay Gupta and at least one other agent owner.
*   **Contracts & Schemas (`contracts/`, `schemas/`):** Mutating validation files requires review and sign-off by Neemay Gupta.
*   **Core Architecture Docs:** Architecture modifications require approval from Neemay Gupta before changes are merged.

---

## 4. Git Branch Strategy

To ensure code stability, development is structured around isolated branch paths:

```
                  ┌──────────────────────┐
                  │    main (Stable)     │
                  └──────────┬───────────┘
                             │ Merged via approved PR
                             ▼
                  ┌──────────────────────┐
                  │       develop        │
                  └────┬───┬───┬─────┬───┘
                       │   │   │     │
      ┌────────────────┘   │   │     └────────────────┐
      ▼                    ▼   ▼                      ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│feature/master│ │feature/agent6│ │feature/agent7│ │feature/agent8│
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

-   **`main` Branch:** Production-ready code. Commits are not made directly here; changes are merged only from approved pull requests.
-   **`develop` Branch:** Active integration area.
-   **Feature Branches (`feature/master-agent`, `feature/agent6`, etc.):** Individual workspaces for developers. Developers only push to their assigned feature branch.
-   **No Force Pushes:** Overwriting history on `main` or `develop` branches is strictly forbidden.

---

## 5. Pull Request Workflow

All code additions must follow the structured PR process:

```
  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
  │  Dev Branch  ├──────>│ Push Changes ├──────>│ Create PR on │
  │ (Local work) │       │ (GitHub Repo)│       │   develop    │
  └──────────────┘       └──────────────┘       └──────┬───────┘
                                                       │
                                                       ▼
  ┌──────────────┐       ┌──────────────┐       ┌──────┴───────┐
  │ Run tests /  │<──────┤ Approved &   │<──────┤  Code Review │
  │ Merge Branch │       │ Signed Off   │       │  (Teammates) │
  └──────────────┘       └──────────────┘       └──────────────┘
```

1.  **Feature Work:** Developer works locally on their assigned branch.
2.  **Commit & Push:** Dev commits logical changes (referencing tickets/tasks) and pushes to their remote feature branch.
3.  **Create PR:** Developer opens a Pull Request targeting `develop`.
4.  **Code Review:** Assigned teammates inspect changes, checking for code quality and contract compliance.
5.  **Approval:** PR requires at least two approvals (including the Master Agent owner).
6.  **Merge & Integration:** Once approved, the Master Agent owner merges the PR, triggering integration tests.

---

## 6. Merge Responsibilities

-   **PR Authorship:** The owner of the feature branch is responsible for opening the PR, explaining the changes, and resolving any conflicts.
-   **PR Review:** The repository integration lead (Neemay Gupta) reviews the PR to ensure the code remains compliant with system contracts.
-   **Conflict Resolution:** Merge conflicts must be resolved collaboratively by the authors of the conflicting branches.
-   **No Self-Merging:** Developers cannot approve or merge their own PRs.

---

## 7. Collaboration Rules

-   **Domain Isolation:** Developers must not modify files in folders owned by other developers.
-   **Contract Immutability:** No changes can be made to the contracts (`contracts/`, `schemas/`, `database_contracts.md`, etc.) without review and sign-off.
-   **Proactive Communication:** Notify teammates of changes to shared libraries or helper tools in `shared/` before committing.
-   **Documentation-First:** Update architecture documents and blueprints prior to committing any structural changes to code files.
-   **Agent 7 Developer Isolation (Piyush):** May modify only files under `agents/agent7/**` and related tests. Must not modify the Master Agent or shared resources.
-   **Agent 8 Developer Isolation (Haris):** May modify only files under `agents/agent8/**` and related tests. Must not modify the Master Agent or shared resources.
-   **Master Agent & Shared Contract Stability:** The Master Agent and shared schemas must NOT be modified by worker-agent branches unless an incompatibility is formally identified, reviewed, and approved by the system lead (Neemay Gupta).

---

## 8. Integration Strategy

Pipeline-2 integration is scheduled sequentially to ease debugging:

1.  **Phase A (Master Agent):** Establish the orchestration skeleton and endpoints.
2.  **Phase B (Scheduling Integration):** Connect Agent 6 to the Master Agent to verify calendar scheduling.
3.  **Phase C (Technical Evaluation Integration):** Integrate Agent 7 to verify scorecard parsing.
4.  **Phase D (HR & Ranking Integration):** Integrate Agent 8 to verify evaluation scoring and sorting logic.
5.  **Phase E (MCP Servers Integration):** Connect database and external utility MCP tools.
6.  **Phase F (E2E Validation):** Run end-to-end simulation tests once all modules are integrated.

---

## 9. Review Checklist

Before approving any Pull Request, reviewers must verify:

-   [ ] **Architecture Compliance:** Core architecture remains unchanged.
-   [ ] **Contract Respect:** Data payloads match schemas under `contracts/`.
-   [ ] **Zero Peer Calls:** No direct Agent-to-Agent imports or communication loops.
-   [ ] **Zero SQL / Direct DB Calls:** Database actions go through the Database MCP.
-   [ ] **MCP Compliance:** Tool invocations follow schemas defined in `mcp_contracts.md`.
-   [ ] **Observability:** Telemetry and tracking events are logged correctly.
-   [ ] **Error Handling:** Fallback scenarios and retries are implemented.
-   [ ] **Documentation Sync:** Documentation is updated to match code modifications.
-   [ ] **Clean Commits:** Unrelated configuration changes or formatting edits are omitted.

---

## 10. Team Communication

-   **Weekly Syncs:** A weekly meeting to discuss progress, roadmap alignment, and integration blockers.
-   **Contract Alignment:** Meet and review changes prior to altering schemas or contracts.
-   **Issue Tracking:** Task logs are managed through GitHub Issues.
-   **PR Conversations:** Review questions and suggestions must be recorded directly on the GitHub PR thread.
-   **Design Record:** Major technical choices must be documented in `docs/` using Architecture Decision Records (ADRs).

---

## 11. Future Onboarding

Onboarding new developers involves the following steps:
1.  **Module Allocation:** Assign the new developer to a specific agent namespace or a new MCP server.
2.  **Isolated Workspace:** The developer works in their assigned namespace (e.g., `agents/agent9/`), isolated from existing agent directories.
3.  **Contract Interface:** The developer uses existing schemas under `contracts/` and `schemas/` to integrate their agent.
4.  **Coordination:** System-wide changes are coordinated by Neemay Gupta.

---

## 12. Summary

In summary, Pipeline-2 uses a contract-first, ownership-driven collaborative development model. Each developer owns their component directory, while changes to shared resources require approval from the integration lead. This approach prevents merge conflicts, clarifies responsibilities, and ensures the repository remains organized as the system scales.
