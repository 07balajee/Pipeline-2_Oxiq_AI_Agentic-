#!/usr/bin/env python3
"""
OxiqAI HRMS Recruitment Pipeline-2 — 4-Service Live Smoke Test CLI Script
Verifies live network connectivity, health, readiness, and end-to-end execution across:
- Master FastAPI Service (http://127.0.0.1:8000)
- Agent 6 FastAPI Service (http://127.0.0.1:8001)
- Agent 7 FastAPI Service (http://127.0.0.1:8002)
- Agent 8 FastAPI Service (http://127.0.0.1:8003)
"""

import sys
import time
import uuid
import httpx

MASTER_URL = "http://127.0.0.1:8000"
AGENT6_URL = "http://127.0.0.1:8001"
AGENT7_URL = "http://127.0.0.1:8002"
AGENT8_URL = "http://127.0.0.1:8003"

def run_smoke_test():
    print("=" * 70)
    print("OxiqAI Pipeline-2 — Live 4-Process Network Smoke Test")
    print("=" * 70)

    # 1. Health & Readiness Pings
    services = {
        "Master Service (:8000)": f"{MASTER_URL}/v1/health",
        "Agent 6 Service (:8001)": f"{AGENT6_URL}/v1/agents/agent6/health",
        "Agent 7 Service (:8002)": f"{AGENT7_URL}/v1/agents/agent7/health",
        "Agent 8 Service (:8003)": f"{AGENT8_URL}/v1/agents/agent8/health",
    }

    print("\n--- 1. Pinging Process Health Endpoints ---")
    all_healthy = True
    for name, health_url in services.items():
        try:
            start_t = time.time()
            res = httpx.get(health_url, timeout=3.0)
            latency = (time.time() - start_t) * 1000
            if res.status_code == 200:
                print(f"  [OK] {name} -> 200 OK ({latency:.2f}ms)")
            else:
                print(f"  [FAIL] {name} -> HTTP {res.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"  [UNREACHABLE] {name} -> {str(e)}")
            all_healthy = False

    if not all_healthy:
        print("\n[!] WARNING: One or more processes are offline.")
        print("To run the full 4-process smoke test, start all 4 services in separate terminals:")
        print("  Terminal 1: uvicorn services.master_api.app:app --port 8000")
        print("  Terminal 2: uvicorn services.agent6_api.app:app --port 8001")
        print("  Terminal 3: uvicorn services.agent7_api.app:app --port 8002")
        print("  Terminal 4: uvicorn services.agent8_api.app:app --port 8003")
        sys.exit(1)

    print("\n--- 2. Checking Master Dependency Readiness Endpoint ---")
    res_ready = httpx.get(f"{MASTER_URL}/v1/readiness", timeout=5.0)
    print(f"  Readiness Status Code: {res_ready.status_code}")
    print(f"  Readiness Payload: {res_ready.json()}")

    # 2. Trigger E2E Candidate Workflow
    print("\n--- 3. Executing End-to-End Candidate Workflow ---")
    cand_id = f"CAND-SMOKE-{uuid.uuid4().hex[:6]}"
    corr_id = f"smoke-correlation-{uuid.uuid4().hex[:6]}"
    headers = {"X-Correlation-ID": corr_id}

    start_payload = {
        "candidate_data": {
            "candidate_id": cand_id,
            "name": "Live Smoke Test Candidate",
            "email": "smoke@example.com",
            "resume_url": "CV_Smoke.pdf",
            "screening_score": 90.0,
            "job_id": "job-smoke-123",
            "job_title": "Staff Engineer"
        },
        "job_data": {
            "job_id": "job-smoke-123",
            "job_title": "Staff Engineer",
            "department": "Platform Engineering"
        },
        "metadata": {"interactive": False}
    }

    # Step A: Start Workflow (Master -> Agent 6)
    print(f"  A. Starting workflow for candidate '{cand_id}'...")
    res_start = httpx.post(f"{MASTER_URL}/v1/workflow/start", json=start_payload, headers=headers, timeout=10.0)
    if res_start.status_code != 201:
        print(f"  [FAIL] Workflow start failed: {res_start.text}")
        sys.exit(1)
    wf_id = res_start.json()["workflow_id"]
    print(f"     Workflow ID created: {wf_id}")

    res_st1 = httpx.get(f"{MASTER_URL}/v1/workflow/{wf_id}", timeout=5.0).json()
    print(f"     State after Agent 6: {res_st1['current_state']}")

    # Step B: Trigger Technical Interview (Master -> Agent 7)
    print("  B. Triggering 'InterviewStarted' event (Agent 7 technical eval)...")
    res_evt1 = httpx.post(f"{MASTER_URL}/v1/workflow/event", json={
        "workflow_id": wf_id,
        "event_name": "InterviewStarted"
    }, headers=headers, timeout=10.0)
    print(f"     Event HTTP status: {res_evt1.status_code}")

    res_st2 = httpx.get(f"{MASTER_URL}/v1/workflow/{wf_id}", timeout=5.0).json()
    print(f"     State after Agent 7: {res_st2['current_state']}")

    # Step C: Trigger HR Assessment (Master -> Agent 8)
    print("  C. Triggering 'TriggerHRRound' event (Agent 8 HR eval & ranking)...")
    res_evt2 = httpx.post(f"{MASTER_URL}/v1/workflow/event", json={
        "workflow_id": wf_id,
        "event_name": "TriggerHRRound"
    }, headers=headers, timeout=10.0)
    print(f"     Event HTTP status: {res_evt2.status_code}")

    res_st3 = httpx.get(f"{MASTER_URL}/v1/workflow/{wf_id}", timeout=5.0).json()
    print(f"     State after Agent 8: {res_st3['current_state']}")
    print(f"     Step Data: {res_st3.get('step_data')}")

    print("\n" + "=" * 70)
    if res_st3["current_state"] == "HRInterviewCompleted":
        print("  [SUCCESS] 4-Process Live Smoke Test Passed Cleanly!")
        print("=" * 70)
    else:
        print(f"  [FAIL] Unexpected final state: {res_st3['current_state']}")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    run_smoke_test()
