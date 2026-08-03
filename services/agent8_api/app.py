from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.agent8_api.routes import router
from services.agent8_api.dependencies import initialize_dependencies

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan manager to initialize composition root dependencies at startup.
    """
    initialize_dependencies()
    yield

app = FastAPI(
    title="OxiqAI HRMS Recruitment Pipeline-2 - Agent 8 FastAPI Service",
    description="Microservice adapter wrapping the HRInterviewAgent (Agent 8) evaluation & ranking loop.",
    version="1.0.0",
    lifespan=lifespan
)

# Register endpoints under prefix matching API contract specification
app.include_router(router, prefix="/v1/agents/agent8")
