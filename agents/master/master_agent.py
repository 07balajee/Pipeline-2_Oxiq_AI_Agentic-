import time
import uuid
from typing import Dict
from schemas.workflow_state import WorkflowStateModel
from shared.config.constants import (
    STATE_CANDIDATE_SHORTLISTED,
    EVENT_CANDIDATE_SHORTLISTED,
    STATE_WORKFLOW_PAUSED,
    STATE_WORKFLOW_FAILED,
    STATE_OFFER_PIPELINE_TRIGGERED,
    STATE_CANDIDATE_REJECTED
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

class MasterAgent:
    """
    The orchestrator of Pipeline-2. Upgraded to support advanced workflow state management,
    modular event store logging, human approval pause gates, retries, and fallback paths.
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
        
        self._subscribe_events()

    def _subscribe_events(self):
        """
        Subscribes the orchestration handler to all valid workflow event types.
        """
        for event_type in EventTypes:
            event_bus.subscribe(event_type.value, self.handle_event)

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

        # Check approval resume case
        if event.name == "WorkflowResumed":
            self.event_store.log_event(event, "Completed")
            pending_next_state = context.metadata.pop("pending_next_state", None)
            paused_approval = context.metadata.pop("paused_on_approval", None)
            
            if pending_next_state:
                context.previous_state = context.current_state
                context.current_state = pending_next_state
                state_manager.update_state(workflow_id, pending_next_state, current_step="Process_WorkflowResumed")
                timeline.add_milestone(f"Human Approval Granted: {paused_approval}")
                timeline.add_milestone(f"Workflow Resumed to State: {pending_next_state}")
                
                # Check for handoff transitions on resume
                if pending_next_state == STATE_OFFER_PIPELINE_TRIGGERED:
                    self.complete_workflow(workflow_id, trace, timeline)
                return

        # Check if the workflow is currently suspended in paused or failed state
        if state.current_state in [STATE_WORKFLOW_PAUSED, STATE_WORKFLOW_FAILED] and event.name != "WorkflowResumed":
            workflow_logger.info(
                f"Workflow {workflow_id} is currently suspended in '{state.current_state}'. Ignoring event {event.name}.",
                trace_id=workflow_id
            )
            return

        # 1. Context Merging & Preparation
        self.context_manager.prepare_execution_context(context, event)

        # 2. Routing transition check via WorkflowEngine
        start_time = time.time()
        next_state, target_agent = self.workflow_engine.resolve_next_step(context, event.name)
        duration_ms = (time.time() - start_time) * 1000
        
        trace.add_step(
            actor="MasterAgent",
            action=f"RouteStateFrom_{context.current_state}_Via_{event.name}",
            status="SUCCESS",
            duration_ms=duration_ms,
            input_payload={"event": event.name, "current_state": context.current_state},
            output_payload={"next_state": next_state, "target_agent": target_agent}
        )

        # 3. Human Approval check before proceeding to next state
        if self.approval_engine.should_pause_for_approval(context.current_state, next_state, context):
            approval_type = self.approval_engine.process_approval(context.current_state, next_state, context)
            timeline.add_milestone(f"Workflow Paused on Approval: {approval_type}")
            self.event_store.log_event(event, "Completed")
            return

        # Process standard state shift
        context.previous_state = context.current_state
        context.current_state = next_state
        state_manager.update_state(workflow_id, next_state, current_step=f"Process_{event.name}")
        timeline.add_milestone(f"State transitioned: {context.previous_state} -> {next_state}")

        # 4. Invoke Worker Agent if target exists
        if target_agent:
            agent_start = time.time()
            timeline.add_milestone(f"Invoking Worker Agent: {target_agent}")
            try:
                response = self.dispatcher.dispatch(target_agent, context)
                agent_duration = (time.time() - agent_start) * 1000
                state_manager.accumulate_time(workflow_id, agent_duration / 1000.0)
                
                # Response schema validation using ResponseValidator
                is_valid, validation_errors = self.response_validator.validate_response(target_agent, response)
                
                if not is_valid:
                    self.event_store.log_event(event, "Failed")
                    trace.add_step(
                        actor=target_agent,
                        action="RunTask",
                        status="FAILED",
                        duration_ms=agent_duration,
                        input_payload={"context_state": context.previous_state},
                        output_payload={"errors": validation_errors}
                    )
                    self.handle_agent_failure(workflow_id, target_agent, validation_errors)
                    return

                trace.add_step(
                    actor=target_agent,
                    action="RunTask",
                    status=response.execution_status,
                    duration_ms=agent_duration,
                    input_payload={"context_state": context.previous_state},
                    output_payload=response.model_dump()
                )

                if response.execution_status == "SUCCESS":
                    self.event_store.log_event(event, "Completed")
                    self.retry_engine.reset_retry_count(context)
                    timeline.add_milestone(f"Agent {target_agent} completed successfully")
                    
                    if response.generated_event:
                        next_event = BaseEvent(
                            name=response.generated_event,
                            candidate_id=context.candidate.candidate_id,
                            payload=response.metadata
                        )
                        self.event_store.log_event(next_event, "Created")
                        event_bus.publish(next_event)
                else:
                    self.event_store.log_event(event, "Failed")
                    self.handle_agent_failure(workflow_id, target_agent, response.errors)
                    
            except Exception as e:
                self.event_store.log_event(event, "Failed")
                agent_duration = (time.time() - agent_start) * 1000
                error_logger.error(f"Execution crash in agent {target_agent}: {str(e)}", trace_id=workflow_id, error=e)
                trace.add_step(
                    actor=target_agent,
                    action="RunTask",
                    status="FAILED",
                    duration_ms=agent_duration,
                    output_payload={"error": str(e)}
                )
                self.handle_agent_failure(workflow_id, target_agent, [str(e)])
        else:
            # Check terminal states
            self.event_store.log_event(event, "Completed")
            if next_state == STATE_OFFER_PIPELINE_TRIGGERED:
                self.complete_workflow(workflow_id, trace, timeline)
            elif next_state == STATE_CANDIDATE_REJECTED:
                workflow_logger.info(f"Workflow {workflow_id} reached rejection state. Candidate archived.", trace_id=workflow_id)
                trace.final_status = "REJECTED"
                trace.end_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                timeline.add_milestone("Workflow ended: Candidate Rejected")

    def complete_workflow(self, workflow_id: str, trace: WorkflowTrace, timeline: Timeline):
        workflow_logger.info(f"Workflow {workflow_id} reached handoff state. Handing off details to Pipeline-3...", trace_id=workflow_id)
        trace.final_status = "COMPLETED"
        trace.end_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        audit_logger.log_tool_call("Pipeline3_Handoff", "SUCCESS", 15.0, trace_id=workflow_id)
        timeline.add_milestone("Workflow completed and handed off to Pipeline-3")

    def handle_agent_failure(self, workflow_id: str, agent_name: str, errors: list):
        """
        Escalation handler if worker agent tasks fail.
        """
        context = self.active_contexts[workflow_id]
        timeline = self.active_timelines[workflow_id]
        
        # Check retry count eligibility
        if self.retry_engine.should_retry(context):
            attempt = self.retry_engine.increment_retry_count(context)
            timeline.add_milestone(f"Retry attempt {attempt} for agent {agent_name}")
            
            retry_event = BaseEvent(
                name="RetryRequested",
                candidate_id=context.candidate.candidate_id,
                payload={"failed_agent": agent_name, "attempt": attempt}
            )
            self.event_store.log_event(retry_event, "Created")
            event_bus.publish(retry_event)
        else:
            # Check fallback eligibility
            failure_reason = ", ".join(errors)
            if self.fallback_engine.execute_fallback(context, failure_reason):
                timeline.add_milestone("Fallback applied: Swapped to Offline mode")
                # Reset retries and re-dispatch step
                self.retry_engine.reset_retry_count(context)
                retry_event = BaseEvent(
                    name="RetryRequested",
                    candidate_id=context.candidate.candidate_id,
                    payload={"failed_agent": agent_name, "attempt": 0, "fallback_applied": True}
                )
                self.event_store.log_event(retry_event, "Created")
                event_bus.publish(retry_event)
            else:
                # Exhausted. Mark paused/failed
                workflow_logger.logger.error(f"Workflow {workflow_id} failed. Placing in paused state.")
                state_manager.update_state(workflow_id, STATE_WORKFLOW_PAUSED, current_step=f"Error_{agent_name}_Paused")
                trace = self.active_traces[workflow_id]
                trace.final_status = "PAUSED"
                timeline.add_milestone(f"Retries exhausted. Workflow paused.")
