import unittest
from unittest.mock import patch
import uuid
from fastapi.testclient import TestClient
from services.agent7_api.app import app
from schemas.agent_response import AgentResponse

class TestAgent7API(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.candidate_data = {
            "candidate_id": "CAND-001",
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "resume_url": "CV_JaneSmith.pdf",
            "screening_score": 88.5,
            "job_id": "job-abc-123",
            "job_title": "Senior Backend Engineer"
        }
        self.context_json = {
            "workflow_id": "wf-test-agent7-123",
            "candidate": self.candidate_data,
            "current_state": "TechnicalInterviewPending",
            "metadata": {"interactive": False}
        }

    def test_health_endpoint(self):
        """
        GET /v1/agents/agent7/health must return HTTP 200 health metadata without running the agent.
        """
        response = self.client.get("/v1/agents/agent7/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "healthy",
            "service": "agent7",
            "version": "v1"
        })

    @patch("agents.agent7.agent.TechnicalInterviewAgent.run")
    def test_execute_agent7_happy_path(self, mock_run):
        """
        POST /v1/agents/agent7/execute happy path must return HTTP 200 and SUCCESS agent response.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="TechnicalScoreSubmitted",
            updated_state="TechnicalInterviewCompleted",
            summary="Technical scorecard generated for Jane Smith. Decision: PASS.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={"technical_scores": {"coding_proficiency": 8.5}, "recommendation": "PASS"}
        )

        response = self.client.post("/v1/agents/agent7/execute", json=self.context_json)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["execution_status"], "SUCCESS")
        self.assertEqual(json_data["generated_event"], "TechnicalScoreSubmitted")

    @patch("agents.agent7.agent.TechnicalInterviewAgent.run")
    def test_execute_business_failure_returns_200(self, mock_run):
        """
        POST /v1/agents/agent7/execute business level failures must return HTTP 200 and FAILED status.
        """
        mock_run.return_value = AgentResponse(
            execution_status="FAILED",
            generated_event=None,
            updated_state=None,
            summary="Agent 7 execution failed on operation: 'context_retrieval'",
            errors=["Database context retrieval exhausted after 3 retries."],
            warnings=[],
            suggested_action=None,
            metadata={"failed_operation": "context_retrieval", "failure_category": "TERMINAL"}
        )

        response = self.client.post("/v1/agents/agent7/execute", json=self.context_json)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["execution_status"], "FAILED")
        self.assertIn("Database context retrieval exhausted after 3 retries.", json_data["errors"])

    def test_invalid_workflow_context_returns_422(self):
        """
        POST /v1/agents/agent7/execute malformed payload structure must return HTTP 422 validation error.
        """
        malformed_json = {
            "workflow_id": "wf-invalid",
            "candidate": {
                "candidate_id": "CAND-001"
            }
        }
        response = self.client.post("/v1/agents/agent7/execute", json=malformed_json)
        self.assertEqual(response.status_code, 422)

    @patch("agents.agent7.agent.TechnicalInterviewAgent.run")
    def test_correlation_id_preserved(self, mock_run):
        """
        X-Correlation-ID sent in request headers must be preserved and returned in response headers.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="TechnicalScoreSubmitted",
            updated_state="TechnicalInterviewCompleted",
            summary="Preserved correlation.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        headers = {"X-Correlation-ID": "correlation-test-777"}
        response = self.client.post("/v1/agents/agent7/execute", json=self.context_json, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Correlation-ID"), "correlation-test-777")

    @patch("agents.agent7.agent.TechnicalInterviewAgent.run")
    def test_idempotency_header_accepted(self, mock_run):
        """
        X-Idempotency-Key request header must be accepted and returned in response headers.
        """
        mock_run.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="TechnicalScoreSubmitted",
            updated_state="TechnicalInterviewCompleted",
            summary="Idempotent evaluation.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        headers = {"X-Idempotency-Key": "idemp-key-777"}
        response = self.client.post("/v1/agents/agent7/execute", json=self.context_json, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Idempotency-Key"), "idemp-key-777")

    @patch("agents.agent7.agent.TechnicalInterviewAgent.run")
    def test_unhandled_service_exception_returns_500(self, mock_run):
        """
        Unhandled service exception during execution must return HTTP 500 Internal Server Error.
        """
        mock_run.side_effect = RuntimeError("Critical Agent 7 internal failure.")

        response = self.client.post("/v1/agents/agent7/execute", json=self.context_json)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Critical Agent 7 internal failure.", response.json()["detail"])

if __name__ == "__main__":
    unittest.main()
