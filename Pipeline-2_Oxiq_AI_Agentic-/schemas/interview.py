from pydantic import BaseModel, Field
from typing import Optional

class InterviewModel(BaseModel):
    """
    Pydantic schema representing interview slot bookings.
    """
    interview_id: str = Field(..., description="Unique UUID of the interview event")
    candidate_id: str = Field(..., description="Target candidate UUID")
    interviewer_id: str = Field(..., description="Assigned interviewer UUID")
    scheduled_time: str = Field(..., description="Confirmed UTC schedule timestamp")
    meeting_link: Optional[str] = Field(None, description="Conferencing access URL")
    status: str = Field("SCHEDULED", description="Active scheduling state")
