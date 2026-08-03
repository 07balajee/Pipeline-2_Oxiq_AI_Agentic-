import unittest
from unittest.mock import patch, MagicMock
import httpx
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from shared.clients.agent_client import AgentServiceClient, AgentTransportError
from agents.master.dispatcher import Dispatcher
from schemas.agent_response import AgentResponse

class TestDistributedFailures(unittest.TestCase):
    def setUp(self):
        self.dispatcher = Dispatcher()
        self.candidate_data = {
            "candidate_id": "CAND-FAIL-001",
            "name": "Alex Failure",
            "email": "alex.fail@example.com",
            "resume_url": "CV_AlexFail.pdf",
            "screening_score": 85.0,
            "job_id": "job-abc-123",
            "job_title": "Software Engineer"
        }
        self.context = WorkflowContext(
            workflow_id="wf-test-fail-123",
            candidate=CandidateContext(**self.candidate_data),
            current_state="CandidateShortlisted"
        )

    @patch("httpx.Client.post")
    def test_agent6_service_down(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused on port 8001")
        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent6", self.context)
        self.assertEqual(ctx.exception.agent, "agent6")
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("httpx.Client.post")
    def test_agent7_service_down(self, mock_post):
        self.context.current_state = "TechnicalInterviewPending"
        mock_post.side_effect = httpx.ConnectError("Connection refused on port 8002")
        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent7", self.context)
        self.assertEqual(ctx.exception.agent, "agent7")
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("httpx.Client.post")
    def test_agent8_service_down(self, mock_post):
        self.context.current_state = "HRInterviewPending"
        mock_post.side_effect = httpx.ConnectError("Connection refused on port 8003")
        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent8", self.context)
        self.assertEqual(ctx.exception.agent, "agent8")
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("httpx.Client.post")
    def test_agent_http_timeout(self, mock_post):
        mock_post.side_effect = httpx.ReadTimeout("Request timed out after 30s")
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        with self.assertRaises(AgentTransportError) as ctx:
            client.execute(self.context, agent_name="agent6")
        self.assertEqual(ctx.exception.category, "TIMEOUT")

    @patch("httpx.Client.post")
    def test_agent_http_500_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Exception"
        mock_post.return_value = mock_resp
        
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        with self.assertRaises(AgentTransportError) as ctx:
            client.execute(self.context, agent_name="agent6")
        self.assertEqual(ctx.exception.category, "HTTP_SERVICE_ERROR")
        self.assertEqual(ctx.exception.status_code, 500)

    @patch("httpx.Client.post")
    def test_agent_invalid_json_response(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("Invalid JSON token")
        mock_post.return_value = mock_resp
        
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        with self.assertRaises(AgentTransportError) as ctx:
            client.execute(self.context, agent_name="agent6")
        self.assertEqual(ctx.exception.category, "INVALID_RESPONSE")

    @patch("httpx.Client.post")
    def test_agent_contract_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Missing execution_status attribute
        mock_resp.json.return_value = {"invalid_field": "test"}
        mock_post.return_value = mock_resp
        
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        with self.assertRaises(AgentTransportError) as ctx:
            client.execute(self.context, agent_name="agent6")
        self.assertEqual(ctx.exception.category, "CONTRACT_ERROR")

    @patch("httpx.Client.post")
    def test_agent_business_failure_returns_200_failed(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "execution_status": "FAILED",
            "errors": ["SLOTS_EXHAUSTED"],
            "summary": "Interviewer slots exhausted",
            "metadata": {}
        }
        mock_post.return_value = mock_resp
        
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        resp = client.execute(self.context, agent_name="agent6")
        self.assertEqual(resp.execution_status, "FAILED")
        self.assertEqual(resp.errors, ["SLOTS_EXHAUSTED"])

    @patch("httpx.Client.post")
    def test_service_recovery_after_failure(self, mock_post):
        fail_resp = httpx.ConnectError("Connection refused")
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "InterviewCreated",
            "updated_state": "InterviewScheduled",
            "summary": "Scheduled after recovery",
            "metadata": {}
        }
        mock_post.side_effect = [fail_resp, ok_resp]
        
        client = AgentServiceClient("http://127.0.0.1:8001", timeout=30.0)
        with self.assertRaises(AgentTransportError):
            client.execute(self.context, agent_name="agent6")
            
        resp = client.execute(self.context, agent_name="agent6")
        self.assertEqual(resp.execution_status, "SUCCESS")

if __name__ == "__main__":
    unittest.main()
