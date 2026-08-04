import unittest
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from agents.agent8.agent import HRInterviewAgent
from agents.master.router import Router
from shared.config.constants import (
    STATE_TECHNICAL_INTERVIEW_COMPLETED,
    STATE_HR_INTERVIEW_PENDING,
    STATE_HR_EVALUATION_AWAITED,
    STATE_HR_RANKING_PENDING,
    STATE_CANDIDATE_RANKING_AWAITED,
    STATE_HR_INTERVIEW_COMPLETED,
    STATE_CANDIDATE_SELECTED,
    EVENT_TRIGGER_HR_ROUND,
    EVENT_HR_EVALUATION_REQUESTED,
    EVENT_HR_EVALUATION_SUBMITTED,
    EVENT_HR_SCORE_SUBMITTED,
    EVENT_CANDIDATE_RANKING_APPROVED,
    EVENT_CANDIDATE_RANKED,
    AGENT_HR_RANKING,
)


class TestAgent8Router(unittest.TestCase):
    def setUp(self):
        self.router = Router()

    def test_agent8_three_turn_routing(self):
        next_state, target_agent = self.router.route(STATE_TECHNICAL_INTERVIEW_COMPLETED, EVENT_TRIGGER_HR_ROUND)
        self.assertEqual(next_state, STATE_HR_INTERVIEW_PENDING)
        self.assertEqual(target_agent, AGENT_HR_RANKING)

        next_state, target_agent = self.router.route(STATE_HR_INTERVIEW_PENDING, EVENT_HR_EVALUATION_REQUESTED)
        self.assertEqual(next_state, STATE_HR_EVALUATION_AWAITED)
        self.assertIsNone(target_agent)

        next_state, target_agent = self.router.route(STATE_HR_EVALUATION_AWAITED, EVENT_HR_EVALUATION_SUBMITTED)
        self.assertEqual(next_state, STATE_HR_RANKING_PENDING)
        self.assertEqual(target_agent, AGENT_HR_RANKING)

        next_state, target_agent = self.router.route(STATE_HR_RANKING_PENDING, EVENT_HR_SCORE_SUBMITTED)
        self.assertEqual(next_state, STATE_CANDIDATE_RANKING_AWAITED)
        self.assertIsNone(target_agent)

        next_state, target_agent = self.router.route(STATE_CANDIDATE_RANKING_AWAITED, EVENT_CANDIDATE_RANKING_APPROVED)
        self.assertEqual(next_state, STATE_HR_INTERVIEW_COMPLETED)
        self.assertEqual(target_agent, AGENT_HR_RANKING)

        next_state, target_agent = self.router.route(STATE_HR_INTERVIEW_COMPLETED, EVENT_CANDIDATE_RANKED)
        self.assertEqual(next_state, STATE_CANDIDATE_SELECTED)
        self.assertIsNone(target_agent)


class TestAgent8ThreeTurns(unittest.TestCase):
    """agents/agent8/store.py's mock MCPs are a process-lifetime singleton
    (by design, so state survives across the separate dispatches that make
    up Turn 1/2/3 - see agents/agent8/store.py's module docstring). That
    means test methods must never share a candidate_id/workflow_id, or one
    test's writes (e.g. Turn 3 marking the HR interview "Completed") leak
    into another test's preconditions. Each test builds its own context via
    _make_context() with a unique suffix."""

    def setUp(self):
        self.agent = HRInterviewAgent()

    @staticmethod
    def _make_context(suffix: str, current_state: str) -> WorkflowContext:
        candidate_ctx = CandidateContext(
            candidate_id=f"CAND-AGENT8-{suffix}",
            name="Priya Nair",
            email="priya.nair@example.com",
            resume_url="CV_PriyaNair.pdf",
            screening_score=88.0,
            job_id=f"job-agent8-{suffix}",
            job_title="Backend Engineer",
        )
        return WorkflowContext(
            workflow_id=f"wf-test-agent8-{suffix}",
            candidate=candidate_ctx,
            current_state=current_state,
            metadata={"interactive": True},
        )

    def test_turn1_requests_hr_evaluation(self):
        context = self._make_context("turn1", STATE_HR_INTERVIEW_PENDING)
        response = self.agent.run(context)

        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, EVENT_HR_EVALUATION_REQUESTED)
        self.assertEqual(response.updated_state, STATE_HR_EVALUATION_AWAITED)
        self.assertIn("hr_evaluation_form_url", context.step_data)

    def test_full_turn1_turn2_turn3_cycle(self):
        context = self._make_context("full-cycle", STATE_HR_INTERVIEW_PENDING)

        # Turn 1: HR is handed the evaluation form.
        turn1 = self.agent.run(context)
        self.assertEqual(turn1.updated_state, STATE_HR_EVALUATION_AWAITED)

        # Simulate HR submitting the filled-in form (what
        # MasterAgent.resume_workflow's HREvaluationApproval branch stores).
        context.step_data["hr_evaluation"] = {
            "communication_rating": 5,
            "culture_fit_rating": 5,
            "behaviour_rating": 4,
            "motivation_rating": 4,
            "overall_comments": "Strong communicator, great culture fit.",
            "evaluator": "H. Khan",
        }
        context.current_state = STATE_HR_RANKING_PENDING

        # Turn 2: compute HR score, rank the (single-candidate) cohort.
        turn2 = self.agent.run(context)
        self.assertEqual(turn2.execution_status, "SUCCESS")
        self.assertEqual(turn2.generated_event, EVENT_HR_SCORE_SUBMITTED)
        self.assertEqual(turn2.updated_state, STATE_CANDIDATE_RANKING_AWAITED)
        ranking_preview = context.step_data["hr_ranking_preview"]
        self.assertEqual(len(ranking_preview), 1)
        self.assertEqual(ranking_preview[0]["rank"], 1)
        self.assertEqual(ranking_preview[0]["recommendation"], "Selected")

        # Simulate the hiring manager approving the ranking (what
        # MasterAgent.resume_workflow's HRRankingApproval branch stores).
        context.step_data["hr_final_decision"] = {"approved_by": "hr.manager@example.com"}
        context.current_state = STATE_HR_INTERVIEW_COMPLETED

        # Turn 3: persist the outcome.
        turn3 = self.agent.run(context)
        self.assertEqual(turn3.execution_status, "SUCCESS")
        self.assertEqual(turn3.generated_event, EVENT_CANDIDATE_RANKED)
        self.assertEqual(turn3.updated_state, STATE_HR_INTERVIEW_COMPLETED)
        self.assertEqual(context.step_data["hr_final_rank"], 1)
        self.assertEqual(context.step_data["hr_recommendation"], "Selected")

    def test_turn3_without_turn2_snapshot_fails_gracefully(self):
        # Jumping straight to Turn 3 without an approved Turn 2 ranking must
        # fail deterministically (RANKING_SNAPSHOT_MISSING guard), not crash
        # or silently fabricate a result.
        context = self._make_context("no-snapshot", STATE_HR_INTERVIEW_COMPLETED)
        response = self.agent.run(context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertTrue(any("RANKING_SNAPSHOT_MISSING" in err for err in response.errors))


if __name__ == "__main__":
    unittest.main()
