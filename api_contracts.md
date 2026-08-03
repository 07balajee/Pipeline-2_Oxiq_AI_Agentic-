# Pipeline-2 API Contracts Reference (Phase 5.8 Frozen Baseline)

## Master Service Endpoints (:8000)

### 1. `POST /v1/workflow/start`
- **Request**: `WorkflowStartRequest` (`candidate_data`, `job_data`, `metadata`)
- **Headers**: `X-Idempotency-Key` (optional), `X-Correlation-ID` (optional)
- **Response**: `201 Created` — `WorkflowStartResponse` (`workflow_id`, `status`)

### 2. `POST /v1/workflow/event`
- **Request**: `WorkflowEventRequest` (`workflow_id`, `event_name`, `payload`)
- **Headers**: `X-Correlation-ID` (optional)
- **Response**: `200 OK` — `WorkflowEventResponse` (`workflow_id`, `new_state`)

### 3. `POST /v1/workflow/resume`
- **Request**: `WorkflowResumeRequest` (`workflow_id`, `approval_type`, `action`, `notes`)
- **Response**: `200 OK` — `WorkflowResumeResponse` (`workflow_id`, `status`)

### 4. `GET /v1/workflow/{workflow_id}`
- **Response**: `200 OK` — `WorkflowStatusResponse` (`current_state`, `graph_status`, `timeline`, `step_data`, etc.)

### 5. `GET /v1/health`
- **Response**: `200 OK` — `{"status": "healthy", "service": "master", "version": "v1"}`

### 6. `GET /v1/readiness`
- **Response**: `200 OK` (when operational/degraded) or `503` (unhealthy) — `ReadinessResponse`:
  ```json
  {
    "status": "ready",
    "dependencies": {
      "agent6": {"status": "healthy", "url": "http://127.0.0.1:8001", "latency_ms": 1.25},
      "agent7": {"status": "healthy", "url": "http://127.0.0.1:8002", "latency_ms": 1.10},
      "agent8": {"status": "healthy", "url": "http://127.0.0.1:8003", "latency_ms": 0.95}
    }
  }
  ```

---

## Worker Microservice Endpoints

### Agent 6 (:8001)
- `GET /v1/agents/agent6/health`
- `POST /v1/agents/agent6/execute` -> Accepts `WorkflowContext`, returns `AgentResponse`

### Agent 7 (:8002)
- `GET /v1/agents/agent7/health`
- `POST /v1/agents/agent7/execute` -> Accepts `WorkflowContext`, returns `AgentResponse`

### Agent 8 (:8003)
- `GET /v1/agents/agent8/health`
- `POST /v1/agents/agent8/execute` -> Accepts `WorkflowContext`, returns `AgentResponse`
