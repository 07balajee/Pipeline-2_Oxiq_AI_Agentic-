import unittest
from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient
from services.agent6_api.app import app
from schemas.agent_response import AgentResponse

class TestAgent6API(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.candidate_data = {
            "candidate_id": "CAND-001",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "resume_url": "CV_JohnDoe_AIEngineer.pdf",
            "screening_score": 91.0,
            "job_id": "job-abc-123",
            "job_title": "AI Engineer"
        }
        self.context_json = {
            "workflow_id": "wf-test-123",
            "candidate": self.candidate_data,
            "current_state": "CandidateShortlisted",
            "metadata": {"interactive": False}
        }

    def test_health_endpoint(self):
        """
        GET /v1/agents/agent6/health must return HTTP 200 health metadata without running the agent.
        """
        response = self.client.get("/v1/agents/agent6/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "healthy",
            "service": "agent6",
            "version": "v1"
        })

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_execute_agent6_happy_path(self, mock_run):
        """
        POST /v1/agents/agent6/execute happy path must return HTTP 200 and SUCCESS agent response.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Interview successfully scheduled.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["execution_status"], "SUCCESS")
        self.assertEqual(json_data["generated_event"], "InterviewCreated")

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_execute_business_failure_returns_200(self, mock_run):
        """
        POST /v1/agents/agent6/execute business level failures must return HTTP 200 and FAILED status.
        """
        mock_run.return_value = AgentResponse(
            execution_status="FAILED",
            generated_event=None,
            updated_state=None,
            summary="Interviewer availability slots exhausted.",
            errors=["SLOTS_EXHAUSTED"],
            warnings=[],
            suggested_action="escalate",
            metadata={}
        )

        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["execution_status"], "FAILED")
        self.assertIn("SLOTS_EXHAUSTED", json_data["errors"])

    def test_invalid_workflow_context_returns_422(self):
        """
        POST /v1/agents/agent6/execute malformed payload structure must return HTTP 422 validation error.
        """
        malformed_json = {
            "workflow_id": "wf-invalid",
            "candidate": {
                "candidate_id": "CAND-001"
                # Missing name, email, resume_url, screening_score, etc.
            }
        }
        response = self.client.post("/v1/agents/agent6/execute", json=malformed_json)
        self.assertEqual(response.status_code, 422)

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_correlation_id_preserved(self, mock_run):
        """
        X-Correlation-ID sent in request headers must be preserved and returned in response headers.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Preserved correlation.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        headers = {"X-Correlation-ID": "correlation-test-123"}
        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Correlation-ID"), "correlation-test-123")

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_correlation_id_generated(self, mock_run):
        """
        X-Correlation-ID missing in request headers must be generated as UUID and returned.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Generated correlation.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json)
        self.assertEqual(response.status_code, 200)
        correlation_id = response.headers.get("X-Correlation-ID")
        self.assertIsNotNone(correlation_id)
        # Verify it is a valid UUID
        try:
            uuid.UUID(correlation_id)
        except ValueError:
            self.fail("Correlation ID header is not a valid UUID string.")

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_idempotency_header_accepted(self, mock_run):
        """
        X-Idempotency-Key request header must be accepted and returned in response headers.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Idempotent reservation.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        headers = {"X-Idempotency-Key": "idemp-key-abc-123"}
        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Idempotency-Key"), "idemp-key-abc-123")

    @patch("agents.agent6.agent.InterviewInvitationAgent.run")
    def test_unhandled_service_exception_returns_500(self, mock_run):
        """
        Unhandled service exception during execution must return HTTP 500 Internal Server Error.
        """
        mock_run.side_effect = RuntimeError("Critical adapter connection failure.")

        response = self.client.post("/v1/agents/agent6/execute", json=self.context_json)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Critical adapter connection failure.", response.json()["detail"])
