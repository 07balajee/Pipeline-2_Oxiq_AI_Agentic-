import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from services.master_api.app import app
from services.master_api.dependencies import get_master_agent
from agents.master.master_agent import MasterAgent
from schemas.agent_response import AgentResponse
from shared.events.event_bus import event_bus
from agents.master.state_manager import state_manager
from shared.registry.tool_registry import tool_registry
from shared.registry.agent_registry import agent_registry
import uuid

class TestMasterAPI(unittest.TestCase):
    def setUp(self):
        # Save original singletons
        self.original_listeners = dict(event_bus._listeners)
        self.original_states = dict(state_manager._states)
        self.original_tools = dict(tool_registry._tools)
        self.original_agents = dict(agent_registry._agents)
        
        # Instantiate process-scoped MasterAgent
        self.master = MasterAgent()
        
        # Force dependency injection to use this test master instance
        app.dependency_overrides[get_master_agent] = lambda: self.master
        self.client = TestClient(app)
        
        # Candidate and job test payloads
        self.candidate_payload = {
            "candidate_id": "cand-api-123",
            "name": "Alex Mercer",
            "email": "alex.mercer@example.com",
            "resume_url": "CV_AlexMercer.pdf",
            "screening_score": 88.5,
            "job_id": "job-api-999",
            "pipeline_state": "CandidateShortlisted"
        }
        
        self.job_payload = {
            "job_id": "job-api-999",
            "job_title": "AI Architect",
            "technical_criteria": ["Python", "LangChain"],
            "soft_skills_criteria": ["Leadership"],
            "status": "ACTIVE"
        }

    def tearDown(self):
        # Clear overrides and restore singletons
        app.dependency_overrides.clear()
        event_bus._listeners = self.original_listeners
        state_manager._states = self.original_states
        tool_registry._tools = self.original_tools
        agent_registry._agents = self.original_agents

    def test_health_endpoint_returns_200(self):
        """1. Health check returns status healthy."""
        resp = self.client.get("/v1/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "healthy")

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_valid_start_accepted_with_201(self, mock_dispatch):
        """2 & 6. Valid workflow start is accepted, reaches MasterAgent, and returns 201."""
        # Setup mock dispatcher success response
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Meeting scheduled successfully.",
            errors=[],
            warnings=[],
            suggested_action="",
            metadata={"interviewer_name": "Priya", "time_slot": "Monday 10:00 AM", "candidate_id": "cand-api-123"}
        )
        
        resp = self.client.post("/v1/workflow/start", json={
            "candidate_data": self.candidate_payload,
            "job_data": self.job_payload,
            "metadata": {"interactive": False}
        })
        
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("workflow_id", data)
        self.assertEqual(data["status"], "completed")

    def test_malformed_start_returns_422(self):
        """3. Malformed payload returns 422 Validation Error."""
        # Missing candidate_data entirely
        resp = self.client.post("/v1/workflow/start", json={
            "job_data": self.job_payload
        })
        self.assertEqual(resp.status_code, 422)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_correlation_id_propagation(self, mock_dispatch):
        """4 & 5. Correlation ID header is preserved or generated if absent."""
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Meeting scheduled.",
            errors=[],
            metadata={"interviewer_name": "Priya", "time_slot": "Monday 10:00 AM", "candidate_id": "cand-api-123"}
        )
        
        # Scenario A: Supplied in Header
        supplied_corr_id = "supplied-corr-999"
        resp = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload},
            headers={"X-Correlation-ID": supplied_corr_id}
        )
        self.assertEqual(resp.headers.get("X-Correlation-ID"), supplied_corr_id)
        
        # Confirm it was saved to workflow metadata
        wf_id = resp.json()["workflow_id"]
        ctx = self.master.active_contexts[wf_id]
        self.assertEqual(ctx.metadata.get("correlation_id"), supplied_corr_id)
        
        # Scenario B: Generated when absent
        candidate_gen = dict(self.candidate_payload)
        candidate_gen["candidate_id"] = "candidate-corr-gen"
        resp_gen = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": candidate_gen, "job_data": self.job_payload}
        )
        gen_corr_id = resp_gen.headers.get("X-Correlation-ID")
        self.assertIsNotNone(gen_corr_id)
        wf_id_gen = resp_gen.json()["workflow_id"]
        ctx_gen = self.master.active_contexts[wf_id_gen]
        self.assertEqual(ctx_gen.metadata.get("correlation_id"), gen_corr_id)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_human_approval_pause_and_resume_flow(self, mock_dispatch):
        """7, 8, 9 & 10. Start pauses on SlotApproval, resumes, and events update state."""
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Scheduled.",
            errors=[],
            metadata={"interviewer_name": "Priya", "time_slot": "Monday 10:00 AM", "candidate_id": "cand-api-123"}
        )
        
        # 1. Start workflow with interactive checkpoints enabled -> triggers human approval pause
        resp_start = self.client.post(
            "/v1/workflow/start",
            json={
                "candidate_data": self.candidate_payload,
                "job_data": self.job_payload,
                "metadata": {"interactive": True}
            }
        )
        wf_id = resp_start.json()["workflow_id"]
        
        # Verify status is paused
        resp_status = self.client.get(f"/v1/workflow/{wf_id}")
        self.assertEqual(resp_status.status_code, 200)
        self.assertEqual(resp_status.json()["graph_status"], "PAUSED")
        self.assertEqual(resp_status.json()["approval_type"], "SlotApproval")
        
        # 2. Resuming with invalid type or when not paused returns 409
        resp_bad_resume = self.client.post("/v1/workflow/resume", json={
            "workflow_id": wf_id,
            "approval_type": "WrongApprovalType",
            "action": "APPROVE"
        })
        self.assertEqual(resp_bad_resume.status_code, 409)
        
        # 3. Resume with SlotApproval APPROVE continues the thread
        resp_resume = self.client.post("/v1/workflow/resume", json={
            "workflow_id": wf_id,
            "approval_type": "SlotApproval",
            "action": "APPROVE",
            "notes": "Verified."
        })
        self.assertEqual(resp_resume.status_code, 200)
        self.assertEqual(resp_resume.json()["status"], "resumed")
        
        # Confirm state advanced to InterviewScheduled
        status_after = self.client.get(f"/v1/workflow/{wf_id}")
        self.assertEqual(status_after.json()["current_state"], "InterviewScheduled")
        
        # 4. Triggering event on resume state progresses it further
        resp_event = self.client.post("/v1/workflow/event", json={
            "workflow_id": wf_id,
            "event_name": "InterviewStarted"
        })
        self.assertEqual(resp_event.status_code, 200)

    def test_unknown_workflow_routes_return_404(self):
        """11 & 12. Non-existent workflows return 404."""
        bad_wf = "wf-unknown-uuid"
        
        # GET Status
        resp_get = self.client.get(f"/v1/workflow/{bad_wf}")
        self.assertEqual(resp_get.status_code, 404)
        
        # POST Event
        resp_event = self.client.post("/v1/workflow/event", json={
            "workflow_id": bad_wf,
            "event_name": "InterviewStarted"
        })
        self.assertEqual(resp_event.status_code, 404)
        
        # POST Resume
        resp_resume = self.client.post("/v1/workflow/resume", json={
            "workflow_id": bad_wf,
            "approval_type": "SlotApproval",
            "action": "APPROVE"
        })
        self.assertEqual(resp_resume.status_code, 404)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_workflow_start_idempotency(self, mock_dispatch):
        """17 & 18. Workflow start deduplicates using X-Idempotency-Key."""
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Meeting scheduled.",
            errors=[],
            metadata={"interviewer_name": "Priya", "time_slot": "Monday 10:00 AM", "candidate_id": "cand-api-123"}
        )
        
        key = "idem-key-start-test-1"
        
        # First call
        resp1 = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload},
            headers={"X-Idempotency-Key": key}
        )
        self.assertEqual(resp1.status_code, 201)
        wf_id1 = resp1.json()["workflow_id"]
        
        # Second duplicate call
        resp2 = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload},
            headers={"X-Idempotency-Key": key}
        )
        self.assertEqual(resp2.status_code, 201)
        wf_id2 = resp2.json()["workflow_id"]
        
        # Must return the SAME workflow ID without creating a new one
        self.assertEqual(wf_id1, wf_id2)
        
        # Different job or different key can create separate workflow
        key2 = "idem-key-start-test-2"
        self.candidate_payload["candidate_id"] = "candidate-diff-1"
        resp3 = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload},
            headers={"X-Idempotency-Key": key2}
        )
        wf_id3 = resp3.json()["workflow_id"]
        self.assertNotEqual(wf_id1, wf_id3)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_slot_approval_rejection_rescheduling(self, mock_dispatch):
        """8 & SlotApproval rejection behavior."""
        mock_dispatch.return_value = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Scheduled.",
            errors=[],
            metadata={"interviewer_name": "Priya", "time_slot": "Monday 10:00 AM", "candidate_id": "cand-api-123"}
        )
        
        resp = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload, "metadata": {"interactive": True}}
        )
        wf_id = resp.json()["workflow_id"]
        
        # Reject slot approval -> triggers recommendation retry (RetryRequested)
        resp_resume = self.client.post("/v1/workflow/resume", json={
            "workflow_id": wf_id,
            "approval_type": "SlotApproval",
            "action": "REJECT"
        })
        self.assertEqual(resp_resume.status_code, 200)
        
        # Confirm that metadata recorded rejection and cleared scheduled_time slot
        ctx = self.master.active_contexts[wf_id]
        self.assertIn("rejected_recommendations", ctx.metadata)
        self.assertNotIn("scheduled_time", ctx.step_data)

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_offline_fallback_rejection_leaves_paused(self, mock_dispatch):
        """9 & OfflineFallback rejection behavior."""
        # Mock Meet failure to trigger fallback proposals
        mock_dispatch.return_value = AgentResponse(
            execution_status="FAILED",
            generated_event=None,
            updated_state=None,
            summary="Meet creation failed.",
            errors=["Google Meet generation failed."],
            metadata={"candidate_id": "cand-api-123", "interviewer_name": "Priya", "time_slot": "Monday 10:00 AM"}
        )
        
        resp = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload, "metadata": {"interactive": False}}
        )
        wf_id = resp.json()["workflow_id"]
        
        # Verify proposed fallback exists
        status = self.client.get(f"/v1/workflow/{wf_id}")
        self.assertEqual(status.json()["approval_type"], "Offline Interview")
        
        # Reject fallback -> returns False (leaves workflow paused)
        resp_resume = self.client.post("/v1/workflow/resume", json={
            "workflow_id": wf_id,
            "approval_type": "Offline Interview",
            "action": "REJECT"
        })
        # Because reject fallback returns False (remains paused), router returns 409
        self.assertEqual(resp_resume.status_code, 409)
        
        # Verify state is still paused
        status_after = self.client.get(f"/v1/workflow/{wf_id}")
        self.assertEqual(status_after.json()["graph_status"], "PAUSED")

    @patch("agents.master.dispatcher.Dispatcher.dispatch")
    def test_agent6_transport_exhaustion_returns_200_paused(self, mock_dispatch):
        """14 & 15. Downstream Agent 6 transport failures return HTTP 200 and pause workflow status (no 500 error)."""
        # Dispatcher raising connection errors
        from shared.clients.agent_client import AgentTransportError
        mock_dispatch.side_effect = AgentTransportError("agent6", "CONNECTION_ERROR", "Agent 6 is offline.")
        
        resp = self.client.post(
            "/v1/workflow/start",
            json={"candidate_data": self.candidate_payload, "job_data": self.job_payload, "metadata": {"interactive": False}}
        )
        
        # Master API returns HTTP 200 (reception was successful) but state is paused
        self.assertEqual(resp.status_code, 201)
        wf_id = resp.json()["workflow_id"]
        
        # Verify status is paused
        status = self.client.get(f"/v1/workflow/{wf_id}")
        self.assertEqual(status.json()["graph_status"], "PAUSED")
        self.assertIn("Agent 6 is offline", status.json()["failure"])

    def test_unexpected_crash_returns_500(self):
        """16. Global exception handler maps runtime errors to HTTP 500."""
        # Cause an unexpected crash during status query
        with patch.object(self.master, "get_workflow_status", side_effect=RuntimeError("Database corruption!")):
            resp = self.client.get("/v1/workflow/wf-any-id")
            self.assertEqual(resp.status_code, 500)
            self.assertIn("SYSTEM_CRASH", resp.json()["error_code"])
