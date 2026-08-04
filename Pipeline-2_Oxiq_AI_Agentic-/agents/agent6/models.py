from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List

class InterviewMode(str, Enum):
    """
    Standard modes supported for interviews.
    """
    ONLINE = "Online"
    OFFLINE = "Offline"

class Interviewer(BaseModel):
    """
    Local domain model representing interviewer details.
    """
    interviewer_id: str = Field(..., description="Unique UUID/ID of the interviewer")
    name: str = Field(..., description="Interviewer full name")
    role: str = Field(..., description="Interviewer title/role")
    department: str = Field(..., description="Interviewer department")
    skills: List[str] = Field(default_factory=list, description="Interviewer technical skills")
    supported_interview_types: List[str] = Field(default_factory=list, description="Supported interview types, e.g. Technical, HR")
    supported_modes: List[str] = Field(default_factory=list, description="Supported modes, e.g. Online, Offline")
    is_active: bool = Field(True, description="Interviewer active status")


class InterviewSlot(BaseModel):
    """
    Local domain model representing a calendar availability slot.
    """
    slot_id: str = Field(..., description="Unique ID of the timeslot")
    label: str = Field(..., description="Human readable timestamp label")
    is_available: bool = Field(True, description="Availability flag")

class InterviewSummary(BaseModel):
    """
    Local domain model representing interview booking summary.
    """
    summary_text: str = Field(..., description="Formatted description of the booking details")
    created_at: str = Field(..., description="Timestamp when summary was generated")

class InterviewObject(BaseModel):
    """
    Compiled domain model combining candidate, job, mode, interviewer,
    and timeslot variables into a unified scheduled object.
    """
    candidate_id: str
    candidate_name: str
    candidate_email: str
    job_id: str
    job_title: str
    interview_mode: str
    interviewer_name: str
    interviewer_role: str
    time_slot: str
    status: str
    created_at: str
    workflow_id: str
