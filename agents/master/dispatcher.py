import time
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from shared.registry.agent_registry import agent_registry
from shared.logger.logger import audit_logger, workflow_logger

class Dispatcher:
    """
    Dynamic execution dispatcher. Resolves agent namespaces from
    the AgentRegistry, handles invocation lifecycle, and tracks metrics.
    """

    def dispatch(self, agent_name: str, context: WorkflowContext) -> AgentResponse:
        """
        Loads and executes the worker agent matching the target key.
        
        Args:
            agent_name (str): Key of the agent registered in the registry.
            context (WorkflowContext): Active workflow details.
            
        Returns:
            AgentResponse: Result of the execution.
        """
        workflow_logger.info(f"Dispatching task to worker agent: {agent_name}", trace_id=context.workflow_id)
        start_time = time.time()
        
        try:
            # 1. Fetch class definition from registry
            agent_class = agent_registry.get_agent(agent_name)
            
            # 2. Instantiate worker agent
            agent_instance = agent_class()
            
            # 3. Execute work context
            response = agent_instance.run(context)
            
            # 4. Telemetry audit logs
            duration_ms = (time.time() - start_time) * 1000
            audit_logger.log_tool_call(
                tool_name=agent_name,
                status=response.execution_status,
                duration_ms=duration_ms,
                trace_id=context.workflow_id,
                metadata={"summary": response.summary}
            )
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            audit_logger.log_tool_call(
                tool_name=agent_name,
                status="FAILED",
                duration_ms=duration_ms,
                trace_id=context.workflow_id,
                metadata={"error": str(e)}
            )
            workflow_logger.logger.error(f"Dispatcher execution failed: {str(e)}")
            raise
