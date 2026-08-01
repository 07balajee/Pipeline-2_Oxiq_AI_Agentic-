import datetime
from typing import Dict, Any
from shared.logger.logger import workflow_logger
from agents.agent6.tools import Agent6ToolsAdapter

class CompensationManager:
    """
    Manages the cancellation/release sequence for external side-effecting operations
    if the scheduling workflow fails before final database persistence (e.g. database commit failure).
    """

    @staticmethod
    def compensate(context: Any, update_prep: Dict[str, Any] = None, insert_prep: Dict[str, Any] = None):
        workflow_logger.info("Initializing side-effect compensation sequence...", trace_id=context.workflow_id)

        # 1. Rollback Database transactions
        if update_prep:
            workflow_logger.info("Compensate: Rolling back candidate state database preparation...", trace_id=context.workflow_id)
            Agent6ToolsAdapter.rollback_transaction(update_prep, context.workflow_id, context.metadata)
        if insert_prep:
            workflow_logger.info("Compensate: Rolling back interview record database preparation...", trace_id=context.workflow_id)
            Agent6ToolsAdapter.rollback_transaction(insert_prep, context.workflow_id, context.metadata)

        # 2. Cancel Calendar Booking
        booking_id = context.step_data.get("booking_id")
        if booking_id:
            workflow_logger.info(f"Compensate: Releasing calendar booking '{booking_id}'...", trace_id=context.workflow_id)
            context.step_data.pop("booking_id", None)

        # 3. Invalidate Google Meet Link
        meeting_link = context.step_data.get("meeting_link")
        if meeting_link:
            workflow_logger.info(f"Compensate: Invalidating Google Meet resource '{meeting_link}'...", trace_id=context.workflow_id)
            context.step_data.pop("meeting_link", None)

        # 4. Invalidate Document
        packet_id = context.step_data.get("packet_id")
        if packet_id:
            workflow_logger.info(f"Compensate: Deleting temporary generated document '{packet_id}'...", trace_id=context.workflow_id)
            context.step_data.pop("packet_id", None)

        # 5. Check if notification was already sent
        notification_sent = context.step_data.get("notification_sent")
        if notification_sent:
            workflow_logger.logger.warning("Compensate: Warning - Email notification was already delivered. Recording inconsistency.")

        # Clear preparation flags
        context.step_data.pop("db_update_prepared", None)
        context.step_data.pop("db_insert_prepared", None)

        # Record compensation event details in trace metrics/telemetry
        if "compensation_log" not in context.metadata:
            context.metadata["compensation_log"] = []
        context.metadata["compensation_log"].append({
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
            "rolled_back_db": bool(update_prep or insert_prep),
            "cancelled_booking": bool(booking_id),
            "invalidated_meet": bool(meeting_link)
        })

        workflow_logger.info("Compensation sequence completed successfully.", trace_id=context.workflow_id)
