# OxiqAI HRMS - Recruitment Pipeline-2
## MODEL CONTEXT PROTOCOL (MCP) INTERFACE CONTRACTS

---

## 1. Purpose

The **Model Context Protocol (MCP) Contract** defines the tool interface standard for Pipeline-2. Standardizing these connections:
- **Abstracts Infrastructure:** Decouples agents from direct API schemas and DB engines.
- **Enforces Security Boundaries:** Restricts third-party API credentials to standalone MCP processes, keeping agent contexts clean of credentials.
- **Improves Modular Testing:** Allows developer teams to run agent pipelines against mock MCP servers without configuring live databases or calendar services.
- **Ensures Extensibility:** Allows developers to swap services (e.g., migrating from Google Calendar to Microsoft Outlook) without updating prompt templates or agent logic.

---

## 2. MCP Architecture

The MCP layer serves as the boundary between the cognitive LLM-backed agent logic and system infrastructure (databases, file storage, email, calendars).

```
   ┌────────────────────────────────────────────────────────┐
   │                    COGNITIVE LAYER                     │
   │  - Master Agent             - Worker Agents (A6/7/8)   │
   └────────────────────────┬───────────────────────────────┘
                            │ Standardized JSON-RPC (MCP)
                            ▼
   ┌────────────────────────────────────────────────────────┐
   │                    ABSTRACTION LAYER                   │
   │  - Database MCP             - Resume / Document MCP    │
   │  - Google Calendar MCP      - SMTP / Notification MCP  │
   └────────────────────────┬───────────────────────────────┘
                            │ API Calls / SQL Connections
                            ▼
   ┌────────────────────────────────────────────────────────┐
   │                  INFRASTRUCTURE LAYER                  │
   │  - PostgreSQL DB            - Google Workspace / Mail  │
   └────────────────────────────────────────────────────────┘
```

---

## 3. Internal MCP Servers

### Database MCP
- **Purpose:** Centralized SQL access engine for PostgreSQL.
- **Responsibilities:** Executes reads/writes, manages transaction rollbacks, validates inputs, and writes audit logs.
- **Allowed Consumers:** Master Agent, Agent 6, Agent 7, Agent 8 (with column-level table restrictions).
- **Core Operations:**
  - `fetch_candidate_by_id` (Inputs: `candidate_id`)
  - `update_candidate_state` (Inputs: `candidate_id`, `state`)
  - `insert_interview_schedule` (Inputs: `candidate_id`, `scheduled_time`, `interviewer_id`)
  - `save_evaluation_scorecard` (Inputs: `interview_id`, `scorecard_json`, `evaluation_type`)
  - `calculate_pool_rankings` (Inputs: `job_id`)

### Resume MCP
- **Purpose:** Parses and extracts profile data from candidate resumes.
- **Responsibilities:** Downloads resumes, extracts text elements, and returns structured profiles.
- **Expected Inputs:** `resume_url`, `extraction_parameters`
- **Expected Outputs:** JSON containing text snippets, experience summary, skills list, and education history.
- **Consumers:** Master Agent, Agent 7.

### Document MCP
- **Purpose:** Generates formatted candidate evaluation summary PDF reports.
- **Responsibilities:** Merges candidate scores, feedback notes, and ranking cards into PDF templates.
- **Expected Inputs:** `candidate_id`, `report_type` (e.g., `TECHNICAL`, `HR`, `CONSOLIDATED`)
- **Expected Outputs:** `document_url` (filepath or cloud storage link)
- **Consumers:** Master Agent.

### Analytics MCP
- **Purpose:** Monitors system usage, latency, and costs.
- **Responsibilities:** Logs agent execution times, prompt token usage, and tool latency metrics.
- **Expected Inputs:** `trace_id`, `agent_name`, `metrics_payload`
- **Expected Outputs:** `status` (Boolean)
- **Consumers:** Master Agent, Agent 6, Agent 7, Agent 8.

### Notification MCP
- **Purpose:** Dispatches chat notifications to team members.
- **Responsibilities:** Formats and routes status updates to internal channels (e.g., Slack or Microsoft Teams).
- **Expected Inputs:** `channel_id`, `message_text`, `notification_priority`
- **Expected Outputs:** `delivery_status` (Boolean)
- **Consumers:** Master Agent.

### Company Policy MCP
- **Purpose:** Exposes corporate guidelines and background verification parameters.
- **Responsibilities:** Returns scoring rules and screening criteria.
- **Expected Inputs:** `job_title`, `query_type`
- **Expected Outputs:** Structured policy JSON.
- **Consumers:** Master Agent, Agent 8.

### Salary Band MCP
- **Purpose:** Retrieves compensation benchmarks.
- **Responsibilities:** Queries budget rules to output approved salary ranges.
- **Expected Inputs:** `job_id`, `experience_years`
- **Expected Outputs:** `salary_range` (JSON with min, max, and currency values).
- **Consumers:** Master Agent, Agent 8.

---

## 4. External MCP Servers

### Google Calendar MCP
- **Purpose:** Synchronizes bookings with Google Calendar resources.
- **Responsibilities:** Queries interviewer availability, books appointments, and processes scheduling conflicts.
- **Expected Inputs:** `interviewer_email`, `candidate_email`, `time_slot`, `event_title`
- **Expected Outputs:** `calendar_event_id`, `status` (Boolean)
- **Consumers:** Agent 6.

### Google Meet MCP
- **Purpose:** Generates virtual conferencing spaces.
- **Responsibilities:** Creates meeting codes, sets permissions, and handles cancellations.
- **Expected Inputs:** `calendar_event_id`, `access_settings`
- **Expected Outputs:** `meeting_url`
- **Consumers:** Agent 6.

### SMTP Mail MCP
- **Purpose:** Dispatches notification emails to candidates.
- **Responsibilities:** Sends booking notices, feedback templates, and follow-up emails.
- **Expected Inputs:** `recipient_email`, `subject`, `email_body`, `template_id`
- **Expected Outputs:** `message_id`, `delivery_status`
- **Consumers:** Agent 6.

### Future Integrations (Optional Roadmap)
- **Microsoft Teams / Zoom MCP:** Standardized alternatives for generating meeting links.
- **Slack MCP:** Real-time updates and notification channel integration.
- **Outlook Calendar / Mail MCP:** Alternate corporate email and scheduling provider sync.

---

## 5. MCP Ownership Matrix

| MCP Server | Master Agent | Agent 6 (Invite) | Agent 7 (Tech) | Agent 8 (HR & Rank) |
| :--- | :--- | :--- | :--- | :--- |
| **Database MCP** | Read / Write | Read / Write | Read / Write | Read / Write |
| **Resume MCP** | Read Only | No Access | Read Only | No Access |
| **Document MCP** | Invoke (Write) | No Access | No Access | No Access |
| **Analytics MCP** | Invoke (Write) | Invoke (Write) | Invoke (Write) | Invoke (Write) |
| **Notification MCP** | Invoke | No Access | No Access | No Access |
| **Policy MCP** | Read Only | No Access | No Access | Read Only |
| **Salary Band MCP** | Read Only | No Access | No Access | Read Only |
| **Google Calendar** | No Access | Invoke (Write) | No Access | No Access |
| **Google Meet** | No Access | Invoke (Write) | No Access | No Access |
| **SMTP Mail** | No Access | Invoke (Write) | No Access | No Access |

---

## 6. MCP Invocation Rules

-   **Unidirectional Invocation:** Agents query MCP servers. MCP servers do not call agents.
-   **No Peer MCP Calling:** MCP servers operate independently. An MCP server must not call another MCP server (e.g., the Database MCP cannot invoke the SMTP Mail MCP).
-   **No Internal Business Logic:** MCP tools serve as raw interfaces to data or services. They must not contain pipeline logic (such as checking if a candidate passed a technical assessment or calculating pool rankings).

---

## 7. Error Handling

All MCP servers must handle potential failures systematically:
-   **Connection Timeout:** If an external API is down, the MCP server queues queries and retries execution using exponential backoff.
-   **Service Outage:** Return `SERVICE_UNAVAILABLE` to the calling agent to trigger fallback logic (such as rescheduling).
-   **Authentication Mismatches:** If API keys expire, return `AUTHENTICATION_ERROR` to the Master Agent to trigger notification alerts.
-   **Malformed Payload:** Input parameter mismatches raise immediate validation exceptions.
-   **Rate Limits:** If API rate limits are hit, pause calls and request retry scheduling.

---

## 8. Security Principles

-   **Token Segregation:** Auth tokens and API keys are stored securely on the host system. They are never sent to or stored within the LLM agent context.
-   **Authorization Limits:** Access to tables and API scopes is restricted using the least privilege principle.
-   **Input Validation:** The MCP server sanitizes all tool inputs to prevent SQL injection or cross-site scripting vulnerabilities.
-   **Audit Logs:** Every tool execution is logged with the trace ID, user details, and timestamp.

---

## 9. Future Extensibility

-   **Integrating New Systems:** A coding assessment platform is added by implementing a Coding MCP server, keeping existing agents unaffected.
-   **Hot-Swapping Services:** Moving from SMTP email to SendGrid requires updating the mail MCP configuration, leaving the agent prompting and scheduling logic unchanged.
-   **Scale Testing:** Developers can run unit tests against mock servers, avoiding live API costs and setup complexities.

---

## 10. Summary

In summary, the MCP layer serves as the infrastructure abstraction layer for Pipeline-2. By routing all API calls and database queries through standardized MCP interfaces, the architecture enforces strict security boundaries, decouples agents from third-party APIs, and simplifies system maintenance.
