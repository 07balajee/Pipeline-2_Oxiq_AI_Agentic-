import unittest
from unittest.mock import patch, MagicMock
from langchain_core.runnables import RunnableConfig
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.agent_response import AgentResponse
from shared.clients.agent_client import AgentTransportError
from agents.master.graph import compile_workflow_graph
from agents.master.master_agent import MasterAgent

class TestMasterGraph(unittest.TestCase):
    def setUp(self):
        # We initialize MasterAgent to reuse its dependencies, validator instances, and active collections.
        self.master = MasterAgent()
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
        self.master.active_contexts["wf-test-123"] = self.context
        self.master.active_timelines["wf-test-123"] = MagicMock()
        self.master.active_traces["wf-test-123"] = MagicMock()
        
        # Save initial state in DB state_manager
        from schemas.workflow_state import WorkflowStateModel
        from agents.master.state_manager import state_manager
        initial_state = WorkflowStateModel(
            workflow_id="wf-test-123",
            candidate_id="CAND-001",
            current_state="CandidateShortlisted",
            current_step="IntakeInitialization"
        )
        state_manager.save_state(initial_state)
        
        self.graph = compile_workflow_graph()
        self.config = self.master._build_graph_config("wf-test-123")

    def test_graph_builds_successfully(self):
        """
        1. Compiling the StateGraph creates a valid LangGraph application.
        """
        self.assertIsNotNone(self.graph)
        self.assertTrue(hasattr(self.graph, "invoke"))

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_valid_shortlist_routes_to_agent6(self, mock_dispatch):
        """
        2 & 3. Route node correctly resolves AGENT_INVITATION (agent6) for CandidateShortlisted event.
        """
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Success",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={"candidate_id": "CAND-001", "time_slot": "Monday 10:00 AM", "interviewer_name": "Priya Singh"}
        )
        
        res = self.graph.invoke({
            "workflow_context": self.context,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, self.config)
        
        self.assertEqual(res["target_agent"], "agent6")
        self.assertEqual(res["next_state"], "InterviewScheduling")
        mock_dispatch.assert_called_once()

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_successful_response_advances_graph_state(self, mock_dispatch):
        """
        5. A successful worker response transitions the state machine correctly.
        """
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Success",
            errors=[],
            warnings=[],
            suggested_action=None,
            metadata={"candidate_id": "CAND-001", "time_slot": "Monday 10:00 AM", "interviewer_name": "Priya Singh"}
        )

        res = self.graph.invoke({
            "workflow_context": self.context,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, self.config)
        
        # In a single event turn, CandidateShortlisted event transitions state to InterviewScheduling
        self.assertEqual(res["workflow_context"].current_state, "InterviewScheduling")
        self.assertEqual(res["agent_response"].generated_event, "InterviewCreated")
        self.assertEqual(res["graph_status"], "EVENT_COMPLETED")

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_transport_connection_error_enters_retry_loop(self, mock_dispatch):
        """
        7 & 8. Transport connection errors (Errno 61 refused) trigger Master-level retry counts.
        """
        mock_dispatch.side_effect = AgentTransportError(
            agent="agent6",
            category="CONNECTION_ERROR",
            message="Connection refused."
        )

        res = self.graph.invoke({
            "workflow_context": self.context,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, self.config)
        
        # Max retries (3) should execute and exhaust
        self.assertEqual(res["workflow_context"].metadata.get("retry_count"), 3)
        # Verify it results in a service paused/failed status and NO Offline Fallback was applied
        self.assertEqual(res["graph_status"], "FAILED")
        self.assertNotIn("proposed_fallback", res["workflow_context"].metadata)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_business_failed_eligible_enters_fallback_offline(self, mock_dispatch):
        """
        6, 10 & C. Business failed outcomes eligible for offline fallback propose offline modes.
        """
        # Simulate Meet creation failure outcome from agent response
        mock_dispatch.return_value = AgentResponse(
            execution_status="FAILED",
            generated_event=None,
            updated_state=None,
            summary="Virtual meeting creation failed.",
            errors=["Google Meet generation failed"],
            warnings=[],
            suggested_action=None,
            metadata={}
        )

        res = self.graph.invoke({
            "workflow_context": self.context,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, self.config)
        
        # Exhausting retry attempts for fallback eligible failure proposes fallback
        self.assertEqual(res["workflow_context"].metadata.get("proposed_fallback"), "Offline Interview")
        self.assertEqual(res["graph_status"], "PAUSED")

    def test_human_approval_interrupt_pause_and_resume(self):
        """
        11, 12 & F. Transition requiring approval interrupts, pauses graph state, and resumes correctly.
        """
        # Set state to InterviewScheduling where slot approval transition occurs
        self.context.current_state = "InterviewScheduling"
        
        # Enable interactive checkpoints
        self.context.metadata["interactive"] = True
        
        # 1. Start execution -> should interrupt before human_approval_node on SlotApproval state shift
        config = {"configurable": {"thread_id": "thread-hitl-test", **self.config["configurable"]}}
        
        res = self.graph.invoke({
            "workflow_context": self.context,
            "incoming_event": "InterviewCreated",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, config)
        
        # Graph should halt at human approval gate
        thread_state = self.graph.get_state(config)
        self.assertEqual(thread_state.next, ("human_approval_node",))
        
        # 2. Update state to simulate approval resumption
        self.context.metadata["pending_next_state"] = "InterviewScheduled"
        self.context.metadata["paused_on_approval"] = "SlotApproval"
        self.graph.update_state(config, {"workflow_context": self.context})
        
        # Resume invoke
        res_resumed = self.graph.invoke(None, config)
        
        self.assertEqual(res_resumed["workflow_context"].current_state, "InterviewScheduled")
        self.assertEqual(res_resumed["graph_status"], "EVENT_COMPLETED")

    def test_thread_id_isolation(self):
        """
        G. Different thread IDs isolate candidate execution state checkpoints.
        """
        config_a = {"configurable": {"thread_id": "thread-candidate-A", **self.config["configurable"]}}
        config_b = {"configurable": {"thread_id": "thread-candidate-B", **self.config["configurable"]}}
        
        ctx_a = WorkflowContext(
            workflow_id="wf-A",
            candidate=self.candidate,
            current_state="CandidateShortlisted",
            metadata={"interactive": False}
        )
        ctx_b = WorkflowContext(
            workflow_id="wf-B",
            candidate=self.candidate,
            current_state="CandidateShortlisted",
            metadata={"interactive": False}
        )
        
        # Register in state manager
        from schemas.workflow_state import WorkflowStateModel
        from agents.master.state_manager import state_manager
        state_manager.save_state(WorkflowStateModel(
            workflow_id="wf-A",
            candidate_id="CAND-001",
            current_state="CandidateShortlisted",
            current_step="IntakeInitialization"
        ))
        state_manager.save_state(WorkflowStateModel(
            workflow_id="wf-B",
            candidate_id="CAND-001",
            current_state="CandidateShortlisted",
            current_step="IntakeInitialization"
        ))
        
        # Mocks for timeline and traces
        self.master.active_timelines["wf-A"] = MagicMock()
        self.master.active_traces["wf-A"] = MagicMock()
        self.master.active_timelines["wf-B"] = MagicMock()
        self.master.active_traces["wf-B"] = MagicMock()
        
        self.graph.invoke({
            "workflow_context": ctx_a,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, config_a)
        
        state_b = self.graph.invoke({
            "workflow_context": ctx_b,
            "incoming_event": "CandidateShortlisted",
            "event_payload": {},
            "target_agent": None,
            "next_state": None,
            "agent_response": None,
            "transport_error": None,
            "graph_status": "RUNNING"
        }, config_b)
        
        # Checking B's run thread does not inherit A's thread checkpoints
        self.assertEqual(state_b["workflow_context"].workflow_id, "wf-B")

    def test_no_direct_agent_imports(self):
        """
        15 & H. Verify graph code does not directly reference or import InterviewInvitationAgent.
        """
        with open("agents/master/graph/nodes.py", "r") as f:
            code = f.read()
        self.assertNotIn("InterviewInvitationAgent", code)
        self.assertNotIn("agents.agent6", code)
