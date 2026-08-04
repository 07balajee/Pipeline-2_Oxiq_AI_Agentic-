from typing import Dict, Optional
from schemas.workflow_state import WorkflowStateModel
from shared.logger.logger import audit_logger

class StateManager:
    """
    Manages active workflow states, step sequences, retry counts, and processing times.
    Acts as an in-memory database simulator for Phase 2.
    """
    def __init__(self):
        self._states: Dict[str, WorkflowStateModel] = {}

    def get_state(self, workflow_id: str) -> Optional[WorkflowStateModel]:
        """
        Retrieves the state details associated with a workflow ID.
        """
        return self._states.get(workflow_id)

    def save_state(self, state: WorkflowStateModel):
        """
        Saves or updates a workflow state record.
        """
        self._states[state.workflow_id] = state
        audit_logger.log_mutation(
            table="workflow_states (in-memory)",
            operation="UPSERT",
            trace_id=state.workflow_id,
            metadata=state.model_dump()
        )

    def update_state(self, workflow_id: str, new_state: str, current_step: str):
        """
        Updates the active state flag and step tracking indicators.
        """
        state = self.get_state(workflow_id)
        if not state:
            raise KeyError(f"Workflow State '{workflow_id}' not initialized.")
        
        state.previous_state = state.current_state
        state.current_state = new_state
        state.previous_step = state.current_step
        state.current_step = current_step
        
        self.save_state(state)

    def increment_retry(self, workflow_id: str) -> int:
        """
        Increments the transaction retry counter.
        """
        state = self.get_state(workflow_id)
        if not state:
            raise KeyError(f"Workflow State '{workflow_id}' not initialized.")
        
        state.retry_count += 1
        self.save_state(state)
        return state.retry_count

    def reset_retry(self, workflow_id: str):
        """
        Resets retry attempts back to zero.
        """
        state = self.get_state(workflow_id)
        if not state:
            raise KeyError(f"Workflow State '{workflow_id}' not initialized.")
        
        state.retry_count = 0
        self.save_state(state)

    def accumulate_time(self, workflow_id: str, duration_seconds: float):
        """
        Aggregates execution latency.
        """
        state = self.get_state(workflow_id)
        if not state:
            raise KeyError(f"Workflow State '{workflow_id}' not initialized.")
        
        state.execution_time += duration_seconds
        self.save_state(state)

# Global StateManager instance
state_manager = StateManager()
