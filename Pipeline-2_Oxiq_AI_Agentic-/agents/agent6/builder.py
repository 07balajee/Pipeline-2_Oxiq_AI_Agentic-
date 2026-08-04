from datetime import datetime
from agents.agent6.models import InterviewObject, Interviewer, InterviewSlot, InterviewMode
from shared.context.workflow_context import WorkflowContext

class InterviewBuilder:
    """
    Builder pattern implementation for compiling the final InterviewObject.
    """
    def __init__(self):
        self._candidate_id = None
        self._candidate_name = None
        self._candidate_email = None
        self._job_id = None
        self._job_title = None
        self._interview_mode = None
        self._interviewer_name = None
        self._interviewer_role = None
        self._time_slot = None
        self._status = "SCHEDULED"
        self._workflow_id = None

    def with_context(self, context: WorkflowContext) -> "InterviewBuilder":
        self._candidate_id = context.candidate.candidate_id
        self._candidate_name = context.candidate.name
        self._candidate_email = context.candidate.email
        self._job_id = context.candidate.job_id
        self._job_title = context.candidate.job_title
        self._workflow_id = context.workflow_id
        return self

    def with_mode(self, mode: InterviewMode) -> "InterviewBuilder":
        self._interview_mode = mode.value
        return self

    def with_interviewer(self, interviewer: Interviewer) -> "InterviewBuilder":
        self._interviewer_name = interviewer.name
        self._interviewer_role = interviewer.role
        return self

    def with_slot(self, slot: InterviewSlot) -> "InterviewBuilder":
        self._time_slot = slot.label
        return self

    def with_status(self, status: str) -> "InterviewBuilder":
        self._status = status
        return self

    def build(self) -> InterviewObject:
        """
        Assembles and returns the InterviewObject.
        """
        # Ensure UTC time format
        now_str = datetime.utcnow().isoformat() + "Z"
        
        return InterviewObject(
            candidate_id=self._candidate_id or "",
            candidate_name=self._candidate_name or "",
            candidate_email=self._candidate_email or "",
            job_id=self._job_id or "",
            job_title=self._job_title or "",
            interview_mode=self._interview_mode or "",
            interviewer_name=self._interviewer_name or "",
            interviewer_role=self._interviewer_role or "",
            time_slot=self._time_slot or "",
            status=self._status,
            created_at=now_str,
            workflow_id=self._workflow_id or ""
        )
