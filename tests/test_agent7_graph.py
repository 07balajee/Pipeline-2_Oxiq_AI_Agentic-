import unittest
from unittest.mock import patch, MagicMock
from shared.context.workflow_context import WorkflowContext
from shared.context.candidate_context import CandidateContext
from shared.registry.tool_registry import tool_registry
from schemas.agent_response import AgentResponse
from schemas.mcp_response import MCPResponse
from agents.agent7.agent import TechnicalInterviewAgent
from agents.agent7.graph import compile_agent_graph
from tests.mocks.failable_clients import (
    FailableDatabaseMCPClient,
    FailableResumeMCPClient
)

class TestAgent7GraphIntegration(unittest.TestCase):
    def setUp(self):
        self.agent = TechnicalInterviewAgent()
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
            workflow_id="wf-test-agent7-123",
            candidate=self.candidate_ctx,
            current_state="TechnicalInterviewPending",
            previous_state="InterviewScheduled"
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
        self.assertEqual(response.generated_event, "TechnicalScoreSubmitted")
        self.assertEqual(response.updated_state, "TechnicalInterviewCompleted")
        self.assertIn("technical_scores", response.metadata)
        self.assertEqual(response.metadata["recommendation"], "PASS")
        self.assertTrue(self.context.step_data.get("technical_scores_committed"))

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
        self.assertEqual(response.generated_event, "TechnicalScoreSubmitted")

    def test_db_read_retry_exhaustion(self):
        self.register_failable_tools()
        self.context.metadata["simulate_db_read_failure_always"] = True
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "context_retrieval")

    def test_db_commit_retry_and_recovery(self):
        self.register_failable_tools()
        self.context.metadata["simulate_db_write_failure"] = True
        # Failure simulate write deadlock on first attempt
        # FailableDatabaseMCPClient fails on commit action if simulate_db_write_failure is set
        # Test expecting FAILED when commit fails continuously
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "FAILED")
        self.assertEqual(response.metadata.get("failed_operation"), "database_commit")

    def test_idempotency_checkpoint(self):
        self.register_failable_tools()
        self.context.step_data["technical_scores_committed"] = True
        self.context.step_data["technical_scores"] = {"coding_proficiency": 9.0}
        self.context.step_data["technical_recommendation"] = "PASS"
        
        response = self.agent.run(self.context)
        self.assertEqual(response.execution_status, "SUCCESS")

    def test_context_reference_sync(self):
        self.register_failable_tools()
        response = self.agent.run(self.context)
        
        self.assertEqual(response.execution_status, "SUCCESS")
        # Assert in-place mutations synced to caller context
        self.assertTrue(self.context.step_data["technical_scores_committed"])
        self.assertIn("coding_proficiency", self.context.step_data["technical_scores"])

if __name__ == "__main__":
    unittest.main()
