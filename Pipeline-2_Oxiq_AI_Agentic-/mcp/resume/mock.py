from typing import Any, Dict

def get_mock_resume_data(workflow_id: str) -> Dict[str, Any]:
    """
    Returns mock data for candidates resume screening.
    """
    return {
        "resume_url": "CV_JohnDoe_AIEngineer.pdf",
        "screening_summary": "Candidate has 5+ years experience in Python, NLP, and LLM architectures. Technical score matches target profiles.",
        "skills_found": ["Python", "Transformers", "Pydantic", "FastAPI", "Docker"],
        "education": "M.S. in Computer Science"
    }
