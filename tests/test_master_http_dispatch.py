import unittest
from unittest.mock import patch, MagicMock
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.agent_response import AgentResponse
from agents.master.dispatcher import Dispatcher
from shared.clients.agent_client import AgentTransportError

class TestMasterHttpDispatch(unittest.TestCase):
    def setUp(self):
        self.dispatcher = Dispatcher()
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

    @patch("shared.clients.agent_client.AgentServiceClient.execute")
    def test_agent6_routes_through_http_client(self, mock_execute):
        """
        11. agent6 requests are routed through the HTTP AgentServiceClient.
        """
        mock_execute.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Success",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        res = self.dispatcher.dispatch("agent6", self.context)
        self.assertEqual(res.execution_status, "SUCCESS")
        mock_execute.assert_called_once_with(self.context, agent_name="agent6")

    @patch("shared.registry.agent_registry.AgentRegistry.get_agent")
    @patch("shared.clients.agent_client.AgentServiceClient.execute")
    def test_agent6_does_not_call_agent_registry(self, mock_execute, mock_get_agent):
        """
        12. When agent6 is NOT registered locally (production path), dispatch routes
        through HTTP and does NOT instantiate agent6 from registry.
        """
        # Simulate production: agent6 is not registered in the local registry
        mock_get_agent.side_effect = KeyError("Agent 'agent6' is not registered")
        mock_execute.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Success",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        self.dispatcher.dispatch("agent6", self.context)
        # HTTP client must have been used
        mock_execute.assert_called_once()

    @patch("shared.clients.agent_client.AgentServiceClient.execute")
    def test_agent7_uses_http_dispatch(self, mock_execute):
        """
        agent7 (Technical assessment) dispatches via AgentServiceClient over HTTP to port 8002.
        """
        mock_execute.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="TechnicalScoreSubmitted",
            updated_state="TechnicalInterviewCompleted",
            summary="Assessment passed.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        res = self.dispatcher.dispatch("agent7", self.context)
        self.assertEqual(res.execution_status, "SUCCESS")
        mock_execute.assert_called_once()

    @patch("httpx.Client.post")
    def test_agent7_service_down_raises_transport_error(self, mock_post):
        """
        When Agent 7 HTTP service is unavailable, Dispatcher raises AgentTransportError without local fallback.
        """
        import httpx
        from shared.clients.agent_client import AgentTransportError
        mock_post.side_effect = httpx.ConnectError("Connection refused on port 8002")

        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent7", self.context)

        self.assertIn("agent7", ctx.exception.agent)
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("shared.clients.agent_client.AgentServiceClient.execute")
    def test_agent8_uses_http_dispatch(self, mock_execute):
        """
        agent8 (HR assessment & re-ranking) dispatches via AgentServiceClient over HTTP to port 8003.
        """
        mock_execute.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="HRScoreSubmitted",
            updated_state="HRInterviewCompleted",
            summary="Ranks compiled.",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        res = self.dispatcher.dispatch("agent8", self.context)
        self.assertEqual(res.execution_status, "SUCCESS")
        mock_execute.assert_called_once()

    @patch("httpx.Client.post")
    def test_agent8_service_down_raises_transport_error(self, mock_post):
        """
        When Agent 8 HTTP service is unavailable, Dispatcher raises AgentTransportError without local fallback.
        """
        import httpx
        from shared.clients.agent_client import AgentTransportError
        mock_post.side_effect = httpx.ConnectError("Connection refused on port 8003")

        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent8", self.context)

        self.assertIn("agent8", ctx.exception.agent)
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")

    @patch("shared.clients.agent_client.AgentServiceClient.execute")
    def test_agent6_transport_failure_propagates(self, mock_execute):
        """
        16. Agent 6 transport failures are raised and reach the Master Agent without silent local recovery.
        """
        mock_execute.side_effect = AgentTransportError(
            agent="agent6",
            category="CONNECTION_ERROR",
            message="Connection refused."
        )

        with self.assertRaises(AgentTransportError) as ctx:
            self.dispatcher.dispatch("agent6", self.context)
        self.assertEqual(ctx.exception.category, "CONNECTION_ERROR")
