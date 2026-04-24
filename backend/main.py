"""FastAPI app entrypoint.

Wires up routes, middleware (auth, rate limiting, metrics), and healthcheck.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.middleware.metrics import PrometheusMiddleware, metrics_endpoint
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.routes import cases, events, friction, score, settings
from backend.config import get_settings
from backend.logging_setup import configure_logging

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("api.startup", env=settings.api_env, port=settings.api_port)

    # Load model AUC metrics into Prometheus on startup
    _register_model_metrics()

    yield
    log.info("api.shutdown")


def _register_model_metrics() -> None:
    """Push latest model AUCs to Prometheus gauges on startup."""
    import json
    import os

    from backend.api.middleware.metrics import set_model_auc

    for model_name, rel_path in [
        ("lstm", "ml/lstm/artifacts/metrics.json"),
        ("xgboost", "ml/xgboost/artifacts/metrics.json"),
    ]:
        path = os.path.join(os.path.dirname(__file__), "..", rel_path)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                auc = data.get("val_auc")
                if auc is not None:
                    set_model_auc(model_name, auc)
                    log.info("metrics.model_auc_loaded", model=model_name, auc=auc)
            except Exception:
                log.debug("metrics.model_auc_load_failed", model=model_name)


app = FastAPI(
    title="All-Green Fraud Detection",
    description="Behavioral fraud detection for social-engineering attacks",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS -- open in dev, tighten in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not get_settings().is_prod else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(PrometheusMiddleware)
app.add_middleware(RateLimitMiddleware, enabled=get_settings().is_prod or True)
# ^ enabled in all envs for now — flip to is_prod if it's annoying in dev

app.include_router(events.router, prefix="/v1", tags=["events"])
app.include_router(score.router, prefix="/v1", tags=["score"])
app.include_router(friction.router, prefix="/v1", tags=["friction"])
app.include_router(cases.router, prefix="/v1", tags=["cases"])
app.include_router(settings.router, prefix="/v1", tags=["settings"])

app.add_route("/metrics", metrics_endpoint, methods=["GET"])


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "allgreen-fraud", "docs": "/docs"}
