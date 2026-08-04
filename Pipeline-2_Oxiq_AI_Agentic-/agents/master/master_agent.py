import time
import uuid
from typing import Dict, Any
from schemas.workflow_state import WorkflowStateModel
from shared.config.constants import (
    STATE_CANDIDATE_SHORTLISTED,
    EVENT_CANDIDATE_SHORTLISTED,
    STATE_WORKFLOW_PAUSED,
    STATE_WORKFLOW_FAILED,
    STATE_OFFER_PIPELINE_TRIGGERED,
    STATE_CANDIDATE_REJECTED,
    EVENT_HR_EVALUATION_SUBMITTED,
    EVENT_CANDIDATE_RANKING_APPROVED
)
from shared.context.candidate_context import CandidateContext
from shared.context.workflow_context import WorkflowContext
from shared.context.workflow_trace import WorkflowTrace
from shared.events.base_event import BaseEvent
from shared.events.event_bus import event_bus
from shared.events.event_types import EventTypes
from shared.logger.logger import workflow_logger, audit_logger, error_logger
from agents.master.state_manager import state_manager
from agents.master.router import Router
from agents.master.dispatcher import Dispatcher
from agents.master.validator import Validator

# Import modular orchestration components
from agents.master.orchestrator import (
    Timeline, EventStore, ApprovalEngine, RetryEngine, FallbackEngine, ResponseValidator, ContextManager, WorkflowEngine
)
from agents.master.graph import compile_workflow_graph

class MasterAgent:
    """
    The orchestrator facade of Pipeline-2. Re-engineered to delegate candidate workflow routing,
    worker agent dispatches, retry schedules, and validation sequences to a Compiled LangGraph.
    """
    def __init__(self):
        self.router = Router()
        self.dispatcher = Dispatcher()
        self.validator = Validator()
        
        # Instantiate orchestration components
        self.workflow_engine = WorkflowEngine()
        self.context_manager = ContextManager()
        self.response_validator = ResponseValidator()
        self.retry_engine = RetryEngine()
        self.fallback_engine = FallbackEngine()
        self.approval_engine = ApprovalEngine()
        self.event_store = EventStore()
        
        # In-memory storage for contexts, traces, and timeline trackers
        self.active_contexts: Dict[str, WorkflowContext] = {}
        self.active_traces: Dict[str, WorkflowTrace] = {}
        self.active_timelines: Dict[str, Timeline] = {}
        
        # Compile LangGraph app
        self.graph = compile_workflow_graph()
        
        self._subscribe_events()

    def _subscribe_events(self):
        """
        Subscribes the orchestration handler to all valid workflow event types.
        """
        for event_type in EventTypes:
            event_bus.subscribe(event_type.value, self.handle_event)

    def _build_graph_config(self, workflow_id: str) -> dict:
        """
        Constructs the dependency injection dictionary for LangGraph nodes.
        """
        return {
            "configurable": {
                "thread_id": workflow_id,
                "state_manager": state_manager,
                "workflow_engine": self.workflow_engine,
                "context_manager": self.context_manager,
                "dispatcher": self.dispatcher,
                "response_validator": self.response_validator,
                "retry_engine": self.retry_engine,
                "fallback_engine": self.fallback_engine,
                "approval_engine": self.approval_engine,
                "event_store": self.event_store,
                "timeline": self.active_timelines[workflow_id],
                "trace": self.active_traces[workflow_id]
            }
        }

    def start_workflow(self, candidate_data: dict, job_data: dict, metadata: dict = None) -> str:
        """
        Intakes candidate records and starts the interview management pipeline.
        
        Returns:
            str: The unique workflow ID/trace ID generated for this run.
        """
        # 1. Schema Validation
        candidate = self.validator.validate_candidate(candidate_data)
        job = self.validator.validate_job(job_data)
        
        workflow_id = str(uuid.uuid4())
        workflow_logger.info(f"Intaking candidate: {candidate.name}. Initializing workflow: {workflow_id}", trace_id=workflow_id)

        # 2. Context Initialization
        candidate_ctx = CandidateContext(
            candidate_id=candidate.candidate_id,
            name=candidate.name,
            email=candidate.email,
            resume_url=candidate.resume_url,
            screening_score=candidate.screening_score,
            job_id=job.job_id,
            job_title=job.job_title
        )
        
        wf_context = WorkflowContext(
            workflow_id=workflow_id,
            candidate=candidate_ctx,
            current_state=STATE_CANDIDATE_SHORTLISTED,
            metadata=metadata or {}
        )
        
        self.active_contexts[workflow_id] = wf_context
        
        # Create trace log
        wf_trace = WorkflowTrace(trace_id=workflow_id, candidate_id=candidate.candidate_id)
        self.active_traces[workflow_id] = wf_trace
        
        # Initialize Timeline and log start milestones
        timeline = Timeline()
        self.active_timelines[workflow_id] = timeline
        timeline.add_milestone("Candidate Shortlist Intake")
        timeline.add_milestone("Candidate Context Loaded & Screened")
        
        # Initialize database state manager
        initial_state = WorkflowStateModel(
            workflow_id=workflow_id,
            candidate_id=candidate.candidate_id,
            current_state=STATE_CANDIDATE_SHORTLISTED,
            current_step="IntakeInitialization"
        )
        state_manager.save_state(initial_state)
        
        # 3. Emit Initial Event to Event Bus
        init_event = BaseEvent(
            name=EVENT_CANDIDATE_SHORTLISTED,
            candidate_id=candidate.candidate_id,
            payload=candidate_data
        )
        wf_trace.add_step(
            actor="Pipeline-1",
            action="CandidateShortlistIntake",
            status="SUCCESS",
            duration_ms=10.0,
            output_payload=init_event.payload
        )
        
        self.event_store.log_event(init_event, "Created")
        event_bus.publish(init_event)
        
        return workflow_id

    def handle_event(self, event: BaseEvent):
        """
        Orchestrates state transitions and invokes worker agents in response to events.
        """
        # Find active context by checking our in-memory cache
        workflow_id = next((wid for wid, ctx in self.active_contexts.items() if ctx.candidate.candidate_id == event.candidate_id), None)
        
        if not workflow_id:
            return

        context = self.active_contexts[workflow_id]
        trace = self.active_traces[workflow_id]
        timeline = self.active_timelines[workflow_id]
        state = state_manager.get_state(workflow_id)
        
        if not state:
            error_logger.error(f"State not found for workflow {workflow_id}", trace_id=workflow_id)
            return

        # Log event entry
        self.event_store.log_event(event, "Queued")
        self.event_store.log_event(event, "Executing")
        timeline.add_milestone(f"Event Received: {event.name}")

        config = self._build_graph_config(workflow_id)

        # Check approval resume case
        if event.name == "WorkflowResumed":
            self.event_store.log_event(event, "Completed")
            pending_next_state = context.metadata.pop("pending_next_state", None)
            paused_approval = context.metadata.pop("paused_on_approval", None)
            
            if pending_next_state:
                context.metadata["pending_next_state"] = pending_next_state
                context.metadata["paused_on_approval"] = paused_approval
                
                # Checkpoint resume path
                self.graph.update_state(config, {
                    "workflow_context": context,
                    "incoming_event": event.name,
                    "event_payload": event.payload
                })
                
                final_state = self.graph.invoke(None, config)
                if final_state and "workflow_context" in final_state:
                    self.active_contexts[workflow_id] = final_state["workflow_context"]
                
                # Trigger completion handoff on resume
                if pending_next_state == STATE_OFFER_PIPELINE_TRIGGERED:
                    self.complete_workflow(workflow_id, trace, timeline)
                return

        # Check if the workflow is currently suspended in paused or failed state
        if state.current_state in [STATE_WORKFLOW_PAUSED, STATE_WORKFLOW_FAILED] and event.name != "WorkflowResumed" and event.name != "RetryRequested":
            workflow_logger.info(
                f"Workflow {workflow_id} is currently suspended in '{state.current_state}'. Ignoring event {event.name}.",
                trace_id=workflow_id
            )
            return

        # Check if the graph is currently suspended/interrupted on human_approval_node thread
        thread_state = self.graph.get_state(config)

        if thread_state and thread_state.next:
            # Update state variables on suspended thread and resume
            self.graph.update_state(config, {
                "workflow_context": context,
                "incoming_event": event.name,
                "event_payload": event.payload,
                "target_agent": None,
                "next_state": None,
                "agent_response": None,
                "transport_error": None
            })
            final_state = self.graph.invoke(None, config)
        else:
            # Start fresh invocation
            final_state = self.graph.invoke({
                "workflow_context": context,
                "incoming_event": event.name,
                "event_payload": event.payload,
                "target_agent": None,
                "next_state": None,
                "agent_response": None,
                "transport_error": None,
                "graph_status": "RUNNING"
            }, config)

        # Sync final graph context state back to facade memory
        if final_state and "workflow_context" in final_state:
            self.active_contexts[workflow_id] = final_state["workflow_context"]

        # Handle next event cascades
        resp = final_state.get("agent_response")
        if resp and resp.execution_status == "SUCCESS":
            self.event_store.log_event(event, "Completed")
            if resp.generated_event:
                next_event = BaseEvent(
                    name=resp.generated_event,
                    candidate_id=context.candidate.candidate_id,
                    payload=resp.metadata
                )
                self.event_store.log_event(next_event, "Created")
                event_bus.publish(next_event)
        elif final_state.get("graph_status") == "WORKFLOW_COMPLETED":
            self.event_store.log_event(event, "Completed")
            next_state = final_state.get("next_state")
            if next_state == STATE_OFFER_PIPELINE_TRIGGERED:
                self.complete_workflow(workflow_id, trace, timeline)

    def complete_workflow(self, workflow_id: str, trace: WorkflowTrace, timeline: Timeline):
        workflow_logger.info(f"Workflow {workflow_id} reached handoff state. Handing off details to Pipeline-3...", trace_id=workflow_id)
        trace.final_status = "COMPLETED"
        trace.end_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        audit_logger.log_tool_call("Pipeline3_Handoff", "SUCCESS", 15.0, trace_id=workflow_id)
        timeline.add_milestone("Workflow completed and handed off to Pipeline-3")

    def get_workflow_status(self, workflow_id: str) -> dict:
        """
        Public facade method to aggregate candidate workflow status details safely.
        """
        context = self.active_contexts.get(workflow_id)
        if not context:
            raise KeyError(f"Workflow '{workflow_id}' not found.")
            
        state_model = state_manager.get_state(workflow_id)
        timeline = self.active_timelines.get(workflow_id)
        
        # Get graph checkpoints next execution indicators
        config = self._build_graph_config(workflow_id)
        thread_state = self.graph.get_state(config)
        graph_status = "RUNNING"
        approval_type = None
        approval_status = None
        
        if thread_state:
            if thread_state.next:
                graph_status = "PAUSED"
                approval_status = "PENDING"
                approval_type = context.metadata.get("paused_on_approval") or context.metadata.get("proposed_fallback")
            else:
                graph_status = "COMPLETED"
                
        # Override with DB state if paused/failed
        if state_model:
            if state_model.current_state == STATE_WORKFLOW_PAUSED:
                graph_status = "PAUSED"
            elif state_model.current_state == STATE_WORKFLOW_FAILED:
                graph_status = "FAILED"
                
        timeline_entries = timeline.get_entries() if timeline else []
        last_error = context.metadata.get("last_execution_error")
        
        return {
            "workflow_id": workflow_id,
            "current_state": context.current_state,
            "graph_status": graph_status,
            "approval_status": approval_status,
            "approval_type": approval_type,
            "last_event": context.metadata.get("last_event_processed"),
            "last_agent": context.metadata.get("last_agent_dispatched"),
            "timeline": timeline_entries,
            "step_data": context.step_data,
            "failure": last_error
        }

    def resume_workflow(self, workflow_id: str, approval_type: str, decision: str, payload: dict | None = None) -> bool:
        """
        Public facade method to resume a paused workflow from HITL gates.
        """
        context = self.active_contexts.get(workflow_id)
        if not context:
            raise KeyError(f"Workflow '{workflow_id}' not found.")
            
        state_model = state_manager.get_state(workflow_id)
        if not state_model:
            raise KeyError(f"State not found for workflow '{workflow_id}'")
            
        # Standardize decisions
        decision = decision.upper()
        if decision not in ["APPROVE", "REJECT"]:
            raise ValueError(f"Invalid resume action: {decision}")
            
        # Case A: SlotApproval
        if approval_type == "SlotApproval":
            # Verify we are actually awaiting slot approval
            if not context.metadata.get("paused_on_approval") == "SlotApproval":
                return False
                
            if decision == "APPROVE":
                resume_event = BaseEvent(
                    name="WorkflowResumed",
                    candidate_id=context.candidate.candidate_id,
                    payload=payload or {}
                )
                self.handle_event(resume_event)
                return True
            else:
                # Record rejection and schedule retry
                rejected = {
                    "interviewer_id": context.step_data.get("interviewer_id"),
                    "time_slot": context.step_data.get("scheduled_time")
                }
                context.metadata.setdefault("rejected_recommendations", []).append(rejected)
                
                # Clear previous recommendations
                context.step_data.pop("scheduled_time", None)
                context.step_data.pop("meeting_link", None)
                context.step_data.pop("interviewer_id", None)
                context.step_data.pop("interview_mode", None)
                context.step_data.pop("packet_id", None)
                
                context.metadata.pop("paused_on_approval", None)
                context.metadata.pop("pending_next_state", None)
                
                # Re-run recommendation invitation
                retry_event = BaseEvent(
                    name="RetryRequested",
                    candidate_id=context.candidate.candidate_id,
                    payload={"failed_agent": "agent6", "attempt": 0}
                )
                self.handle_event(retry_event)
                return True
                
        # Case B: OfflineFallback
        elif approval_type == "Offline Interview":
            if not context.metadata.get("proposed_fallback") == "Offline Interview":
                return False
                
            if decision == "APPROVE":
                context.step_data["interview_mode"] = "Offline"
                context.metadata["interview_mode"] = "Offline"
                context.step_data["meeting_link"] = None
                
                context.metadata.pop("proposed_fallback", None)
                context.metadata.pop("failure_reason", None)
                context.metadata.pop("fallback_applied", None)
                
                context.current_state = "InterviewScheduling"
                context.previous_state = "WorkflowPaused"
                state_manager.update_state(workflow_id, "InterviewScheduling", current_step="Process_FallbackApproved")
                
                self.retry_engine.reset_retry_count(context)
                
                retry_event = BaseEvent(
                    name="RetryRequested",
                    candidate_id=context.candidate.candidate_id,
                    payload={"failed_agent": "agent6", "attempt": 0, "fallback_applied": True}
                )
                self.handle_event(retry_event)
                return True
            else:
                # Rejected fallback leaves workflow paused
                return False

        # Case C: HREvaluationApproval - HR has filled in and submitted the evaluation form
        elif approval_type == "HREvaluationApproval":
            if not context.metadata.get("paused_on_approval") == "HREvaluationApproval":
                return False

            if decision == "APPROVE":
                context.step_data["hr_evaluation"] = payload or {}

                resume_event = BaseEvent(
                    name="WorkflowResumed",
                    candidate_id=context.candidate.candidate_id,
                    payload=payload or {}
                )
                self.handle_event(resume_event)

                # Chain straight into Agent 8 Turn 2 (compute HR score + rank cohort)
                submitted_event = BaseEvent(
                    name=EVENT_HR_EVALUATION_SUBMITTED,
                    candidate_id=context.candidate.candidate_id,
                    payload=payload or {}
                )
                self.handle_event(submitted_event)
                return True
            else:
                # Rejected/incomplete submission leaves workflow paused for a corrected resubmission
                return False

        # Case D: HRRankingApproval - hiring manager reviewed and approved the computed ranking
        elif approval_type == "HRRankingApproval":
            if not context.metadata.get("paused_on_approval") == "HRRankingApproval":
                return False

            if decision == "APPROVE":
                context.step_data["hr_final_decision"] = payload or {}

                resume_event = BaseEvent(
                    name="WorkflowResumed",
                    candidate_id=context.candidate.candidate_id,
                    payload=payload or {}
                )
                self.handle_event(resume_event)

                # Chain straight into Agent 8 Turn 3 (persist outcome)
                approved_event = BaseEvent(
                    name=EVENT_CANDIDATE_RANKING_APPROVED,
                    candidate_id=context.candidate.candidate_id,
                    payload=payload or {}
                )
                self.handle_event(approved_event)
                return True
            else:
                # Rejected ranking leaves workflow paused pending a fresh Turn 2
                return False

        return False
