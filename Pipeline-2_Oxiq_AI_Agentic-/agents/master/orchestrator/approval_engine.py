from shared.events.base_event import BaseEvent
from shared.events.event_bus import event_bus
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class ApprovalEngine:
    """
    Manages human verification checkpoints and pauses.
    Interceptors pause execution and await user validation before resuming.
    """

    def should_pause_for_approval(self, current_state: str, next_state: str, context: WorkflowContext) -> bool:
        """
        Determines if the transition between current_state and next_state requires human sign-off.
        """
        is_interactive = context.metadata.get("interactive", False)
        if not is_interactive:
            return False

        # Transition bounds requiring human verification
        # 1. SlotApproval: when transitioning to the scheduled wait state
        if current_state == "InterviewScheduling" and next_state == "InterviewScheduled":
            return True
        # 2. SelectionApproval: when selecting the candidate
        if current_state == "CandidateSelected" and next_state == "OfferPipelineTriggered":
            return True
        # 3. HREvaluationApproval: Agent 8 Turn 1 handed HR a form, awaiting submitted ratings
        if current_state == "HRInterviewPending" and next_state == "HREvaluationAwaited":
            return True
        # 4. HRRankingApproval: Agent 8 Turn 2 produced a ranking, awaiting hiring manager sign-off
        if current_state == "HRRankingPending" and next_state == "CandidateRankingAwaited":
            return True
        return False

    def process_approval(self, current_state: str, next_state: str, context: WorkflowContext) -> str:
        """
        Pauses the workflow and emits the WorkflowPaused lifecycle trigger.
        """
        approval_type = "ManagerApproval"
        if current_state == "InterviewScheduling" and next_state == "InterviewScheduled":
            approval_type = "SlotApproval"
        elif current_state == "CandidateSelected" and next_state == "OfferPipelineTriggered":
            approval_type = "SelectionApproval"
        elif current_state == "HRInterviewPending" and next_state == "HREvaluationAwaited":
            approval_type = "HREvaluationApproval"
        elif current_state == "HRRankingPending" and next_state == "CandidateRankingAwaited":
            approval_type = "HRRankingApproval"

        context.metadata["paused_on_approval"] = approval_type
        context.metadata["pending_next_state"] = next_state
        
        workflow_logger.info(
            f"Human approval required: '{approval_type}'. Pausing workflow execution...",
            trace_id=context.workflow_id
        )
        
        # Publish WorkflowPaused onto the shared event bus
        event_bus.publish(BaseEvent(name="WorkflowPaused", candidate_id=context.candidate.candidate_id))
        
        return approval_type
