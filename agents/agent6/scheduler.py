import time
from typing import List, Tuple, Dict, Any, Optional
from agents.agent6.models import InterviewMode, Interviewer, InterviewSlot, InterviewObject
from agents.agent6.validator import Validator
from agents.agent6.mode_selector import ModeSelector
from agents.agent6.interviewer_selector import InterviewerSelector
from agents.agent6.slot_selector import SlotSelector
from agents.agent6.builder import InterviewBuilder
from agents.agent6.response_builder import ResponseBuilder
from agents.agent6.tools import Agent6ToolsAdapter
from schemas.agent_response import AgentResponse
from schemas.mcp_response import MCPResponse
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class Scheduler:
    """
    Coordinates the multi-step scheduling sequence of Agent 6.
    Ensures clear separation of concerns by delegating actions to Mock MCP servers
    via the Agent6ToolsAdapter client wrapper.
    """
    def __init__(self):
        self.validator = Validator()
        self.mode_selector = ModeSelector()
        self.interviewer_selector = InterviewerSelector()
        self.slot_selector = SlotSelector()

    def run_scheduling_workflow(self, context: WorkflowContext) -> AgentResponse:
        """
        Executes the main orchestration path for Agent 6 scheduling.
        Optimized execution sequence:
        Validate -> Resume -> Read Candidate/Job -> Select Mode -> Select Interviewer -> Calendar slot check
        -> Reserve timeslot -> Create Meet -> Generate Document -> Prepare DB Transaction -> Commit DB state
        -> Send Notification
        """
        start_time = time.time()
        workflow_logger.info("Initializing Agent 6 scheduling coordinator...", trace_id=context.workflow_id)

        # Step 1: Validate candidate context schema locally
        is_valid, validation_errors = self.validator.validate(context)
        if not is_valid:
            return (
                ResponseBuilder()
                .with_status("FAILED")
                .with_errors(validation_errors)
                .with_summary("Candidate context validation failed.")
                .with_metadata({"duration_ms": (time.time() - start_time) * 1000})
                .build()
            )

        # MCP Action 1: Resume MCP call (Degraded Mode support)
        resume_url = context.candidate.resume_url
        resume_resp = Agent6ToolsAdapter.get_resume_summary(resume_url, context.workflow_id, context.metadata)
        self._print_mcp_telemetry(resume_resp)
        if resume_resp.status != "SUCCESS":
            # If name and email exist, continue in degraded mode
            if context.candidate.name and context.candidate.email:
                workflow_logger.info("Resume MCP call failed. Proceeding in degraded mode with available candidate context.", trace_id=context.workflow_id)
                context.metadata["degraded_mode"] = True
                context.metadata["degraded_reason"] = "Resume MCP unavailable"
            else:
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Resume MCP call failed: {resume_resp.errors}"])
                    .build()
                )

        # MCP Action 2: Database MCP (Read Candidate)
        db_read_resp = Agent6ToolsAdapter.read_candidate(context.candidate.candidate_id, context.workflow_id, context.metadata)
        self._print_mcp_telemetry(db_read_resp)
        if db_read_resp.status != "SUCCESS":
            return (
                ResponseBuilder()
                .with_status("FAILED")
                .with_errors([f"Database candidate read failed: {db_read_resp.errors}"])
                .build()
            )

        # MCP Action 2b: Database MCP (Read Job)
        db_job_resp = Agent6ToolsAdapter.read_job(context.candidate.job_id, context.workflow_id, context.metadata)
        self._print_mcp_telemetry(db_job_resp)
        if db_job_resp.status != "SUCCESS":
            return (
                ResponseBuilder()
                .with_status("FAILED")
                .with_errors([f"Database job read failed: {db_job_resp.errors}"])
                .build()
            )

        job_payload = db_job_resp.payload
        is_job_valid, job_errors = self.validator.validate_job_payload(job_payload, context.workflow_id)
        if not is_job_valid:
            return (
                ResponseBuilder()
                .with_status("FAILED")
                .with_errors(job_errors)
                .with_summary("Job context validation failed.")
                .build()
            )

        # Step 2: Determine Interview Mode (Online vs Offline)
        mode = self.mode_selector.select_mode(context)

        # Step 3: Select & Match Interviewer (Idempotency checkpoint)
        interviewer_id = context.step_data.get("interviewer_id")
        interviewer = None
        score_breakdown = {"total_score": 0, "reasons": []}
        
        if interviewer_id:
            from agents.agent6.interviewer_selector import InterviewerSelector
            selector = InterviewerSelector()
            interviewer = next((i for i in selector.mock_interviewers if i.interviewer_id == interviewer_id), None)
            score_breakdown = {"total_score": 100, "reasons": ["✓ Reused matching interviewer from checkpoint"]}
            workflow_logger.info(f"Idempotency: Reusing selected interviewer '{interviewer_id}'", trace_id=context.workflow_id)

        if not interviewer:
            try:
                interviewer_match = self.interviewer_selector.select_interviewer(context, job_payload, mode)
                if not interviewer_match:
                    return (
                        ResponseBuilder()
                        .with_status("FAILED")
                        .with_errors(["No eligible interviewer found matching candidate and job requirements."])
                        .with_summary("Interviewer matching failed.")
                        .build()
                    )
                interviewer, score_breakdown = interviewer_match
            except Exception as e:
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([str(e)])
                    .with_summary("Calendar availability query failed.")
                    .build()
                )

        # Step 4: Select Available Slot (Idempotency checkpoint)
        scheduled_time = context.step_data.get("scheduled_time")
        slot = None
        slot_reason = "Reused matching slot from checkpoint"

        if scheduled_time:
            slot = InterviewSlot(slot_id=context.step_data.get("slot_id") or "slot-reused", label=scheduled_time)
            workflow_logger.info(f"Idempotency: Reusing scheduled slot '{scheduled_time}'", trace_id=context.workflow_id)
        
        if not slot:
            try:
                slot_match = self.slot_selector.select_slot(context, interviewer.interviewer_id)
                if not slot_match:
                    return (
                        ResponseBuilder()
                        .with_status("FAILED")
                        .with_errors([f"No available conflict-free slots found for interviewer '{interviewer.name}'."])
                        .with_summary("Time slot selection failed.")
                        .build()
                    )
                slot, slot_reason = slot_match
            except Exception as e:
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([str(e)])
                    .with_summary("Calendar availability query failed.")
                    .build()
                )

        # Print final recommendations if interactive
        is_interactive = context.metadata.get("interactive", False)
        if is_interactive and not context.step_data.get("scheduled_time"):
            print("\nRecommended:")
            print(f"  {interviewer.name}")
            print(f"  {interviewer.role}")
            print(f"\nMatch Score: {score_breakdown['total_score']}/100")
            print("Reasons:")
            for reason in score_breakdown["reasons"]:
                print(f"  {reason}")
            print("--------------------------------------------------")

        # Deterministic Idempotency Keys matching architectural trace standards
        cand_id = context.candidate.candidate_id
        calendar_key = f"pl2:{cand_id}:agent6:calendar_reservation"
        meet_key = f"pl2:{cand_id}:agent6:meet_creation"
        doc_key = f"pl2:{cand_id}:agent6:document_generation"
        notify_key = f"pl2:{cand_id}:agent6:notification"
        db_write_key = f"pl2:{cand_id}:agent6:database_write"

        # MCP Action 3: Calendar MCP (Reserve timeslot with Idempotency check)
        booking_id = context.step_data.get("booking_id")
        if not booking_id:
            cal_reserve_resp = Agent6ToolsAdapter.reserve_slot(
                slot.slot_id, interviewer.name, context.workflow_id,
                idempotency_key=calendar_key, metadata=context.metadata
            )
            self._print_mcp_telemetry(cal_reserve_resp)
            if cal_reserve_resp.status != "SUCCESS":
                # Check for slot unavailable (simulation hook)
                if "available" in str(cal_reserve_resp.errors).lower():
                    workflow_logger.logger.warning(f"Slot {slot.label} unavailable. Blacklisting and retrying.")
                    rejected = {
                        "interviewer_id": interviewer.interviewer_id,
                        "time_slot": slot.label
                    }
                    context.metadata.setdefault("rejected_recommendations", []).append(rejected)
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Calendar reservation failed: {cal_reserve_resp.errors}"])
                    .build()
                )
            booking_id = cal_reserve_resp.payload.get("booking_id")
            context.step_data["booking_id"] = booking_id
            context.step_data["calendar_reservation_idempotency_key"] = calendar_key
        else:
            workflow_logger.info(f"Idempotency Checkpoint: Skipped Calendar reservation. Reused booking '{booking_id}'", trace_id=context.workflow_id)

        # MCP Action 4: Meet MCP (Online mode only with Idempotency check)
        meeting_link = context.step_data.get("meeting_link")
        if mode == InterviewMode.ONLINE and not meeting_link:
            meet_resp = Agent6ToolsAdapter.generate_meeting(
                context.workflow_id, idempotency_key=meet_key, metadata=context.metadata
            )
            self._print_mcp_telemetry(meet_resp)
            if meet_resp.status != "SUCCESS" or not meet_resp.payload or not meet_resp.payload.get("meeting_url"):
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Meet link generation failed: {meet_resp.errors if meet_resp else 'Empty payload'}"])
                    .build()
                )
            meeting_link = meet_resp.payload.get("meeting_url")
            context.step_data["meeting_link"] = meeting_link
            context.step_data["meet_creation_idempotency_key"] = meet_key
        elif meeting_link:
            workflow_logger.info(f"Idempotency Checkpoint: Skipped Meet generation. Reused meet link '{meeting_link}'", trace_id=context.workflow_id)

        # Step 5: Build Interview Object locally
        interview_obj = self.build_interview_object(context, mode, interviewer, slot, meeting_link)

        # MCP Action 5: Document MCP (Generate interview packet with Idempotency check)
        packet_id = context.step_data.get("packet_id")
        if not packet_id:
            doc_resp = Agent6ToolsAdapter.generate_interview_packet(
                interview_obj.model_dump(), context.workflow_id,
                idempotency_key=doc_key, metadata=context.metadata
            )
            self._print_mcp_telemetry(doc_resp)
            if doc_resp.status != "SUCCESS":
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Interview packet generation failed: {doc_resp.errors}"])
                    .build()
                )
            packet_id = doc_resp.payload.get("packet_id")
            context.step_data["packet_id"] = packet_id
            context.step_data["document_generation_idempotency_key"] = doc_key
        else:
            workflow_logger.info(f"Idempotency Checkpoint: Skipped Document generation. Reused packet '{packet_id}'", trace_id=context.workflow_id)

        # MCP Action 6: Database MCP (Prepare writes BEFORE notification)
        update_prep = context.step_data.get("db_update_prepared")
        if not update_prep:
            update_prep_resp = Agent6ToolsAdapter.prepare_candidate_update(
                context.candidate.candidate_id, "InterviewScheduled", context.workflow_id,
                idempotency_key=db_write_key, metadata=context.metadata
            )
            self._print_mcp_telemetry(update_prep_resp)
            if update_prep_resp.status != "SUCCESS":
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Database candidate update preparation failed: {update_prep_resp.errors}"])
                    .build()
                )
            update_prep = update_prep_resp.payload
            context.step_data["db_update_prepared"] = update_prep
            context.step_data["database_write_idempotency_key"] = db_write_key
        
        insert_prep = context.step_data.get("db_insert_prepared")
        if not insert_prep:
            insert_prep_resp = Agent6ToolsAdapter.prepare_database_payload(
                context.candidate.candidate_id, interviewer.interviewer_id, slot.label, context.workflow_id,
                idempotency_key=db_write_key, metadata=context.metadata
            )
            self._print_mcp_telemetry(insert_prep_resp)
            if insert_prep_resp.status != "SUCCESS":
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Database interview insertion preparation failed: {insert_prep_resp.errors}"])
                    .build()
                )
            insert_prep = insert_prep_resp.payload
            context.step_data["db_insert_prepared"] = insert_prep

        # Commit transactions BEFORE dispatching notifications to guarantee consistency
        db_committed = context.step_data.get("db_committed")
        if not db_committed:
            commit_update_resp = Agent6ToolsAdapter.commit_transaction(update_prep, context.workflow_id, context.metadata)
            self._print_mcp_telemetry(commit_update_resp)
            if commit_update_resp.status != "SUCCESS":
                from agents.agent6.compensation import CompensationManager
                CompensationManager.compensate(context, update_prep, insert_prep)
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Database commit for candidate update failed: {commit_update_resp.errors}"])
                    .build()
                )

            commit_insert_resp = Agent6ToolsAdapter.commit_transaction(insert_prep, context.workflow_id, context.metadata)
            self._print_mcp_telemetry(commit_insert_resp)
            if commit_insert_resp.status != "SUCCESS":
                from agents.agent6.compensation import CompensationManager
                CompensationManager.compensate(context, update_prep, insert_prep)
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Database commit for interview record failed: {commit_insert_resp.errors}"])
                    .build()
                )
            context.step_data["db_committed"] = True
        else:
            workflow_logger.info("Idempotency Checkpoint: Database transaction already committed.", trace_id=context.workflow_id)

        # MCP Action 7: Notification MCP (Dispatch email only AFTER database commit success)
        notification_sent = context.step_data.get("notification_sent")
        if not notification_sent:
            email_body = f"Hello {context.candidate.name}, you have been scheduled for an interview on {slot.label} with {interviewer.name}."
            notify_resp = Agent6ToolsAdapter.send_notification(
                context.candidate.email,
                "Interview Confirmation",
                email_body,
                context.workflow_id,
                idempotency_key=notify_key,
                metadata=context.metadata
            )
            self._print_mcp_telemetry(notify_resp)
            if notify_resp.status != "SUCCESS":
                # Return failed, the DB writes are committed so next retry will reuse it and only retry notification!
                return (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_errors([f"Notification dispatch failed: {notify_resp.errors}"])
                    .build()
                )
            context.step_data["notification_sent"] = True
            context.step_data["notification_idempotency_key"] = notify_key
        else:
            workflow_logger.info("Idempotency Checkpoint: Notification already sent.", trace_id=context.workflow_id)

        # Persist finalized scheduling metrics
        context.step_data["scheduled_time"] = slot.label
        context.step_data["slot_id"] = slot.slot_id
        context.step_data["interviewer_id"] = interviewer.interviewer_id
        context.step_data["interview_mode"] = mode.value

        # Step 6: Build final AgentResponse
        duration_ms = (time.time() - start_time) * 1000
        
        summary_msg = (
            f"Interview successfully scheduled for {context.candidate.name} with "
            f"{interviewer.name} ({interviewer.role}) on {slot.label}."
        )
        
        response = (
            ResponseBuilder()
            .with_status("SUCCESS")
            .with_event_and_state("InterviewCreated", "InterviewScheduled")
            .with_summary(summary_msg)
            .with_metadata({
                **interview_obj.model_dump(),
                "duration_ms": duration_ms,
                "interviewer_score": score_breakdown.get("total_score"),
                "interviewer_reasons": score_breakdown.get("reasons"),
                "slot_reason": slot_reason
            })
            .build()
        )
        
        workflow_logger.info("Agent 6 scheduling completed successfully.", trace_id=context.workflow_id)
        return response

    def build_interview_object(
        self,
        context: WorkflowContext,
        mode: InterviewMode,
        interviewer: Interviewer,
        slot: InterviewSlot,
        meeting_link: Optional[str]
    ) -> InterviewObject:
        workflow_logger.info("Scheduling step: Build Interview Object", trace_id=context.workflow_id)
        builder = (
            InterviewBuilder()
            .with_context(context)
            .with_mode(mode)
            .with_interviewer(interviewer)
            .with_slot(slot)
            .with_status("SCHEDULED")
        )
        return builder.build()

    def _print_mcp_telemetry(self, response: MCPResponse):
        """
        Renders telemetry trace logs in structured visual console boxes.
        """
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f" [{response.mcp_name}] - EXECUTION SUCCESSFUL")
        print(f"  Status        : {response.status}")
        print(f"  Trace ID      : {response.trace_id}")
        print(f"  Workflow ID   : {response.workflow_id}")
        print(f"  Execution Time: {response.execution_time_ms:.1f} ms")
        if response.payload:
            print(f"  Payload       : {response.payload}")
        if response.warnings:
            print(f"  Warnings      : {response.warnings}")
        if response.errors:
            print(f"  Errors        : {response.errors}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
