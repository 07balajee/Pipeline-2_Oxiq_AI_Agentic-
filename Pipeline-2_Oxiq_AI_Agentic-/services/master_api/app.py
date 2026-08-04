from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from services.master_api.routes import router
from services.master_api.dependencies import get_master_agent
import time
import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events coordinator to initialize the singleton MasterAgent.
    """
    get_master_agent()
    yield

app = FastAPI(
    title="OxiqAI HRMS Pipeline-2 Master Service API",
    version="1.0.0",
    lifespan=lifespan
)

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Middleware extracting and propagating correlation tracing headers.
    """
    try:
        corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = corr_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"An unhandled internal service crash occurred: {str(exc)}",
                "error_code": "SYSTEM_CRASH"
            }
        )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception mapper translating runtime failures to 500 detail json.
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"An unhandled internal service crash occurred: {str(exc)}",
            "error_code": "SYSTEM_CRASH"
        }
    )

app.include_router(router)
