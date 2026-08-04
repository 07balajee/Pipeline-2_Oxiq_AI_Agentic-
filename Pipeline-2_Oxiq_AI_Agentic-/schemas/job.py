from pydantic import BaseModel, Field
from typing import List

class JobModel(BaseModel):
    """
    Pydantic schema representing job details and requirements.
    """
    job_id: str = Field(..., description="Unique UUID of the job requisition")
    job_title: str = Field(..., description="Job Title")
    technical_criteria: List[str] = Field(default_factory=list, description="List of technical criteria required")
    soft_skills_criteria: List[str] = Field(default_factory=list, description="List of HR evaluation parameters")
    status: str = Field("ACTIVE", description="Current requisition status")
