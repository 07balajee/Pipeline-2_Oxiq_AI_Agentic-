import logging
import sys
import time
from typing import Any, Dict, Optional

class BaseStructuredLogger:
    """
    Base logger class to provide structured, JSON-like logging outputs.
    Ensures all trace logs automatically correlate via a trace_id.
    """
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Ensure we have a standard stream handler outputting to stdout
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _format_message(self, message: str, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        parts = []
        if trace_id:
            parts.append(f"[TraceID: {trace_id}]")
        parts.append(message)
        if metadata:
            parts.append(f"| Context: {metadata}")
        return " ".join(parts)


class WorkflowLogger(BaseStructuredLogger):
    """
    Logs high-level candidate state transitions, agent runs, and lifecycle checkpoints.
    """
    def __init__(self, level: str = "INFO"):
        super().__init__("WorkflowLogger", level)

    def info(self, message: str, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        formatted = self._format_message(message, trace_id, metadata)
        self.logger.info(formatted)


class AuditLogger(BaseStructuredLogger):
    """
    Logs physical database mutations, tool calls, and credential checks.
    """
    def __init__(self, level: str = "INFO"):
        super().__init__("AuditLogger", level)

    def log_mutation(self, table: str, operation: str, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        msg = f"DATABASE MUTATION | Table: {table} | Operation: {operation}"
        formatted = self._format_message(msg, trace_id, metadata)
        self.logger.info(formatted)

    def log_tool_call(self, tool_name: str, status: str, duration_ms: float, trace_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        msg = f"TOOL EXECUTION | Tool: {tool_name} | Status: {status} | Latency: {duration_ms:.2f}ms"
        formatted = self._format_message(msg, trace_id, metadata)
        self.logger.info(formatted)

    def log_distributed_telemetry(
        self,
        workflow_id: str,
        correlation_id: str,
        agent_name: str,
        event: Optional[str],
        state: Optional[str],
        operation: str,
        latency_ms: float,
        retry_count: int = 0,
        error_category: Optional[str] = None
    ):
        meta = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "agent_name": agent_name,
            "event": event,
            "state": state,
            "operation": operation,
            "latency_ms": round(latency_ms, 2),
            "retry_count": retry_count,
            "error_category": error_category
        }
        msg = f"DISTRIBUTED TELEMETRY | Agent: {agent_name} | Op: {operation} | Latency: {latency_ms:.2f}ms"
        formatted = self._format_message(msg, trace_id=correlation_id, metadata=meta)
        self.logger.info(formatted)


class ErrorLogger(BaseStructuredLogger):
    """
    Logs exceptions, validation errors, and critical system faults.
    """
    def __init__(self, level: str = "ERROR"):
        super().__init__("ErrorLogger", level)

    def error(self, message: str, trace_id: Optional[str] = None, error: Optional[Exception] = None, metadata: Optional[Dict[str, Any]] = None):
        meta = metadata or {}
        if error:
            meta["exception_type"] = type(error).__name__
            meta["exception_message"] = str(error)
        formatted = self._format_message(message, trace_id, meta)
        self.logger.error(formatted)

# Global logging singletons
workflow_logger = WorkflowLogger()
audit_logger = AuditLogger()
error_logger = ErrorLogger()
