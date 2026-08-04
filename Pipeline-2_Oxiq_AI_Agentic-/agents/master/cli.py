import sys
import json
from shared.config.constants import (
    AGENT_INVITATION,
    AGENT_TECHNICAL,
    AGENT_HR_RANKING
)
from shared.registry.agent_registry import agent_registry
from agents.agent7.agent import TechnicalInterviewAgent
from agents.agent8.agent import HRInterviewAgent
from agents.master.master_agent import MasterAgent
from shared.events.base_event import BaseEvent
from shared.events.event_bus import event_bus
from shared.logger.logger import workflow_logger

# Import tool registry and MCP clients
from shared.registry.tool_registry import tool_registry
from mcp.resume.client import ResumeMCPClient
from mcp.database.client import DatabaseMCPClient
from mcp.calendar.client import CalendarMCPClient
from mcp.meet.client import MeetMCPClient
from mcp.document.client import DocumentMCPClient
from mcp.notification.client import NotificationMCPClient

# 1. Register agents dynamically to the AgentRegistry
agent_registry.register(AGENT_TECHNICAL, TechnicalInterviewAgent)
agent_registry.register(AGENT_HR_RANKING, HRInterviewAgent)

# 2. Register tools dynamically to the ToolRegistry
tool_registry.register("resume_mcp", ResumeMCPClient)
tool_registry.register("database_mcp", DatabaseMCPClient)
tool_registry.register("calendar_mcp", CalendarMCPClient)
tool_registry.register("meet_mcp", MeetMCPClient)
tool_registry.register("document_mcp", DocumentMCPClient)
tool_registry.register("notification_mcp", NotificationMCPClient)

def print_banner():
    print("\n====================================")
    print("   OxiqAI Recruitment Pipeline-2   ")
    print("          Master Agent CLI          ")
    print("====================================")

def get_input(prompt: str) -> str:
    try:
        val = input(prompt).strip()
        return val
    except (KeyboardInterrupt, EOFError):
        print("\nExiting CLI...")
        sys.exit(0)

def main():
    print_banner()
    print("Waiting for Screening Agent...")
    
    candidate_id = get_input("\nEnter Candidate ID: > ")
    print("Loading Candidate Context...")
    
    # Mock data fetched from Database (Pipeline-1 outputs)
    mock_candidate_data = {
        "candidate_id": candidate_id,
        "name": "John Doe",
        "email": "john.doe@example.com",
        "resume_url": "CV_JohnDoe_AIEngineer.pdf",
        "screening_score": 91.0,
        "job_id": "job-abc-123",
        "pipeline_state": "CandidateShortlisted"
    }
    
    mock_job_data = {
        "job_id": "job-abc-123",
        "job_title": "AI Engineer",
        "technical_criteria": ["Python", "Transformers", "Pydantic"],
        "soft_skills_criteria": ["Communication", "Culture Fit", "Leadership"],
        "status": "ACTIVE"
    }

    # Initialize Master Agent
    master = MasterAgent()
    
    # Start the workflow, passing metadata indicating interactive execution
    workflow_id = master.start_workflow(mock_candidate_data, mock_job_data, metadata={"interactive": True})
    
    print("\n-----------------------------")
    print("Candidate Loaded:")
    print(f"Name:  {mock_candidate_data['name']}")
    print(f"Job:   {mock_job_data['job_title']}")
    print(f"Trace: {workflow_id}")
    print("-----------------------------")

    context = master.active_contexts[workflow_id]
    
    # Step 1: Trigger automated scheduling once at the start
    choice = get_input("\nTrigger automated scheduling? [Y/N] > ").lower().strip()
    if choice != 'y':
        print("\nWorkflow paused/cancelled at user request.")
        sys.exit(0)
        
    event_bus.publish(
        BaseEvent(
            name="CandidateShortlisted",
            candidate_id=mock_candidate_data["candidate_id"]
        )
    )
    
    # Scheduling interactive loop with retry on rejection
    while True:
        # Check if the orchestrator paused for approval
        if "paused_on_approval" in context.metadata:
            approval_type = context.metadata["paused_on_approval"]
            print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f" [Approval Engine] - Human Verification Required")
            print(f"  Type:        {approval_type}")
            print(f"  Candidate:   {context.candidate.name}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            app_choice = get_input("Approve recommended schedule? (Y/N) > ").lower().strip()
            if app_choice == 'y':
                event_bus.publish(
                    BaseEvent(
                        name="WorkflowResumed",
                        candidate_id=mock_candidate_data["candidate_id"]
                    )
                )
                print(f"\n[System Status] Current State: {context.current_state}")
                print(f"[System Status] Dynamic context details loaded: {json.dumps(context.step_data, indent=2)}")
                timeline = master.active_timelines[workflow_id]
                timeline.print_timeline()
                break  # Approved! Proceed out of the scheduling loop
            else:
                print("\nTransition rejected. Recording rejection and re-scheduling...")
                # Record rejected recommendation
                rejected = {
                    "interviewer_id": context.step_data.get("interviewer_id"),
                    "time_slot": context.step_data.get("scheduled_time")
                }
                context.metadata.setdefault("rejected_recommendations", []).append(rejected)
                
                # Clear previous schedule context so next attempt doesn't trigger duplicate validation
                context.step_data.pop("scheduled_time", None)
                context.step_data.pop("meeting_link", None)
                context.step_data.pop("interviewer_id", None)
                context.step_data.pop("interview_mode", None)
                context.step_data.pop("packet_id", None)
                
                # Pop approval state metadata
                context.metadata.pop("paused_on_approval", None)
                context.metadata.pop("pending_next_state", None)
                
                # Remain inside InterviewScheduling workflow, re-run recommendation
                event_bus.publish(
                    BaseEvent(
                        name="RetryRequested",
                        candidate_id=mock_candidate_data["candidate_id"],
                        payload={"failed_agent": "agent6", "attempt": 0}
                    )
                )
        elif context.current_state == "WorkflowPaused" and context.metadata.get("proposed_fallback") == "Offline Interview":
            print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f" Scheduling requires attention.")
            print(f"\n Candidate: {context.candidate.name}")
            print(f" Stage:     Interview Scheduling")
            print(f" Failure:   {context.metadata.get('failure_reason', 'Google Meet generation')}")
            print(f" Retries:   3/3")
            print(f" Proposed fallback: Offline Interview")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            app_choice = get_input("Approve offline fallback? (Y/N) > ").lower().strip()
            if app_choice == 'y':
                print("\nApplying fallback: Switching to Offline Interview...")
                # Update context state to Offline mode
                context.step_data["interview_mode"] = "Offline"
                context.metadata["interview_mode"] = "Offline"
                context.step_data["meeting_link"] = None
                
                # Pop the fallback proposal metadata
                context.metadata.pop("proposed_fallback", None)
                context.metadata.pop("failure_reason", None)
                context.metadata.pop("fallback_applied", None)
                
                # Reset state to active scheduling to allow retry
                context.current_state = "InterviewScheduling"
                context.previous_state = "WorkflowPaused"
                state_manager.update_state(workflow_id, "InterviewScheduling", current_step="Process_FallbackApproved")
                
                # Clear retry count
                master.retry_engine.reset_retry_count(context)
                
                # Re-run Agent 6 in Offline mode
                event_bus.publish(
                    BaseEvent(
                        name="RetryRequested",
                        candidate_id=mock_candidate_data["candidate_id"],
                        payload={"failed_agent": "agent6", "attempt": 0, "fallback_applied": True}
                    )
                )
            else:
                print("\nOffline fallback rejected. Workflow remains paused.")
                sys.exit(0)
        else:
            # If not paused, exit scheduling loop (e.g., error occurred or non-interactive)
            break

    # Define remaining interactive steps
    steps = [
        {
            "prompt": "Start Technical Interview Assessment? [Y/N] > ",
            "action": lambda: event_bus.publish(
                BaseEvent(
                    name="InterviewStarted",
                    candidate_id=mock_candidate_data["candidate_id"]
                )
            )
        },
        {
            "prompt": "Compile and review scorecards? [Y/N] > ",
            "action": lambda: event_bus.publish(
                BaseEvent(
                    name="TechnicalScoreSubmitted",
                    candidate_id=mock_candidate_data["candidate_id"]
                )
            )
        },
        {
            "prompt": "Schedule and trigger HR round evaluation? [Y/N] > ",
            "action": lambda: event_bus.publish(
                BaseEvent(
                    name="TriggerHRRound",
                    candidate_id=mock_candidate_data["candidate_id"]
                )
            )
        },
        # Agent 8 now runs its own three turns (form -> compute & rank -> persist).
        # "Execute pool re-ranking algorithms?" / "Submit candidate rankings to database?"
        # are no longer separate manual triggers - Turn 2 and Turn 3 dispatch
        # automatically as each HITL gate below (HREvaluationApproval, then
        # HRRankingApproval) is approved.
        {
            "prompt": "Approve final candidate selection and request offer? [Y/N] > ",
            "action": lambda: event_bus.publish(
                BaseEvent(
                    name="CandidateSelected",
                    candidate_id=mock_candidate_data["candidate_id"]
                )
            )
        }
    ]

    for step in steps:
        choice = get_input(f"\n{step['prompt']}").lower().strip()
        if choice == 'y':
            step["action"]()
            
            # If the orchestrator intercepted the transition, trigger the pause/resume loop.
            # A single step can now cascade through more than one gate (e.g.
            # "Schedule and trigger HR round evaluation" runs Agent 8 Turn 1,
            # which pauses at HREvaluationApproval; approving that resumes
            # straight into Turn 2, which pauses again at HRRankingApproval) -
            # so this keeps handling gates until none remain, rather than a
            # single check.
            # Re-fetch context on every iteration: LangGraph's checkpointer
            # reconstructs a new WorkflowContext instance on each pause/resume
            # cycle (agents/master/master_agent.py always writes the latest
            # instance back to master.active_contexts[workflow_id]), so a
            # reference captured before this loop would go stale after the
            # first resume.
            rejected = False
            context = master.active_contexts[workflow_id]
            while "paused_on_approval" in context.metadata:
                approval_type = context.metadata["paused_on_approval"]
                print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f" [Approval Engine] - Human Verification Required")
                print(f"  Type:        {approval_type}")
                print(f"  Candidate:   {context.candidate.name}")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                if approval_type == "HREvaluationApproval":
                    print(" HR: submit the evaluation form (ratings on a 1-5 scale).")
                    hr_payload = {
                        "communication_rating": int(get_input("  Communication rating (1-5) > ")),
                        "culture_fit_rating": int(get_input("  Culture fit rating (1-5) > ")),
                        "behaviour_rating": int(get_input("  Behaviour rating (1-5) > ")),
                        "motivation_rating": int(get_input("  Motivation rating (1-5) > ")),
                        "overall_comments": get_input("  Overall comments > "),
                        "evaluator": get_input("  Evaluator name > "),
                    }
                    if master.resume_workflow(workflow_id, approval_type, "APPROVE", hr_payload):
                        print("\nHR evaluation submitted. Computing HR score and ranking...")
                    else:
                        print("\nSubmission rejected. Workflow paused.")
                        rejected = True
                        break
                elif approval_type == "HRRankingApproval":
                    print(" Hiring manager: review the ranking preview and approve.")
                    print(json.dumps(context.step_data.get("hr_ranking_preview", []), indent=2))
                    ranking_payload = {"approved_by": get_input("  Approving manager email > ")}
                    if master.resume_workflow(workflow_id, approval_type, "APPROVE", ranking_payload):
                        print("\nRanking approved. Persisting HR outcome...")
                    else:
                        print("\nApproval rejected. Workflow paused.")
                        rejected = True
                        break
                else:
                    app_choice = get_input("Approve transition and resume workflow? (Y/N) > ").lower().strip()
                    if app_choice == 'y':
                        event_bus.publish(
                            BaseEvent(
                                name="WorkflowResumed",
                                candidate_id=mock_candidate_data["candidate_id"]
                            )
                        )
                    else:
                        print("\nTransition rejected. Workflow paused.")
                        rejected = True
                        break

                # Refresh before the loop re-checks its condition - a resume
                # may have cascaded straight into another approval gate.
                context = master.active_contexts[workflow_id]

            if rejected:
                break

            print(f"\n[System Status] Current State: {context.current_state}")
            print(f"[System Status] Dynamic context details loaded: {json.dumps(context.step_data, indent=2)}")

            # Print timestamped workflow timeline
            timeline = master.active_timelines[workflow_id]
            timeline.print_timeline()
        else:
            print("\nWorkflow paused/cancelled at user request.")
            break

    # Dump trace log metrics on completion
    trace = master.active_traces[workflow_id]
    print("\n====================================")
    print("        WORKFLOW TELEMETRY TRACE    ")
    print("====================================")
    print(json.dumps(trace.model_dump(), indent=2))
    print("====================================")

if __name__ == "__main__":
    main()
