from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger
import time

class HRInterviewAgent(Agent):
    """
    Dummy implementation of Agent 8: HR Interview & Candidate Re-ranking.
    Provides dummy soft skill evaluations and updates cohort rankings.
    """
    def run(self, context: WorkflowContext) -> AgentResponse:
        workflow_logger.info("Executing Agent 8 - HR Evaluator & Pool Re-ranking...", trace_id=context.workflow_id)
        
        # Simulate processing time
        time.sleep(0.5)
        
        candidate_name = context.candidate.name
        hr_scores = {
            "culture_fit": 9.0,
            "communication": 8.5,
            "leadership_potential": 8.0
        }
        rank_index = 1  # Candidate ranks #1 in pool
        recommendation = "PASS"
        summary_msg = f"HR assessment completed. Candidate {candidate_name} ranked #{rank_index} in cohort."
        
        # Save evaluation details into step context
        context.step_data["hr_scores"] = hr_scores
        context.step_data["cohort_rank"] = rank_index
        context.step_data["final_recommendation"] = recommendation
        
        return AgentResponse(
            execution_status="SUCCESS",
            generated_event="HRScoreSubmitted",
            updated_state="HRInterviewCompleted",
            summary=summary_msg,
            metadata={
                "hr_scores": hr_scores,
                "rank_index": rank_index,
                "recommendation": recommendation,
                "agent_name": "agent8",
                "execution_duration_ms": 500
            }
        )
