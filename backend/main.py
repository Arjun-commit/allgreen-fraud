"""FastAPI app entrypoint.

Phase 1: just wires up routes and healthcheck. No scoring yet.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import cases, events, friction, score
from backend.config import get_settings
from backend.logging_setup import configure_logging

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("api.startup", env=settings.api_env, port=settings.api_port)
    # TODO (phase 2): wire up Kafka producer, Redis pool, DB engine here
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="All-Green Fraud Detection",
    description="Behavioral fraud detection for social-engineering attacks",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — open in dev so the frontend on :3000 can hit us. Tighten in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not get_settings().is_prod else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router, prefix="/v1", tags=["events"])
app.include_router(score.router, prefix="/v1", tags=["score"])
app.include_router(friction.router, prefix="/v1", tags=["friction"])
app.include_router(cases.router, prefix="/v1", tags=["cases"])


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "allgreen-fraud", "docs": "/docs"}
