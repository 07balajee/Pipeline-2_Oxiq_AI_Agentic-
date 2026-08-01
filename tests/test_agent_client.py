import unittest
from unittest.mock import patch, MagicMock
import httpx
from shared.clients.agent_client import AgentServiceClient, AgentTransportError
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.agent_response import AgentResponse

class TestAgentServiceClient(unittest.TestCase):
    def setUp(self):
        # Configure client with standard setting variables
        self.client = AgentServiceClient(service_url="http://127.0.0.1:8001", timeout=30.0)
        self.candidate = CandidateContext(
            candidate_id="CAND-001",
            name="John Doe",
            email="john.doe@example.com",
            resume_url="CV_JohnDoe_AIEngineer.pdf",
            screening_score=91.0,
            job_id="job-abc-123",
            job_title="AI Engineer"
        )
        self.context = WorkflowContext(
            workflow_id="wf-test-123",
            candidate=self.candidate,
            current_state="CandidateShortlisted",
            metadata={"interactive": False}
        )

    @patch("httpx.Client.post")
    def test_successful_http_agent_response_parsing(self, mock_post):
        """
        1. Successful HTTP post is correctly parsed into a SUCCESS AgentResponse.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "InterviewCreated",
            "updated_state": "InterviewScheduled",
            "summary": "Interview scheduled successfully.",
            "errors": [],
            "warnings": [],
            "suggested_action": None,
            "metadata": {}
        }
        mock_post.return_value = mock_response

        res = self.client.execute(self.context)
        self.assertEqual(res.execution_status, "SUCCESS")
        self.assertEqual(res.generated_event, "InterviewCreated")
        
        # Verify idempotency key and correlation ID headers sent
        args, kwargs = mock_post.call_args
        headers = kwargs["headers"]
        self.assertEqual(headers["X-Correlation-ID"], "wf-test-123")
        self.assertEqual(headers["X-Idempotency-Key"], "pl2:wf-test-123:agent6:CandidateShortlisted")

    @patch("httpx.Client.post")
    def test_business_failed_agent_response_returned_normally(self, mock_post):
        """
        2. Business-level failed status returns HTTP 200 and parsed normally.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "execution_status": "FAILED",
            "generated_event": None,
            "updated_state": None,
            "summary": "No slots found.",
            "errors": ["SLOT_EXHAUSTED"],
            "warnings": [],
            "suggested_action": "escalate",
            "metadata": {}
        }
        mock_post.return_value = mock_response

        res = self.client.execute(self.context)
        self.assertEqual(res.execution_status, "FAILED")
        self.assertIn("SLOT_EXHAUSTED", res.errors)

    @patch("httpx.Client.post")
    def test_connection_failure_classified_correctly(self, mock_post):
        """
        3. Connection errors are classified as CONNECTION_ERROR.
        """
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        with self.assertRaises(AgentTransportError) as ctx:
            self.client.execute(self.context)
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("httpx.Client.post")
    def test_http_timeout_classified_correctly(self, mock_post):
        """
        4. Request timeouts are classified as TIMEOUT.
        """
        mock_post.side_effect = httpx.ReadTimeout("Timeout reading response")
        with self.assertRaises(AgentTransportError) as ctx:
            self.client.execute(self.context)
        self.assertEqual(ctx.exception.category, "TIMEOUT")

    @patch("httpx.Client.post")
    def test_http_service_error(self, mock_post):
        """
        5. Internal/unavailable service codes (5xx) are classified as HTTP_SERVICE_ERROR.
        """
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_post.return_value = mock_response

        with self.assertRaises(AgentTransportError) as ctx:
            self.client.execute(self.context)
        self.assertEqual(ctx.exception.category, "HTTP_SERVICE_ERROR")
        self.assertEqual(ctx.exception.status_code, 503)

    @patch("httpx.Client.post")
    def test_malformed_json_classified_as_invalid_response(self, mock_post):
        """
        6. Non-JSON responses are classified as INVALID_RESPONSE.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid control character")
        mock_post.return_value = mock_response

        with self.assertRaises(AgentTransportError) as ctx:
            self.client.execute(self.context)
        self.assertEqual(ctx.exception.category, "INVALID_RESPONSE")

    @patch("httpx.Client.post")
    def test_schema_invalid_json_classified_as_contract_error(self, mock_post):
        """
        7. JSON responses missing contract fields are classified as CONTRACT_ERROR.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Missing required fields like execution_status
        mock_response.json.return_value = {"unrelated_field": "val"}
        mock_post.return_value = mock_response

        with self.assertRaises(AgentTransportError) as ctx:
            self.client.execute(self.context)
        self.assertEqual(ctx.exception.category, "CONTRACT_ERROR")
