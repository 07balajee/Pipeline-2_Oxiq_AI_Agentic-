from pydantic import BaseModel, EmailStr
from typing import Optional

class CandidateContext(BaseModel):
    """
    Core data structure holding information about the candidate currently being evaluated.
    Matches handoff schemas from Pipeline-1.
    """
    candidate_id: str
    name: str
    email: EmailStr
    resume_url: str
    screening_score: float
    job_id: str
    job_title: str
    
    # Track any state or notes specific to the candidate profile
    profile_notes: Optional[str] = None
