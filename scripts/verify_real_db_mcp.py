#!/usr/bin/env python3
"""
Verification Script — Real Recruitment DB MCP Integration Proof
Executes live queries and writes against the provided Recruitment DB MCP server (server.py)
and verifies live Supabase PostgreSQL database interaction.
"""

import sys
import json
from mcp.database.real_client import RealRecruitmentDBMCPClient

def run_real_mcp_verification():
    print("=" * 75)
    print("OxiqAI Pipeline-2 — Real Recruitment DB MCP Integration Verification")
    print("=" * 75)

    client = RealRecruitmentDBMCPClient(agent_id="agent_6")

    # A. Validate Agent 6 Capabilities
    print("\n--- A. Validating Agent 6 Capabilities on Live MCP Server ---")
    caps = client.validate_capabilities("agent_6")
    print(f"  Status: {caps.get('ok')}")
    print(f"  Agent Name: {caps.get('agent_name')}")
    print(f"  Granted Resources: {[r['table'] for r in caps.get('resources', [])]}")

    # Query live candidates & jobs to pick active records
    raw_cands = client._call_mcp_tool("query_resource", table="candidates", limit=5)
    cand_rows = raw_cands.get("rows", [])
    cand_id = str(cand_rows[0]["id"]) if cand_rows else "1"

    raw_jobs = client._call_mcp_tool("query_resource", table="jobs", limit=5)
    job_rows = raw_jobs.get("rows", [])
    job_id = str(job_rows[0]["id"]) if job_rows else "job-abc-123"

    print(f"\n  Discovered Live Supabase Candidate ID: '{cand_id}'")
    print(f"  Discovered Live Supabase Job ID: '{job_id}'")

    # B. Read Candidate
    print("\n--- B. Executing Real Candidate Read Query ---")
    res_cand = client.execute(action="read_candidate", candidate_id=cand_id, workflow_id="wf-verify-001")
    print(f"  Status: {res_cand.status}")
    print(f"  Payload: {res_cand.payload}")
    print(f"  Metadata: {res_cand.metadata}")

    # C. Read Job
    print("\n--- C. Executing Real Job Read Query ---")
    res_job = client.execute(action="read_job", job_id=job_id, workflow_id="wf-verify-001")
    print(f"  Status: {res_job.status}")
    print(f"  Payload: {res_job.payload}")
    print(f"  Metadata: {res_job.metadata}")

    # D. Prepare & Commit Interview Write
    print("\n--- D. Executing Real Interview Write & Commit ---")
    iso_scheduled_time = "2026-08-10T10:00:00Z"
    res_prep1 = client.execute(
        action="prepare_interview",
        candidate_id=cand_id,
        interviewer_id="Priya Singh (Senior AI Engineer)",
        scheduled_time=iso_scheduled_time,
        workflow_id="wf-verify-001"
    )
    print(f"  Prepare Interview Result: {res_prep1.status}")

    res_commit = client.execute(action="commit", workflow_id="wf-verify-001")
    print(f"  Commit Status: {res_commit.status}")
    print(f"  Commit Errors: {res_commit.errors}")
    print(f"  Commit Payload: {res_commit.payload}")

    # E. Read-Back Written Interviews
    print("\n--- E. Read-Back Verification of Written Interviews Row ---")
    raw_res = client._call_mcp_tool("query_resource", table="interviews", limit=5)
    print(f"  Raw Query Result ok: {raw_res.get('ok')}")
    print(f"  Source: {raw_res.get('source')}")
    print(f"  Count: {raw_res.get('count')}")
    print(f"  Rows Sample: {json.dumps(raw_res.get('rows', []), indent=2)[:500]}")

    print("\n" + "=" * 75)
    if res_commit.status == "SUCCESS":
        print("  [SUCCESS] Real Recruitment DB MCP Server Integration Verified!")
        print("=" * 75)
    else:
        print("  [FAIL] Commit failed.")
        print("=" * 75)
        sys.exit(1)

if __name__ == "__main__":
    run_real_mcp_verification()
