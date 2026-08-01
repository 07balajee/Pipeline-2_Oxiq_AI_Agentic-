import unittest
from unittest.mock import patch, MagicMock
import datetime
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.mcp_response import MCPResponse
from agents.agent6.agent import InterviewInvitationAgent
from agents.agent6.models import InterviewMode, Interviewer, InterviewSlot
from agents.agent6.tools import Agent6ToolsAdapter
from agents.master.master_agent import MasterAgent
from shared.events.event_bus import event_bus
from shared.events.base_event import BaseEvent

class TestAgent6(unittest.TestCase):
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
        
        # Reset event bus and state manager to prevent cross-test pollution
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
        # Restore original registries and singletons
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

    def create_mcp_response(self, status="SUCCESS", mcp_name="TestMCP", payload=None, errors=None):
        return MCPResponse(
            status=status,
            mcp_name=mcp_name,
            workflow_id="wf-test-123",
            trace_id="trace-test-123",
            execution_time_ms=10.0,
            payload=payload,
            errors=errors or []
        )

    # =========================================================================
    # ORIGINAL 12 PHASE 4 STEP 1 TESTS (PRESERVED)
    # =========================================================================

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.reserve_slot")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_meeting")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_interview_packet")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.send_notification")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_candidate_update")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_database_payload")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.commit_transaction")
    def test_happy_path_online(
        self, mock_commit, mock_prep_db, mock_prep_cand, mock_notify, mock_doc, 
        mock_meet, mock_reserve, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        # Setup mock responses
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={"summary": "Excellent AI candidate"})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={
                "job_id": "job-abc-123", "job_title": "AI Engineer", 
                "department": "Engineering", "technical_criteria": ["Python", "Transformers"],
                "status": "ACTIVE"
            }
        )
        mock_avail.return_value = self.create_mcp_response(
            mcp_name="CalendarMCP", 
            payload=["Monday 10:00 AM", "Monday 2:00 PM"]
        )
        mock_reserve.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload={"booking_id": "bk-123", "confirmed": True})
        mock_meet.return_value = self.create_mcp_response(mcp_name="MeetMCP", payload={"meeting_url": "https://meet.google.com/mock"})
        mock_doc.return_value = self.create_mcp_response(mcp_name="DocumentMCP", payload={"packet_id": "doc-123"})
        mock_notify.return_value = self.create_mcp_response(mcp_name="NotificationMCP", payload={"sent": True})
        mock_prep_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={"prepared": True})
        mock_prep_db.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={"prepared": True})
        mock_commit.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={"committed": True})

        response = self.agent.run(self.context)

        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, "InterviewCreated")
        self.assertEqual(response.updated_state, "InterviewScheduled")
        self.assertIn("Priya Singh", response.summary)
        self.assertEqual(self.context.step_data["interview_mode"], "Online")
        self.assertEqual(self.context.step_data["scheduled_time"], "Monday 10:00 AM")
        self.assertEqual(response.metadata["interviewer_score"], 80)

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.reserve_slot")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.generate_interview_packet")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.send_notification")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_candidate_update")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_database_payload")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.commit_transaction")
    def test_happy_path_offline(
        self, mock_commit, mock_prep_db, mock_prep_cand, mock_notify, mock_doc, 
        mock_reserve, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        # Setup context for Offline mode
        self.context.metadata["interview_mode"] = "Offline"
        
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={
                "job_id": "job-abc-123", "job_title": "AI Engineer", 
                "department": "Engineering", "technical_criteria": ["Python"],
                "status": "ACTIVE"
            }
        )
        mock_avail.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload=["Monday 10:00 AM"])
        mock_reserve.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload={"booking_id": "bk-123"})
        mock_doc.return_value = self.create_mcp_response(mcp_name="DocumentMCP", payload={"packet_id": "doc-123"})
        mock_notify.return_value = self.create_mcp_response(mcp_name="NotificationMCP", payload={})
        mock_prep_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})
        mock_prep_db.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})
        mock_commit.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})

        response = self.agent.run(self.context)

        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(self.context.step_data["interview_mode"], "Offline")
        self.assertEqual(self.context.step_data["interviewer_id"], "int-1")

    def test_invalid_candidate_missing_fields(self):
        # Missing candidate email
        self.context.candidate.email = ""
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Candidate Email is missing.", response.errors)

    def test_invalid_candidate_screening_score(self):
        self.context.candidate.screening_score = 150 # Invalid range
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Screening Score must be a valid numeric percentage between 0 and 100.", response.errors)

    def test_candidate_not_shortlisted(self):
        self.context.current_state = "HRInterviewPending"
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Invalid workflow state for scheduling", response.errors[0])

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    def test_no_interviewer_available_due_to_blacklist(
        self, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        # Setup mock responses
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={"job_id": "job-abc-123", "job_title": "AI Engineer", "department": "Engineering", "status": "ACTIVE"}
        )
        mock_avail.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload=["Monday 10:00 AM"])
        
        # Blacklist all valid interviewers
        self.context.metadata["rejected_recommendations"] = [
            {"interviewer_id": "int-1", "time_slot": "Monday 10:00 AM"},
            {"interviewer_id": "int-2", "time_slot": "Monday 10:00 AM"},
            {"interviewer_id": "int-4", "time_slot": "Monday 10:00 AM"}
        ]

        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("No eligible interviewer found matching candidate and job requirements.", response.errors)

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    def test_no_calendar_slots(
        self, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={"job_id": "job-abc-123", "job_title": "AI Engineer", "department": "Engineering", "status": "ACTIVE"}
        )
        # Return empty list from calendar
        mock_avail.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload=[])

        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("No eligible interviewer found matching candidate and job requirements.", response.errors)

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    def test_rejected_recommendation_blacklist_filtering(
        self, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={"job_id": "job-abc-123", "job_title": "AI Engineer", "department": "Engineering", "status": "ACTIVE"}
        )
        mock_avail.return_value = self.create_mcp_response(
            mcp_name="CalendarMCP", 
            payload=["Monday 10:00 AM", "Monday 2:00 PM"]
        )

        # Reject Priya's first slot (Monday 10:00 AM)
        self.context.metadata["rejected_recommendations"] = [
            {"interviewer_id": "int-1", "time_slot": "Monday 10:00 AM"}
        ]

        with patch("agents.agent6.tools.Agent6ToolsAdapter.reserve_slot") as mock_reserve, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.generate_meeting") as mock_meet, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.generate_interview_packet") as mock_doc, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.send_notification") as mock_notify, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_candidate_update") as mock_prep_cand, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.prepare_database_payload") as mock_prep_db, \
             patch("agents.agent6.tools.Agent6ToolsAdapter.commit_transaction") as mock_commit:
             
            mock_reserve.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload={"booking_id": "bk-123"})
            mock_meet.return_value = self.create_mcp_response(mcp_name="MeetMCP", payload={"meeting_url": "mock"})
            mock_doc.return_value = self.create_mcp_response(mcp_name="DocumentMCP", payload={})
            mock_notify.return_value = self.create_mcp_response(mcp_name="NotificationMCP", payload={})
            mock_prep_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})
            mock_prep_db.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})
            mock_commit.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload={})

            response = self.agent.run(self.context)

            self.assertEqual(response.execution_status, "SUCCESS")
            # Should select Monday 2:00 PM (since Monday 10:00 AM is blacklisted)
            self.assertEqual(self.context.step_data["scheduled_time"], "Monday 2:00 PM")
            self.assertEqual(self.context.step_data["interviewer_id"], "int-1")

    def test_duplicate_scheduling_error(self):
        self.context.step_data["scheduled_time"] = "Monday 10:00 AM"
        # Attempt running without reschedule flag
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Candidate has already been scheduled for an interview.", response.errors)

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    def test_calendar_mcp_failure(
        self, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={"job_id": "job-abc-123", "job_title": "AI Engineer", "department": "Engineering", "status": "ACTIVE"}
        )
        # Calendar MCP fails
        mock_avail.return_value = self.create_mcp_response(mcp_name="CalendarMCP", status="FAILED", errors=["Calendar connection timeout"])

        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Calendar MCP query failed", response.errors[0])

    @patch("agents.agent6.tools.Agent6ToolsAdapter.get_resume_summary")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_candidate")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.read_job")
    @patch("agents.agent6.tools.Agent6ToolsAdapter.fetch_calendar_availability")
    def test_calendar_mcp_malformed_response(
        self, mock_avail, mock_read_job, mock_read_cand, mock_resume
    ):
        mock_resume.return_value = self.create_mcp_response(mcp_name="ResumeMCP", payload={})
        mock_read_cand.return_value = self.create_mcp_response(mcp_name="DatabaseMCP", payload=self.candidate_data)
        mock_read_job.return_value = self.create_mcp_response(
            mcp_name="DatabaseMCP", 
            payload={"job_id": "job-abc-123", "job_title": "AI Engineer", "department": "Engineering", "status": "ACTIVE"}
        )
        # Malformed payload (not a list)
        mock_avail.return_value = self.create_mcp_response(mcp_name="CalendarMCP", payload="Monday 10:00 AM")

        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertIn("Malformed Calendar response", response.errors[0])

    @patch("builtins.input")
    def test_interactive_mode_invalid_input_retry(self, mock_input):
        # Mock interactive ModeSelector input sequence:
        # 1. "invalid_choice"
        # 2. "1" (Online)
        mock_input.side_effect = ["invalid_choice", "1"]
        from agents.agent6.mode_selector import ModeSelector
        mode_selector = ModeSelector()
        self.context.metadata["interactive"] = True
        
        mode = mode_selector.select_mode(self.context)
        self.assertEqual(mode, InterviewMode.ONLINE)
        self.assertEqual(mock_input.call_count, 2)


    # =========================================================================
    # NEW 18 FAILURE, RETRY, FALLBACK & IDEMPOTENCY HARDENING TESTS
    # =========================================================================

    def test_calendar_timeout_then_success(self):
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
        # Should recover on retry and transition to InterviewScheduled
        self.assertEqual(context.current_state, "InterviewScheduled")
        self.assertEqual(context.step_data["scheduled_time"], "Monday 10:00 AM")

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
        
        # Should stop after retries and remain WorkflowPaused
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    def test_empty_slots_next_interviewer(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        # Priya has empty availability
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_empty_slots": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        # Falls back to Aman Verma (int-2) because Priya Singh has empty availability
        self.assertEqual(context.current_state, "InterviewScheduled")
        self.assertEqual(context.step_data["interviewer_id"], "int-2")

    def test_all_interviewers_unavailable(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        # All interviewers are unavailable
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_all_interviewers_unavailable": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    def test_meet_failure_then_success(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_meet_failure_once": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")

    def test_meet_exhaustion_offline_fallback(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        # Always fail Meet
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_meet_failure_always": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        # Should propose Offline fallback and pause execution (WorkflowPaused)
        context = master.active_contexts[workflow_id]
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")
        self.assertEqual(context.metadata.get("proposed_fallback"), "Offline Interview")

    def test_human_rejects_offline_fallback(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_meet_failure_always": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")
        
        # User rejects (does not proceed, remains paused)
        self.assertEqual(context.metadata.get("proposed_fallback"), "Offline Interview")

    def test_db_read_temporary_failure(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_db_read_failure_once": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")

    def test_db_read_terminal_failure(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_db_read_failure_always": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    def test_db_final_write_failure(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_db_write_failure": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")
        # Assert database rollback/compensation logs are written
        self.assertIn("compensation_log", context.metadata)
        self.assertTrue(context.metadata["compensation_log"][0]["rolled_back_db"])
        self.assertTrue(context.metadata["compensation_log"][0]["cancelled_booking"])

    def test_notification_temporary_failure(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_notification_failure_once": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")
        self.assertTrue(context.step_data["notification_sent"])

    def test_notification_retry_exhaustion(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_notification_failure_always": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    def test_doc_generation_failure(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_doc_failure_once": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")
        self.assertIsNotNone(context.step_data["packet_id"])

    def test_resume_degraded_mode(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_resume_failure": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        self.assertEqual(context.current_state, "InterviewScheduled")
        self.assertTrue(context.metadata.get("degraded_mode"))
        self.assertEqual(context.metadata.get("degraded_reason"), "Resume MCP unavailable")

    def test_malformed_mcp_response(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_mcp_malformed": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        from agents.master.state_manager import state_manager
        self.assertEqual(state_manager.get_state(workflow_id).current_state, "WorkflowPaused")

    def test_duplicate_prevention_during_retry(self):
        # Verify that retries skip previously created resources by checking execution checkpoint keys
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_notification_failure_once": True}
        )
        
        # Run execution loop
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        # Assert same idempotency keys are retained and not duplicated
        self.assertEqual(context.step_data["calendar_reservation_idempotency_key"], "pl2:CAND-001:agent6:calendar_reservation")
        self.assertEqual(context.step_data["meet_creation_idempotency_key"], "pl2:CAND-001:agent6:meet_creation")
        self.assertEqual(context.step_data["document_generation_idempotency_key"], "pl2:CAND-001:agent6:document_generation")

    def test_retry_limit_enforcement(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_notification_failure_always": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        # Should pause at exactly MAX_RETRY_ATTEMPTS (3)
        self.assertEqual(context.metadata.get("retry_count"), 3)

    def test_successful_recovery_preserves_state(self):
        self.register_failable_tools()
        master = MasterAgent()
        mock_job = {
            "job_id": "job-abc-123", "job_title": "AI Engineer",
            "department": "Engineering", "technical_criteria": ["Python"],
            "status": "ACTIVE"
        }
        
        workflow_id = master.start_workflow(
            self.candidate_data, mock_job,
            metadata={"interactive": False, "simulate_meet_failure_once": True}
        )
        
        event_bus.publish(BaseEvent(name="CandidateShortlisted", candidate_id="CAND-001"))
        
        context = master.active_contexts[workflow_id]
        # Checks that workflow context properties survived retry re-entry correctly
        self.assertEqual(context.candidate.candidate_id, "CAND-001")
        self.assertEqual(context.candidate.email, "john.doe@example.com")
        self.assertEqual(context.current_state, "InterviewScheduled")

if __name__ == "__main__":
    unittest.main()
