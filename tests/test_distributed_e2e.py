import unittest
from unittest.mock import patch, MagicMock
import uuid
from fastapi.testclient import TestClient
from services.master_api.app import app as master_app
from schemas.agent_response import AgentResponse
from services.agent6_api.dependencies import initialize_dependencies as init_a6_deps
from services.agent7_api.dependencies import initialize_dependencies as init_a7_deps
from services.agent8_api.dependencies import initialize_dependencies as init_a8_deps

class TestDistributedE2E(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(master_app)
        init_a6_deps()
        init_a7_deps()
        init_a8_deps()
        
        self.cand_id = f"CAND-E2E-{uuid.uuid4().hex[:6]}"
        self.candidate_data = {
            "candidate_id": self.cand_id,
            "name": "David E2E",
            "email": "david.e2e@example.com",
            "resume_url": "CV_DavidE2E.pdf",
            "screening_score": 92.5,
            "job_id": "job-e2e-123",
            "job_title": "Principal Architect"
        }
        self.job_data = {
            "job_id": "job-e2e-123",
            "job_title": "Principal Architect",
            "department": "Engineering"
        }

    def test_readiness_endpoint_all_healthy(self):
        with patch("services.master_api.routes.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.get.return_value = mock_resp
            mock_client_cls.return_value.__enter__.return_value = mock_client

            response = self.client.get("/v1/readiness")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "ready")
            self.assertIn("agent6", data["dependencies"])
            self.assertEqual(data["dependencies"]["agent6"]["status"], "healthy")
            self.assertIsNotNone(data["dependencies"]["agent6"]["latency_ms"])

    def test_readiness_endpoint_degraded(self):
        with patch("services.master_api.routes.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            fail_resp = MagicMock()
            fail_resp.status_code = 503
            ok_resp = MagicMock()
            ok_resp.status_code = 200
            mock_client.get.side_effect = [ok_resp, fail_resp, ok_resp]
            mock_client_cls.return_value.__enter__.return_value = mock_client

            response = self.client.get("/v1/readiness")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "degraded")
            self.assertEqual(data["dependencies"]["agent7"]["status"], "unhealthy")

    @patch("shared.clients.agent_client.httpx.Client")
    def test_full_distributed_pipeline_e2e(self, mock_httpx_cls):
        mock_client = MagicMock()
        
        resp_a6 = MagicMock()
        resp_a6.status_code = 200
        resp_a6.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "InterviewCreated",
            "updated_state": "InterviewScheduled",
            "summary": "Agent 6 scheduled interview.",
            "metadata": {
                "candidate_id": self.cand_id,
                "time_slot": "2026-08-05T10:00:00Z",
                "interviewer_name": "Dr. Sarah Tech",
                "meet_link": "https://meet.google.com/abc-defg-hij"
            }
        }

        resp_a7 = MagicMock()
        resp_a7.status_code = 200
        resp_a7.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "TechnicalScoreSubmitted",
            "updated_state": "TechnicalInterviewCompleted",
            "summary": "Agent 7 technical eval passed.",
            "metadata": {"technical_scores": {"coding_proficiency": 9.0}, "recommendation": "PASS"}
        }

        resp_a8 = MagicMock()
        resp_a8.status_code = 200
        resp_a8.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "HRScoreSubmitted",
            "updated_state": "HRInterviewCompleted",
            "summary": "Agent 8 HR score & ranking passed.",
            "metadata": {"hr_scores": {"culture_fit": 9.5}, "rank_index": 1, "recommendation": "PASS"}
        }

        mock_client.post.side_effect = [resp_a6, resp_a7, resp_a8]
        mock_httpx_cls.return_value.__enter__.return_value = mock_client

        # 1. Start Workflow (triggers Master -> Agent 6 over HTTP)
        start_payload = {
            "candidate_data": self.candidate_data,
            "job_data": self.job_data,
            "metadata": {"interactive": False}
        }
        res_start = self.client.post("/v1/workflow/start", json=start_payload)
        self.assertEqual(res_start.status_code, 201)
        wf_id = res_start.json()["workflow_id"]

        # Verify Master transitioned to InterviewScheduled after A6
        status1 = self.client.get(f"/v1/workflow/{wf_id}").json()
        self.assertEqual(status1["current_state"], "InterviewScheduled")

        # 2. Trigger InterviewStarted (triggers Master -> Agent 7 over HTTP)
        res_evt1 = self.client.post("/v1/workflow/event", json={
            "workflow_id": wf_id,
            "event_name": "InterviewStarted"
        })
        self.assertEqual(res_evt1.status_code, 200)

        # Verify Master transitioned to TechnicalInterviewCompleted after A7
        status2 = self.client.get(f"/v1/workflow/{wf_id}").json()
        self.assertEqual(status2["current_state"], "TechnicalInterviewCompleted")

        # 3. Trigger TriggerHRRound (triggers Master -> Agent 8 over HTTP)
        res_evt2 = self.client.post("/v1/workflow/event", json={
            "workflow_id": wf_id,
            "event_name": "TriggerHRRound"
        })
        self.assertEqual(res_evt2.status_code, 200)

        # Verify Master transitioned to HRInterviewCompleted after A8
        status3 = self.client.get(f"/v1/workflow/{wf_id}").json()
        self.assertEqual(status3["current_state"], "HRInterviewCompleted")

        # Verify 3 HTTP POST invocations were made to worker ports
        self.assertEqual(mock_client.post.call_count, 3)

    @patch("shared.clients.agent_client.httpx.Client")
    def test_e2e_correlation_and_idempotency_propagation(self, mock_httpx_cls):
        mock_client = MagicMock()
        resp_a6 = MagicMock()
        resp_a6.status_code = 200
        resp_a6.json.return_value = {
            "execution_status": "SUCCESS",
            "generated_event": "InterviewCreated",
            "updated_state": "InterviewScheduled",
            "summary": "Scheduled.",
            "metadata": {
                "candidate_id": self.cand_id,
                "time_slot": "2026-08-05T10:00:00Z",
                "interviewer_name": "Dr. Sarah Tech"
            }
        }
        mock_client.post.return_value = resp_a6
        mock_httpx_cls.return_value.__enter__.return_value = mock_client

        headers = {
            "X-Correlation-ID": "e2e-trace-999",
            "X-Idempotency-Key": f"e2e-idemp-{uuid.uuid4().hex[:6]}"
        }
        start_payload = {
            "candidate_data": self.candidate_data,
            "job_data": self.job_data,
            "metadata": {"interactive": False}
        }

        # First request
        res1 = self.client.post("/v1/workflow/start", json=start_payload, headers=headers)
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.headers.get("X-Correlation-ID"), "e2e-trace-999")
        wf_id1 = res1.json()["workflow_id"]

        # Idempotent second request with same key returns identical workflow_id
        res2 = self.client.post("/v1/workflow/start", json=start_payload, headers=headers)
        self.assertEqual(res2.status_code, 201)
        wf_id2 = res2.json()["workflow_id"]
        self.assertEqual(wf_id1, wf_id2)

if __name__ == "__main__":
    unittest.main()
