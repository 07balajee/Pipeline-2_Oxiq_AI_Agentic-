from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger
import time

class TechnicalInterviewAgent(Agent):
    """
    Dummy implementation of Agent 7: Technical Interview Assessment.
    Provides dummy technical scoring evaluations.
    """
    def run(self, context: WorkflowContext) -> AgentResponse:
        workflow_logger.info("Executing Agent 7 - Technical Assessment Evaluator...", trace_id=context.workflow_id)
        
        # Simulate processing time
        time.sleep(0.5)
        
        candidate_name = context.candidate.name
        scores = {
            "coding_proficiency": 8.5,
            "problem_solving": 8.0,
            "architecture_design": 7.5
        }
        recommendation = "PASS"
        summary_msg = f"Technical scorecard generated for {candidate_name}. Decision: {recommendation}."
        
        # Save evaluation details into step context
        context.step_data["technical_scores"] = scores
        context.step_data["technical_recommendation"] = recommendation
        
        return AgentResponse(
            execution_status="SUCCESS",
            generated_event="TechnicalScoreSubmitted",
            updated_state="TechnicalInterviewCompleted",
            summary=summary_msg,
            metadata={
                "technical_scores": scores,
                "recommendation": recommendation,
                "agent_name": "agent7",
                "execution_duration_ms": 500
            }
        )
