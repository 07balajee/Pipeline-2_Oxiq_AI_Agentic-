import uuid
from typing import Optional
import httpx
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse

class AgentTransportError(Exception):
    """
    Typed exception for classification of HTTP and transport boundaries failure.
    """
    def __init__(self, agent: str, category: str, message: str, status_code: Optional[int] = None):
        super().__init__(f"Agent [{agent}] transport failed ({category}): {message}")
        self.agent = agent
        self.category = category
        self.message = message
        self.status_code = status_code

class AgentServiceClient:
    """
    Service client abstraction managing the serialization, correlation,
    timeout boundaries, and error classification for Master-Worker agent communication.
    """
    def __init__(self, service_url: str, timeout: float):
        self.service_url = service_url
        self.timeout = timeout

    def execute(self, context: WorkflowContext, agent_name: str = "agent6") -> AgentResponse:
        """
        Invokes the worker agent endpoint over HTTP.
        """
        url = f"{self.service_url}/v1/agents/{agent_name}/execute"
        correlation_id = context.metadata.get("correlation_id") or context.workflow_id or str(uuid.uuid4())
        
        # Deterministic Idempotency Key matching frozen specification
        idempotency_key = f"pl2:{correlation_id}:{agent_name}:{context.current_state}"
        
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id,
            "X-Idempotency-Key": idempotency_key
        }
        
        try:
            payload = context.model_dump()
            # Remote services have no terminal — force non-interactive execution
            payload.setdefault("metadata", {})
            payload["metadata"]["interactive"] = False
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers=headers
                )
        except httpx.ConnectError as ce:
            raise AgentTransportError(
                agent=agent_name,
                category="CONNECTION_ERROR",
                message=f"Cannot reach agent service: {str(ce)}"
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.TimeoutException) as te:
            raise AgentTransportError(
                agent=agent_name,
                category="TIMEOUT",
                message=f"Request to agent service timed out: {str(te)}"
            )
        except Exception as e:
            raise AgentTransportError(
                agent=agent_name,
                category="CONNECTION_ERROR",
                message=f"Unexpected transport failure: {str(e)}"
            )
            
        # Classify HTTP service errors
        if response.status_code != 200:
            raise AgentTransportError(
                agent=agent_name,
                category="HTTP_SERVICE_ERROR",
                status_code=response.status_code,
                message=f"Agent service returned HTTP {response.status_code}: {response.text}"
            )
            
        # Parse returned JSON
        try:
            data = response.json()
        except ValueError as ve:
            raise AgentTransportError(
                agent=agent_name,
                category="INVALID_RESPONSE",
                message=f"Failed to decode JSON response: {str(ve)}"
            )
            
        # Enforce contract validation
        try:
            agent_response = AgentResponse(**data)
            return agent_response
        except Exception as pe:
            raise AgentTransportError(
                agent=agent_name,
                category="CONTRACT_ERROR",
                message=f"Returned JSON violates AgentResponse contract: {str(pe)}"
            )
