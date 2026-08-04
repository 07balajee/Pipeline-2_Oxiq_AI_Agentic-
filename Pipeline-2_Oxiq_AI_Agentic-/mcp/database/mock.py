from typing import Any, Dict

def get_mock_candidate_records(candidate_id: str) -> Dict[str, Any]:
    """
    Returns mock db candidate record details.
    """
    return {
        "candidate_id": candidate_id,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "resume_url": "CV_JohnDoe_AIEngineer.pdf",
        "screening_score": 91.0,
        "job_id": "job-abc-123",
        "pipeline_state": "CandidateShortlisted"
    }
