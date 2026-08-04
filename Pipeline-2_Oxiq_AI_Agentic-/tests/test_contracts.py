import unittest
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from schemas.agent_response import AgentResponse
from agents.agent6.response_builder import ResponseBuilder
from agents.master.orchestrator.response_validator import ResponseValidator
from agents.master.router import Router
from shared.config.constants import (
    STATE_INTERVIEW_SCHEDULED,
    STATE_TECHNICAL_INTERVIEW_PENDING,
    STATE_TECHNICAL_INTERVIEW_COMPLETED,
    STATE_HR_INTERVIEW_PENDING,
    EVENT_INTERVIEW_STARTED,
    EVENT_TRIGGER_HR_ROUND,
    AGENT_TECHNICAL,
    AGENT_HR_RANKING
)

class TestContracts(unittest.TestCase):
    def setUp(self):
        self.validator = ResponseValidator()
        self.router = Router()
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
            workflow_id="wf-test-contract-123",
            candidate=self.candidate_ctx,
            current_state="CandidateShortlisted",
            metadata={"interactive": False}
        )

    def test_agent6_input_contract_acceptance(self):
        # Verify that WorkflowContext holds all fields required by the agent input contract
        self.assertEqual(self.context.workflow_id, "wf-test-contract-123")
        self.assertEqual(self.context.candidate.candidate_id, "CAND-001")
        self.assertEqual(self.context.candidate.job_id, "job-abc-123")
        self.assertEqual(self.context.candidate.name, "John Doe")
        self.assertEqual(self.context.candidate.email, "john.doe@example.com")
        self.assertEqual(self.context.candidate.screening_score, 91.0)
        self.assertEqual(self.context.candidate.resume_url, "CV_JohnDoe_AIEngineer.pdf")
        self.assertEqual(self.context.current_state, "CandidateShortlisted")
        self.assertIsInstance(self.context.step_data, dict)
        self.assertIsInstance(self.context.metadata, dict)
        self.assertIsInstance(self.context.history, list)

    def test_response_validator_rejects_missing_status(self):
        # A response must report execution_status SUCCESS to pass validator (or statuscheck errors will trigger)
        resp = AgentResponse(
            execution_status="FAILED",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Test summary",
            metadata={"candidate_id": "CAND-001", "time_slot": "Monday 10:00 AM", "interviewer_name": "Priya Singh"}
        )
        is_valid, errors = self.validator.validate_response("agent6", resp)
        self.assertFalse(is_valid)
        self.assertTrue(any("reported status: 'FAILED'" in err for err in errors))

    def test_response_validator_rejects_missing_event_or_state(self):
        # Reject missing generated_event or updated_state
        resp = AgentResponse(
            execution_status="SUCCESS",
            summary="Test summary",
            metadata={"candidate_id": "CAND-001", "time_slot": "Monday 10:00 AM", "interviewer_name": "Priya Singh"}
        )
        is_valid, errors = self.validator.validate_response("agent6", resp)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing required attribute: 'generated_event'" in err for err in errors))
        self.assertTrue(any("missing required attribute: 'updated_state'" in err for err in errors))

    def test_response_validator_rejects_missing_agent6_metadata(self):
        # Agent 6 must compile booking details in metadata
        resp = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Test summary",
            metadata={}
        )
        is_valid, errors = self.validator.validate_response("agent6", resp)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing 'candidate_id'" in err for err in errors))
        self.assertTrue(any("missing 'time_slot'" in err for err in errors))
        self.assertTrue(any("missing 'interviewer_name'" in err for err in errors))

    def test_response_validator_accepts_valid_agent6_response(self):
        resp = AgentResponse(
            execution_status="SUCCESS",
            generated_event="InterviewCreated",
            updated_state="InterviewScheduled",
            summary="Test summary",
            metadata={"candidate_id": "CAND-001", "time_slot": "Monday 10:00 AM", "interviewer_name": "Priya Singh"}
        )
        is_valid, errors = self.validator.validate_response("agent6", resp)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_master_routing_for_agent7_and_agent8(self):
        # Route transitions verify Mock Agent 7 and Mock Agent 8 routability
        next_state, target_agent = self.router.route(STATE_INTERVIEW_SCHEDULED, EVENT_INTERVIEW_STARTED)
        self.assertEqual(next_state, STATE_TECHNICAL_INTERVIEW_PENDING)
        self.assertEqual(target_agent, AGENT_TECHNICAL)

        next_state, target_agent = self.router.route(STATE_TECHNICAL_INTERVIEW_COMPLETED, EVENT_TRIGGER_HR_ROUND)
        self.assertEqual(next_state, STATE_HR_INTERVIEW_PENDING)
        self.assertEqual(target_agent, AGENT_HR_RANKING)

    def test_agent7_and_agent8_responses_validate_successfully(self):
        # Validate that standard stub responses from Agent 7, and Agent 8's
        # real Turn 1 (HR evaluation form generation) response, are valid.
        from agents.agent7.agent import TechnicalInterviewAgent
        from agents.agent8.agent import HRInterviewAgent

        agent7 = TechnicalInterviewAgent()
        agent8 = HRInterviewAgent()

        resp7 = agent7.run(self.context)
        is_valid7, errors7 = self.validator.validate_response("agent7", resp7)
        self.assertTrue(is_valid7)
        self.assertEqual(len(errors7), 0)

        # Agent 8 dispatches Turn 1 from STATE_HR_INTERVIEW_PENDING (see
        # agents/master/router.py); it seeds its own demo DB rows, so no
        # further fixture setup is required here.
        self.context.current_state = STATE_HR_INTERVIEW_PENDING
        resp8 = agent8.run(self.context)
        is_valid8, errors8 = self.validator.validate_response("agent8", resp8)
        self.assertTrue(is_valid8)
        self.assertEqual(len(errors8), 0)
        self.assertEqual(resp8.generated_event, "HREvaluationRequested")
        self.assertEqual(resp8.updated_state, "HREvaluationAwaited")
