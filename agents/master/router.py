from typing import Optional, Tuple
from shared.config.constants import (
    STATE_CANDIDATE_SHORTLISTED,
    STATE_INTERVIEW_SCHEDULING,
    STATE_INTERVIEW_SCHEDULED,
    STATE_TECHNICAL_INTERVIEW_PENDING,
    STATE_TECHNICAL_INTERVIEW_COMPLETED,
    STATE_HR_INTERVIEW_PENDING,
    STATE_HR_INTERVIEW_COMPLETED,
    STATE_CANDIDATE_SELECTED,
    STATE_CANDIDATE_REJECTED,
    STATE_OFFER_PIPELINE_TRIGGERED,
    EVENT_CANDIDATE_SHORTLISTED,
    EVENT_INTERVIEW_CREATED,
    EVENT_INTERVIEW_STARTED,
    EVENT_TECHNICAL_SCORE_SUBMITTED,
    EVENT_TRIGGER_HR_ROUND,
    EVENT_HR_SCORE_SUBMITTED,
    EVENT_CANDIDATE_RANKED,
    EVENT_CANDIDATE_SELECTED,
    EVENT_CANDIDATE_REJECTED,
    EVENT_OFFER_REQUESTED,
    EVENT_RETRY_REQUESTED,
    AGENT_INVITATION,
    AGENT_TECHNICAL,
    AGENT_HR_RANKING
)
from shared.logger.logger import workflow_logger

class Router:
    """
    Decoupled state router evaluating state machine transitions.
    Determines next targets and matches them with registered agent keys.
    """

    def route(self, current_state: str, event_name: str) -> Tuple[str, Optional[str]]:
        """
        Processes transition paths.
        
        Args:
            current_state (str): Current active candidate pipeline phase.
            event_name (str): The incoming event name triggering change.
            
        Returns:
            Tuple[str, Optional[str]]: A tuple of (next_state, target_agent_key).
        """
        workflow_logger.info(
            f"Routing evaluation | Current State: {current_state} | Event: {event_name}"
        )

        # 1. Pipeline Start -> Invites Scheduling (Agent 6)
        if current_state == STATE_CANDIDATE_SHORTLISTED and event_name == EVENT_CANDIDATE_SHORTLISTED:
            return STATE_INTERVIEW_SCHEDULING, AGENT_INVITATION

        # 1b. Scheduling Retry -> Re-invoke Agent 6
        elif current_state == STATE_INTERVIEW_SCHEDULING and event_name == EVENT_RETRY_REQUESTED:
            return STATE_INTERVIEW_SCHEDULING, AGENT_INVITATION

        # 2. Scheduling complete -> Move to Scheduled Wait State
        elif current_state == STATE_INTERVIEW_SCHEDULING and event_name == EVENT_INTERVIEW_CREATED:
            return STATE_INTERVIEW_SCHEDULED, None

        # 3. Scheduled state -> Technical interview starts
        # For the CLI skeleton, when the user triggers the interview, we transition to Tech Pending
        elif current_state == STATE_INTERVIEW_SCHEDULED and event_name == EVENT_INTERVIEW_STARTED:
            return STATE_TECHNICAL_INTERVIEW_PENDING, AGENT_TECHNICAL

        # 4. Tech Evaluation completed
        elif current_state == STATE_TECHNICAL_INTERVIEW_PENDING and event_name == EVENT_TECHNICAL_SCORE_SUBMITTED:
            return STATE_TECHNICAL_INTERVIEW_COMPLETED, None

        # 5. Move to HR interview pending
        elif current_state == STATE_TECHNICAL_INTERVIEW_COMPLETED and event_name == EVENT_TRIGGER_HR_ROUND:
            return STATE_HR_INTERVIEW_PENDING, AGENT_HR_RANKING

        # 6. HR evaluation finished -> re-ranking
        elif current_state == STATE_HR_INTERVIEW_PENDING and event_name == EVENT_HR_SCORE_SUBMITTED:
            return STATE_HR_INTERVIEW_COMPLETED, None

        # 7. Candidate ranked -> wait for hiring manager selection
        elif current_state == STATE_HR_INTERVIEW_COMPLETED and event_name == EVENT_CANDIDATE_RANKED:
            return STATE_CANDIDATE_SELECTED, None

        # 8. Selection approved -> trigger Pipeline-3
        elif current_state == STATE_CANDIDATE_SELECTED and event_name == EVENT_CANDIDATE_SELECTED:
            return STATE_OFFER_PIPELINE_TRIGGERED, None

        # 9. Global Rejection transition
        elif event_name == EVENT_CANDIDATE_REJECTED:
            return STATE_CANDIDATE_REJECTED, None

        # 10. Fallback: No matching transitions
        workflow_logger.logger.warning(
            f"No matching transition found for state {current_state} and event {event_name}."
        )
        return current_state, None
