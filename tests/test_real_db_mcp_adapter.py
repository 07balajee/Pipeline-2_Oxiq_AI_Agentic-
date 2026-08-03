import unittest
from unittest.mock import patch, MagicMock
from mcp.database.real_client import RealRecruitmentDBMCPClient
from shared.config.settings import settings

class TestRealRecruitmentDBMCPClient(unittest.TestCase):
    """
    Unit test suite covering the RealRecruitmentDBMCPClient adapter logic,
    action mappings, error classifications, metadata propagation, and prepared transaction handling.
    """

    def setUp(self):
        self.client = RealRecruitmentDBMCPClient(agent_id="agent_6")

    def test_adapter_initialization(self):
        """1. Adapter initializes with correct agent_id and server_path."""
        self.assertEqual(self.client.agent_id, "agent_6")
        self.assertEqual(self.client.transport, settings.mcp_db_transport)

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_read_candidate_success(self, mock_call):
        """2. read_candidate maps to query_resource and formats candidate payload."""
        mock_call.return_value = {
            "ok": True,
            "source": "database",
            "stale": False,
            "rows": [{
                "id": "CAND-101",
                "name": "Aastha Sharma",
                "email": "aastha@example.com",
                "resume_url": "CV_Aastha.pdf",
                "status": "Applied",
                "job_id": "job-abc-123"
            }]
        }

        resp = self.client.execute(action="read_candidate", candidate_id="CAND-101", workflow_id="wf-1")
        
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.payload["candidate_id"], "CAND-101")
        self.assertEqual(resp.payload["name"], "Aastha Sharma")
        self.assertEqual(resp.metadata["source"], "database")
        mock_call.assert_called_once_with("query_resource", table="candidates", filters={"id": "CAND-101"})

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_read_candidate_stale_json_fallback(self, mock_call):
        """3. read_candidate preserves stale=True warning metadata when DB falls back to JSON twin."""
        mock_call.return_value = {
            "ok": True,
            "source": "json_fallback",
            "stale": True,
            "rows": [{
                "id": "CAND-102",
                "name": "Stale Candidate",
                "email": "stale@example.com",
                "resume_url": "CV_Stale.pdf",
                "status": "Applied",
                "job_id": "job-abc-123"
            }]
        }

        resp = self.client.execute(action="read_candidate", candidate_id="CAND-102", workflow_id="wf-2")
        
        self.assertEqual(resp.status, "SUCCESS")
        self.assertTrue(resp.metadata["stale"])
        self.assertIn("legacy JSON twin", resp.metadata["warning"])

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_read_job_success(self, mock_call):
        """4. read_job maps to query_resource and formats job payload."""
        mock_call.return_value = {
            "ok": True,
            "source": "database",
            "stale": False,
            "rows": [{
                "id": "job-123",
                "title": "Senior AI Engineer",
                "department": "Engineering",
                "status": "ACTIVE"
            }]
        }

        resp = self.client.execute(action="read_job", job_id="job-123", workflow_id="wf-3")
        
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.payload["job_id"], "job-123")
        self.assertEqual(resp.payload["job_title"], "Senior AI Engineer")
        mock_call.assert_called_once_with("query_resource", table="jobs", filters={"id": "job-123"})

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_prepare_and_commit_flow(self, mock_call):
        """5. prepare_interview and prepare_update + commit execute write_resource and transition_status."""
        # Prepare interview & state update
        res_prep1 = self.client.execute(
            action="prepare_interview",
            candidate_id="CAND-200",
            interviewer_id="Priya Singh",
            scheduled_time="Monday 10:00 AM",
            workflow_id="wf-4"
        )
        self.assertEqual(res_prep1.status, "SUCCESS")

        res_prep2 = self.client.execute(
            action="prepare_update",
            candidate_id="CAND-200",
            new_state="Interview",
            workflow_id="wf-4"
        )
        self.assertEqual(res_prep2.status, "SUCCESS")

        # Setup mock call responses for commit
        mock_call.side_effect = [
            {"ok": True, "table": "interviews", "inserted": 1},  # write_resource
            {"ok": True, "entity": "candidates", "to": "Interview"}  # transition_status
        ]

        res_commit = self.client.execute(action="commit", workflow_id="wf-4")

        self.assertEqual(res_commit.status, "SUCCESS")
        self.assertEqual(res_commit.payload["executed_steps"], 2)
        self.assertEqual(mock_call.call_count, 2)

    def test_rollback_discards_descriptors(self):
        """6. rollback discards pending memory descriptors."""
        self.client.execute(action="prepare_interview", candidate_id="CAND-300", interviewer_id="Interviewer", scheduled_time="Slot", workflow_id="wf-5")
        self.assertEqual(len(self.client._prepared_descriptors), 1)

        res_rb = self.client.execute(action="rollback", workflow_id="wf-5")
        self.assertEqual(res_rb.status, "SUCCESS")
        self.assertEqual(len(self.client._prepared_descriptors), 0)

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_database_unavailable_error(self, mock_call):
        """7. database_unavailable error returns FAILED response with error classification."""
        mock_call.return_value = {
            "ok": False,
            "code": "database_unavailable",
            "message": "Supabase PostgreSQL unreachable."
        }

        resp = self.client.execute(action="read_candidate", candidate_id="CAND-999", workflow_id="wf-6")
        
        self.assertEqual(resp.status, "FAILED")
        self.assertEqual(resp.metadata["code"], "database_unavailable")
        self.assertIn("database_unavailable", resp.errors[0])

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_capability_denied_error(self, mock_call):
        """8. capability_denied error returns FAILED response with error classification."""
        mock_call.return_value = {
            "ok": False,
            "code": "capability_denied",
            "message": "Agent 'agent_6' has no grant on 'salary'."
        }

        resp = self.client.execute(action="read_candidate", candidate_id="CAND-999", workflow_id="wf-7")
        
        self.assertEqual(resp.status, "FAILED")
        self.assertEqual(resp.metadata["code"], "capability_denied")

    @patch.object(RealRecruitmentDBMCPClient, "_call_mcp_tool")
    def test_validate_capabilities(self, mock_call):
        """9. validate_capabilities calls list_capabilities for specified agent_id."""
        mock_call.return_value = {"ok": True, "agent_id": "agent_6", "resources": []}
        
        res = self.client.validate_capabilities("agent_6")
        self.assertTrue(res["ok"])
        mock_call.assert_called_once_with("list_capabilities", agent_id="agent_6")

if __name__ == "__main__":
    unittest.main()
