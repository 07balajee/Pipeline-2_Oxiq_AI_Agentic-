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
            from shared.config.settings import settings
            from shared.clients.agent_client import AgentServiceClient
            from shared.config.constants import AGENT_INVITATION, AGENT_TECHNICAL, AGENT_HR_RANKING

            # Check if agent is registered locally in registry (primarily for unit test environment)
            is_local = False
            try:
                agent_class = agent_registry.get_agent(agent_name)
                is_local = True
            except KeyError:
                pass

            if agent_name == AGENT_INVITATION and not is_local:
                # 1. Initialize HTTP Client with settings config for Agent 6
                client = AgentServiceClient(
                    service_url=settings.agent6_service_url,
                    timeout=settings.agent_http_timeout_seconds
                )
                response = client.execute(context, agent_name=agent_name)
            elif agent_name == AGENT_TECHNICAL and not is_local:
                # 2. Initialize HTTP Client with settings config for Agent 7
                client = AgentServiceClient(
                    service_url=settings.agent7_service_url,
                    timeout=settings.agent_http_timeout_seconds
                )
                response = client.execute(context, agent_name=agent_name)
            elif agent_name == AGENT_HR_RANKING and not is_local:
                # 3. Initialize HTTP Client with settings config for Agent 8
                client = AgentServiceClient(
                    service_url=settings.agent8_service_url,
                    timeout=settings.agent_http_timeout_seconds
                )
                response = client.execute(context, agent_name=agent_name)
            else:
                # Fall back to local unit test execution if agent is registered locally
                if not is_local:
                    agent_class = agent_registry.get_agent(agent_name)
                agent_instance = agent_class()
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
