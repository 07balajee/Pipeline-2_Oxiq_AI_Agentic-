# OxiqAI HRMS - Recruitment Pipeline-2
## HTTP API CONTRACT SPECIFICATION (MASTER ↔ WORKER)

This document defines the authoritative API schemas, endpoints, headers, error structures, and transport protocols governing communication between the Master Agent and worker agents in Pipeline-2.

---

## 1. Global API Conventions

*   **Protocol:** HTTP/1.1 over TLS (HTTPS).
*   **Default Content-Type:** `application/json` for requests and responses.
*   **API Versioning:** Versioning is prefixed in the URI path (e.g. `/v1/agents/agent6/execute`).
*   **Correlation & Trace Propagation:**
    *   Every request must include the header `X-Correlation-ID` (value of `WorkflowContext.workflow_id`) for end-to-end tracing.
    *   Every logging service and HTTP client must capture and log this header.
*   **Idempotency Handling:**
    *   The `X-Idempotency-Key` header must be sent by the Master Agent on all execute requests. The value is deterministically generated from `workflow_id` + `state_name` + `retry_count`.
    *   Workers must cache this key and return cached results if a duplicate execution request is received.
*   **Timeout Semantics:**
    *   Worker execution endpoints: Client-side connection timeout of **30 seconds**.
    *   If a timeout occurs, the Master Agent Client treats this as a transport failure (HTTP 504 Gateway Timeout) and applies Master-level retry/fallback.

---

## 2. API Status Code & Error Semantics

Pipeline-2 strictly distinguishes between **Transport/Infrastructure failures** and **Business/Workflow failures**:

| Status Code | Meaning | Classification |
| :--- | :--- | :--- |
| **HTTP 200 OK** | Request successfully processed (even if business logic failed). | Successful Transport |
| **HTTP 400 Bad Request** | Request is malformed or invalid parameter value. | Client Error |
| **HTTP 422 Unprocessable Entity** | JSON payload failed Pydantic schema validation. | Schema Validation Error |
| **HTTP 500 Internal Error** | Unhandled exception inside the service runtime. | Service Crash |
| **HTTP 503 Service Unavailable**| Worker service is offline or overloaded. | Service Offline |
| **HTTP 504 Gateway Timeout** | Worker execution exceeded the 30-second limit. | Timeout |

### A. Business Success vs. Failure (HTTP 200)
A worker agent that executes successfully but cannot fulfill the request due to business constraints must return an HTTP 200 status code with `execution_status="FAILED"` in the body.
*   *Example:* No interviewers match department criteria, or calendar availability is fully exhausted.
*   *Response Body:*
    ```json
    {
      "execution_status": "FAILED",
      "generated_event": null,
      "updated_state": null,
      "summary": "Scheduling failed: no eligible interviewer found.",
      "errors": ["INTERVIEWER_EXHAUSTED"],
      "warnings": [],
      "suggested_action": "escalate",
      "metadata": {}
    }
    ```

### B. Standard Error Envelope (HTTP 4xx / 5xx)
If an endpoint returns a non-200 status code, it must conform to the standard error envelope structure:
```json
{
  "detail": "Error message describing the failure",
  "error_code": "SYSTEM_TIMEOUT",
  "correlation_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1"
}
```

---

## 3. Master Agent API

Exposed by the Master Agent service (Default Port: `8000`).

### POST /v1/workflow/start
Initiates a candidate loop workflow (typically triggered by Pipeline-1).
*   **Request Body:** `mock_candidate_data` and `mock_job_data` schemas (see `CandidateContext` definition).
*   **Response Body (HTTP 201 Created):**
    ```json
    {
      "workflow_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1",
      "status": "active"
    }
    ```

### POST /v1/workflow/event
Publishes an event to push the candidate workflow forward.
*   **Request Body:**
    ```json
    {
      "workflow_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1",
      "event_name": "InterviewStarted"
    }
    ```
*   **Response Body (HTTP 200 OK):**
    ```json
    {
      "workflow_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1",
      "new_state": "TechnicalInterviewPending"
    }
    ```

### POST /v1/workflow/resume
Resumes a workflow paused on a human approval checkpoint (HITL).
*   **Request Body:**
    ```json
    {
      "workflow_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1",
      "action": "APPROVE",
      "notes": "Time slot approved by recruiter."
    }
    ```
*   **Response Body (HTTP 200 OK):**
    ```json
    {
      "workflow_id": "aa70c7a9-8404-4957-b3df-51d583e8afb1",
      "status": "resumed"
    }
    ```

### GET /v1/workflow/{workflow_id}
Retrieves current context details and execution state for a workflow.
*   **Response Body (HTTP 200):** Serialized `WorkflowContext` representation.

### GET /v1/health
Health check endpoint.
*   **Response Body (HTTP 200):** `{"status": "healthy"}`

---

## 4. Worker Agent APIs

Exposed by individual worker microservices.

### A. Agent 6 — Interview Invitation & Scheduling (Default Port: `8006`)

#### POST /v1/agents/agent6/execute
Triggers the scheduling heuristic and calendar bookings.
*   **Headers:**
    *   `X-Correlation-ID`: `aa70c7a9-8404-4957-b3df-51d583e8afb1`
    *   `X-Idempotency-Key`: `idemp-a6-aa70c7a9-v1`
*   **Request Body:** `WorkflowContext` (JSON payload matching Pydantic class).
*   **Response Body (HTTP 200):** `AgentResponse` (JSON payload matching Pydantic class).

#### GET /v1/agents/agent6/health
*   **Response Body (HTTP 200):** `{"status": "healthy"}`

---

### B. Agent 7 — Technical Interview Assessment (Default Port: `8007`)

#### POST /v1/agents/agent7/execute
Parses assessment inputs and compiles the technical scorecard.
*   **Headers:**
    *   `X-Correlation-ID`: `aa70c7a9-8404-4957-b3df-51d583e8afb1`
    *   `X-Idempotency-Key`: `idemp-a7-aa70c7a9-v1`
*   **Request Body:** `WorkflowContext` (JSON payload).
*   **Response Body (HTTP 200):** `AgentResponse` (JSON payload).

#### GET /v1/agents/agent7/health
*   **Response Body (HTTP 200):** `{"status": "healthy"}`

---

### C. Agent 8 — HR Interview & Re-ranking (Default Port: `8008`)

#### POST /v1/agents/agent8/execute
Performs soft-skill evaluation and updates the candidate cohort rankings.
*   **Headers:**
    *   `X-Correlation-ID`: `aa70c7a9-8404-4957-b3df-51d583e8afb1`
    *   `X-Idempotency-Key`: `idemp-a8-aa70c7a9-v1`
*   **Request Body:** `WorkflowContext` (JSON payload).
*   **Response Body (HTTP 200):** `AgentResponse` (JSON payload).

#### GET /v1/agents/agent8/health
*   **Response Body (HTTP 200):** `{"status": "healthy"}`
