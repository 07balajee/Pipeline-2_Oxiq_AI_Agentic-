from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class CandidateModel(BaseModel):
    """
    Pydantic schema representing candidate profile data.
    """
    candidate_id: str = Field(..., description="Unique UUID of the candidate")
    name: str = Field(..., description="Candidate full name")
    email: EmailStr = Field(..., description="Candidate email address")
    resume_url: str = Field(..., description="Path to candidates CV document")
    screening_score: float = Field(..., description="Initial screening score from Pipeline-1")
    job_id: str = Field(..., description="Job Requisition UUID")
    pipeline_state: str = Field("CandidateShortlisted", description="Current pipeline phase")
    profile_notes: Optional[str] = None
