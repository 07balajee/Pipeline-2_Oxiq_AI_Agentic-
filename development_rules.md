# Pipeline-2 Development Rules (Phase 5.8 Frozen Baseline)

## Rule 1: Master Domain & Service Isolation (STRICT)

1. `agents/master/**` and `services/master_api/**` MUST NOT import worker implementations (`InterviewInvitationAgent`, `TechnicalInterviewAgent`, `HRInterviewAgent`) or sub-agent modules (`agents.agent6`, `agents.agent7`, `agents.agent8`).
2. Master MUST communicate with all worker microservices exclusively over HTTP via `AgentServiceClient` in `agents/master/dispatcher.py`.
3. Automated AST invariant test `tests/test_architecture_invariants.py::test_master_domain_isolation` and `test_master_service_api_isolation` enforce this rule permanently.

---

## Rule 2: Sub-Agent Peer Isolation (STRICT)

1. Worker sub-agents (`agents/agent6`, `agents/agent7`, `agents/agent8`) MUST NOT import peer worker modules or sub-agent packages.
2. Worker sub-agents MUST NOT import Master domain or service packages.
3. Automated AST invariant tests `tests/test_architecture_invariants.py::test_agentN_peer_and_master_isolation` enforce this rule permanently.

---

## Rule 3: Single Authoritative Source of Truth for Configuration

1. All service URLs, timeouts, retry limits, and environment settings MUST be declared in `shared/config/settings.py` (`Settings`).
2. Constants in `shared/config/constants.py` reference `settings` to prevent configuration drift.

---

## Rule 4: Preserved Contracts & HTTP Schemas

1. All HTTP requests sent to worker services MUST carry `WorkflowContext` in the request body.
2. All worker services MUST return `AgentResponse` in the response body.
3. Headers `X-Correlation-ID` and `X-Idempotency-Key` MUST be accepted, logged, and returned in response headers across all microservice boundaries.
