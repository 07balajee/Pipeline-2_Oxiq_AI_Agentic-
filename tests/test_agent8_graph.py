import unittest
from unittest.mock import patch, MagicMock
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from shared.registry.tool_registry import tool_registry
from schemas.agent_response import AgentResponse
from schemas.mcp_response import MCPResponse
from agents.agent8.agent import HRInterviewAgent
from agents.agent8.graph import compile_agent_graph
from tests.mocks.failable_clients import (
    FailableDatabaseMCPClient,
    FailableResumeMCPClient
)

class TestAgent8GraphIntegration(unittest.TestCase):
    def setUp(self):
        self.agent = HRInterviewAgent()
        self.candidate_data = {
            "candidate_id": "CAND-001",
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "resume_url": "CV_JaneSmith.pdf",
            "screening_score": 88.5,
            "job_id": "job-abc-123",
            "job_title": "Senior Backend Engineer"
        }
        self.candidate_ctx = CandidateContext(**self.candidate_data)
        self.context = WorkflowContext(
            workflow_id="wf-test-agent8-123",
            candidate=self.candidate_ctx,
            current_state="HRInterviewPending",
            previous_state="TechnicalInterviewCompleted"
        )

    def register_failable_tools(self):
        tool_registry.register("database_mcp", FailableDatabaseMCPClient)
        tool_registry.register("resume_mcp", FailableResumeMCPClient)

    def test_graph_compilation(self):
        graph = compile_agent_graph()
        self.assertIsNotNone(graph)
        self.assertTrue(len(graph.nodes) > 0)

    def test_happy_path_execution(self):
        self.register_failable_tools()
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, "HRScoreSubmitted")
        self.assertEqual(response.updated_state, "HRInterviewCompleted")
        self.assertIn("hr_scores", response.metadata)
        self.assertEqual(response.metadata["rank_index"], 1)
        self.assertEqual(response.metadata["recommendation"], "PASS")
        self.assertTrue(self.context.step_data.get("hr_scores_committed"))

    def test_invalid_state_validation_failure(self):
        self.register_failable_tools()
        self.context.current_state = "CandidateShortlisted"
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "intake_validation")
        self.assertIn("Invalid workflow state", response.errors[0])

    def test_missing_candidate_id_failure(self):
        self.register_failable_tools()
        self.context.candidate.candidate_id = ""
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "intake_validation")

    def test_db_read_retry_and_recovery(self):
        self.register_failable_tools()
        self.context.metadata["simulate_db_read_failure_once"] = True
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.generated_event, "HRScoreSubmitted")

    def test_db_read_retry_exhaustion(self):
        self.register_failable_tools()
        self.context.metadata["simulate_db_read_failure_always"] = True
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "context_retrieval")

    def test_db_commit_retry_exhaustion(self):
        self.register_failable_tools()
        self.context.metadata["simulate_db_write_failure"] = True
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "database_commit")

    def test_idempotency_checkpoint(self):
        self.register_failable_tools()
        self.context.step_data["hr_scores_committed"] = True
        self.context.step_data["hr_scores"] = {"culture_fit": 9.5}
        self.context.step_data["cohort_rank"] = 1
        self.context.step_data["final_recommendation"] = "PASS"
        
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")

    def test_context_reference_sync(self):
        self.register_failable_tools()
        response = self.agent.run(self.context)

        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertTrue(self.context.step_data["hr_scores_committed"])
        self.assertIn("culture_fit", self.context.step_data["hr_scores"])
        self.assertEqual(self.context.step_data["cohort_rank"], 1)

    def test_real_hr_evaluation_computes_deterministic_score(self):
        # When a real hr_evaluation payload is supplied, evaluate_hr_node /
        # calculate_ranking_node compute the actual spec §8 formula
        # (agents/agent8/scoring.py) instead of the hardcoded placeholder.
        # Ratings match the worked example pinned in test_agent8_scoring.py
        # (hr_score composite -> 83).
        self.register_failable_tools()
        self.context.metadata["hr_evaluation"] = {
            "communication_rating": 4, "culture_fit_rating": 5, "behaviour_rating": 4,
            "motivation_rating": 4, "overall_comments": "Strong communicator.",
            "evaluator": "H. Khan",
        }
        response = self.agent.run(self.context)

        self.assertEqual(response.execution_status, "SUCCESS")
        self.assertEqual(response.metadata["hr_score_composite"], 83)
        self.assertEqual(response.metadata["technical_score"], 75.0)  # no technical_scores in step_data -> demo default
        self.assertEqual(response.metadata["final_score"], "78.2")  # 0.6*75 + 0.4*83
        self.assertEqual(response.metadata["rank_index"], 1)
        self.assertEqual(response.metadata["recommendation"], "PASS")
        self.assertIn("confidence_score", response.metadata)

    def test_real_hr_evaluation_invalid_payload_fails_cleanly(self):
        self.register_failable_tools()
        self.context.metadata["hr_evaluation"] = {"communication_rating": 4}  # missing required ratings
        response = self.agent.run(self.context)

        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "hr_evaluation")

if __name__ == "__main__":
    unittest.main()
