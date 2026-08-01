import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.agent_response import AgentResponse
from schemas.mcp_response import MCPResponse
from agents.agent6.agent import InterviewInvitationAgent
from agents.agent6.graph import compile_agent_graph
from agents.agent6.models import InterviewMode, Interviewer, InterviewSlot
from agents.agent6.tools import Agent6ToolsAdapter
from agents.master.master_agent import MasterAgent
from services.agent6_api.app import app as agent6_app
from shared.events.event_bus import event_bus
from shared.events.base_event import BaseEvent

class TestAgent6GraphIntegration(unittest.TestCase):
    def setUp(self):
        self.agent = InterviewInvitationAgent()
        self.candidate_data = {
            "candidate_id": "CAND-001",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "resume_url": "CV_JohnDoe_AIEngineer.pdf",
            "screening_score": 91.0,
            "job_id": "job-abc-123",
            "job_title": "AI Engineer"
        }
        self.candidate_ctx = CandidateContext(**self.candidate_data)
        self.context = WorkflowContext(
            workflow_id="wf-test-123",
            candidate=self.candidate_ctx,
            current_state="CandidateShortlisted",
            metadata={"interactive": False}
        )
        
        # Reset event bus and state managers
        from shared.events.event_bus import event_bus
        self.original_listeners = {k: list(v) for k, v in event_bus._listeners.items()}
        event_bus._listeners.clear()
        
        from agents.master.state_manager import state_manager
        self.original_states = dict(state_manager._states)
        state_manager._states.clear()

        from shared.registry.tool_registry import tool_registry
        from shared.registry.agent_registry import agent_registry
        from shared.config.constants import AGENT_INVITATION
        self.original_tools = dict(tool_registry._tools)
        self.original_agents = dict(agent_registry._agents)
        agent_registry.register(AGENT_INVITATION, InterviewInvitationAgent)

    def tearDown(self):
        from shared.events.event_bus import event_bus
        event_bus._listeners = self.original_listeners
        
        from agents.master.state_manager import state_manager
        state_manager._states = self.original_states

        from shared.registry.tool_registry import tool_registry
        from shared.registry.agent_registry import agent_registry
        tool_registry._tools = self.original_tools
        agent_registry._agents = self.original_agents

    def register_failable_tools(self):
        from shared.registry.tool_registry import tool_registry
        from tests.mocks.failable_clients import (
            FailableCalendarMCPClient,
            FailableMeetMCPClient,
            FailableNotificationMCPClient,
            FailableDatabaseMCPClient,
            FailableDocumentMCPClient,
            FailableResumeMCPClient
        )
        tool_registry.register("resume_mcp", FailableResumeMCPClient)
        tool_registry.register("database_mcp", FailableDatabaseMCPClient)
        tool_registry.register("calendar_mcp", FailableCalendarMCPClient)
        tool_registry.register("meet_mcp", FailableMeetMCPClient)
        tool_registry.register("document_mcp", FailableDocumentMCPClient)
        tool_registry.register("notification_mcp", FailableNotificationMCPClient)

    # 1. Graph compiles
    def test_graph_compiles(self):
        graph = compile_agent_graph()
        self.assertIsNotNone(graph)
        # Verify it can compile and get help details
        self.assertTrue(len(graph.nodes) > 0)

    # 2. Online happy path
    def test_online_happy_path(self):
        self.register_failable_tools()
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, "InterviewCreated")
        self.assertEqual(response.updated_state, "InterviewScheduled")
        self.assertEqual(self.context.step_data["interview_mode"], "Online")
        self.assertIsNotNone(self.context.step_data.get("meeting_link"))

    # 3. Offline happy path
    def test_offline_happy_path(self):
        self.register_failable_tools()
        # Set metadata for Offline mode
        self.context.metadata["interview_mode"] = "Offline"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(self.context.step_data["interview_mode"], "Offline")
        self.assertIsNone(self.context.step_data.get("meeting_link"))

    # 4. Offline skips Meet
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_meeting")
    def test_offline_skips_meet(self, mock_generate_meet):
        self.register_failable_tools()
        self.context.metadata["interview_mode"] = "Offline"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_generate_meet.assert_not_called()

    # 5. Validation failure
    def test_validation_failure(self):
        self.register_failable_tools()
        # Candidate email missing
        self.context.candidate.email = ""
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Candidate Email is missing.", response.errors[0])

    # 6. Resume degraded mode
    def test_resume_degraded_mode(self):
        self.register_failable_tools()
        self.context.metadata["simulate_resume_failure"] = True
        response = self.agent.run(self.context)
        # Should succeed in degraded mode because candidate name and email exist
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertTrue(any("degraded" in w.lower() for w in response.warnings))

    # 7. DB context retrieval
    def test_db_context_retrieval(self):
        self.register_failable_tools()
        initial_state = {
            "workflow_context": self.context,
            "interview_mode": None,
            "selected_interviewer": None,
            "selected_slot": None,
            "interview_object": None,
            "db_update_prepared": None,
            "db_insert_prepared": None,
            "retry_counts": {},
            "last_error": None,
            "failure_category": None,
            "failed_operation": None,
            "warnings": [],
            "agent_response": None
        }
        graph = compile_agent_graph()
        final_state = graph.invoke(initial_state)
        self.assertIsNotNone(final_state.get("candidate_context"))
        self.assertIsNotNone(final_state.get("job_context"))

    # 8. Mode selection
    def test_mode_selection(self):
        self.register_failable_tools()
        initial_state = {
            "workflow_context": self.context,
            "interview_mode": None,
            "selected_interviewer": None,
            "selected_slot": None,
            "interview_object": None,
            "db_update_prepared": None,
            "db_insert_prepared": None,
            "retry_counts": {},
            "last_error": None,
            "failure_category": None,
            "failed_operation": None,
            "warnings": [],
            "agent_response": None
        }
        graph = compile_agent_graph()
        final_state = graph.invoke(initial_state)
        self.assertEqual(final_state["interview_mode"], InterviewMode.ONLINE)

    # 9. Interviewer scoring unchanged
    def test_interviewer_scoring_unchanged(self):
        self.register_failable_tools()
        initial_state = {
            "workflow_context": self.context,
            "interview_mode": InterviewMode.ONLINE,
            "selected_interviewer": None,
            "selected_slot": None,
            "interview_object": None,
            "db_update_prepared": None,
            "db_insert_prepared": None,
            "retry_counts": {},
            "last_error": None,
            "failure_category": None,
            "failed_operation": None,
            "warnings": [],
            "agent_response": None
        }
        graph = compile_agent_graph()
        # Retrieve context first
        db_state = graph.invoke(initial_state)
        self.assertIsNotNone(db_state.get("selected_interviewer"))
        self.assertIsNotNone(db_state.get("interviewer_score_breakdown"))

    # 10. Slot ranking unchanged
    def test_slot_ranking_unchanged(self):
        self.register_failable_tools()
        initial_state = {
            "workflow_context": self.context,
            "interview_mode": InterviewMode.ONLINE,
            "selected_interviewer": Interviewer(interviewer_id="int-1", name="Priya Singh", role="Senior AI Engineer", department="Engineering", email="priya@example.com"),
            "selected_slot": None,
            "interview_object": None,
            "db_update_prepared": None,
            "db_insert_prepared": None,
            "retry_counts": {},
            "last_error": None,
            "failure_category": None,
            "failed_operation": None,
            "warnings": [],
            "agent_response": None
        }
        graph = compile_agent_graph()
        final_state = graph.invoke(initial_state)
        self.assertIsNotNone(final_state.get("selected_slot"))
        self.assertIsNotNone(final_state.get("slot_reason"))

    # 11. Calendar transient retry
    def test_calendar_transient_retry(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        # Simulate Calendar timeout once
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_calendar_timeout_once": True}
        )
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")

    # 12. Calendar retry exhaustion
    def test_calendar_retry_exhaustion(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        # Always fail Calendar
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_calendar_timeout_always": True}
        )
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    # 13. Meet transient retry
    def test_meet_transient_retry(self):
        self.register_failable_tools()
        self.context.metadata["simulate_meet_failure_once"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")

    # 14. Meet exhaustion returns FALLBACK_ELIGIBLE
    def test_meet_exhaustion_returns_fallback_eligible(self):
        self.register_failable_tools()
        self.context.metadata["simulate_meet_failure_always"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata["failed_operation"], "meet")
        self.assertEqual(response.metadata["failure_category"], "FALLBACK_ELIGIBLE")
        self.assertEqual(response.suggested_action, "OFFLINE_FALLBACK")

    # 15. Agent 6 does NOT autonomously switch Offline
    def test_agent6_does_not_autonomously_switch_offline(self):
        self.register_failable_tools()
        self.context.metadata["simulate_meet_failure_always"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        # Ensure we did NOT schedule offline autonomously (scheduled_time/interviewer are not finalized in step_data success state)
        self.assertIsNone(self.context.step_data.get("scheduled_time"))

    # 16. Document retry behavior
    def test_document_retry_behavior(self):
        self.register_failable_tools()
        self.context.metadata["simulate_doc_failure_once"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertIsNotNone(self.context.step_data["packet_id"])

    # 17. DB commit failure triggers compensation
    @patch("agents.agent6.compensation.CompensationManager.compensate")
    def test_db_commit_failure_triggers_compensation(self, mock_compensate):
        self.register_failable_tools()
        self.context.metadata["simulate_db_write_failure"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata["failed_operation"], "database_commit")
        self.assertEqual(response.metadata["failure_category"], "COMPENSATION_REQUIRED")
        mock_compensate.assert_called_once()

    # 18. Notification retry
    def test_notification_retry(self):
        self.register_failable_tools()
        self.context.metadata["simulate_notification_failure_once"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertTrue(self.context.step_data["notification_sent"])

    # 19. booking_id prevents duplicate Calendar reservation
    @patch("agents.agent6.tools.Agent6ToolsAdapter.reserve_slot")
    def test_booking_id_prevents_duplicate_calendar_reservation(self, mock_reserve):
        self.register_failable_tools()
        self.context.step_data["booking_id"] = "bk-existing-123"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_reserve.assert_not_called()

    # 20. meeting_link prevents duplicate Meet creation
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_meeting")
    def test_meeting_link_prevents_duplicate_meet_creation(self, mock_meet):
        self.register_failable_tools()
        self.context.step_data["meeting_link"] = "https://meet.google.com/existing-abc"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_meet.assert_not_called()

    # 21. packet_id prevents duplicate document creation
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_interview_packet")
    def test_packet_id_prevents_duplicate_document_creation(self, mock_doc):
        self.register_failable_tools()
        self.context.step_data["packet_id"] = "pkt-existing-123"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_doc.assert_not_called()

    # 22. db_committed prevents duplicate DB commit
    @patch("agents.agent6.tools.Agent6ToolsAdapter.commit_transaction")
    def test_db_committed_prevents_duplicate_db_commit(self, mock_commit):
        self.register_failable_tools()
        self.context.step_data["db_committed"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_commit.assert_not_called()

    # 23. notification_sent prevents duplicate email
    @patch("agents.agent6.tools.Agent6ToolsAdapter.send_notification")
    def test_notification_sent_prevents_duplicate_email(self, mock_notify):
        self.register_failable_tools()
        self.context.step_data["notification_sent"] = True
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")
        mock_notify.assert_not_called()

    # 24. Operation-specific retry counters
    def test_operation_specific_retry_counters(self):
        self.register_failable_tools()
        initial_state = {
            "workflow_context": self.context,
            "interview_mode": None,
            "selected_interviewer": None,
            "selected_slot": None,
            "interview_object": None,
            "db_update_prepared": None,
            "db_insert_prepared": None,
            "retry_counts": {"calendar": 2, "meet": 0},
            "last_error": None,
            "failure_category": None,
            "failed_operation": None,
            "warnings": [],
            "agent_response": None
        }
        graph = compile_agent_graph()
        final_state = graph.invoke(initial_state)
        # Ensure our calendar retries didn't leak into meet retry counters
        self.assertEqual(final_state["retry_counts"]["meet"], 0)

    # 25. FAILED AgentResponse contract unchanged
    def test_failed_agent_response_contract_unchanged(self):
        self.register_failable_tools()
        self.context.metadata["simulate_calendar_timeout_always"] = True
        response = self.agent.run(self.context)
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIsNone(response.generated_event)
        self.assertIsNone(response.updated_state)
        self.assertTrue(len(response.errors) > 0)

    # 26. SUCCESS AgentResponse contract unchanged
    def test_success_agent_response_contract_unchanged(self):
        self.register_failable_tools()
        response = self.agent.run(self.context)
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, "InterviewCreated")
        self.assertEqual(response.updated_state, "InterviewScheduled")
        self.assertIsNotNone(response.summary)
        self.assertIn("CAND-001", response.metadata["candidate_id"])

    # 27. FastAPI execute contract unchanged
    def test_fastapi_execute_contract_unchanged(self):
        self.register_failable_tools()
        client = TestClient(agent6_app)
        
        # Serialize WorkflowContext for POST request
        payload = self.context.model_dump()
        headers = {
            "X-Correlation-ID": "test-correlation-id",
            "X-Idempotency-Key": "test-idempotency-key"
        }
        
        resp = client.post("/v1/agents/agent6/execute", json=payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        json_data = resp.json()
        self.assertEqual(json_data["execution_status"], "SUCCESS")
        self.assertEqual(json_data["generated_event"], "InterviewCreated")
        self.assertEqual(json_data["updated_state"], "InterviewScheduled")

    # 28. Master HTTP dispatcher requires no changes
    def test_master_http_dispatcher_requires_no_changes(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        # Run workflow from start through CandidateShortlisted event
        workflow_id = master.start_workflow(self.candidate_data, mock_job, metadata={"interactive": False})
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        # Verify master state updated correctly using dispatcher dispatch
        from agents.master.state_manager import state_manager
        wf_state = state_manager.get_state(workflow_id)
        self.assertEqual(wf_state.current_state, "InterviewScheduled")
