import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.endpoints import auth, registry, portfolios, market_data, alerts, freeze, notifications, ledger, snapshots, ledger_import, engine, recommendations, dashboard
from app.services.scheduler import init_scheduler, start_scheduler, shutdown_scheduler, register_weekly_retention_job
from app.services.jobs.retention import cleanup_old_logs

# Track if this is the primary worker (single-worker guard)
_scheduler_initialized = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    
    Handles scheduler initialization and shutdown.
    Only initializes scheduler in single-worker environments to prevent
    duplicate APScheduler executions.
    """
    global _scheduler_initialized
    
    # Check if we should run scheduler (single-worker or explicit flag)
    # Gunicorn sets WORKERS_COUNT; uvicorn single worker doesn't
    workers_count = int(os.environ.get("WORKERS_COUNT", "1"))
    is_primary = os.environ.get("PRIMARY_WORKER", "true").lower() == "true"
    
    if workers_count == 1 and is_primary and not _scheduler_initialized:
        init_scheduler()
        register_weekly_retention_job(cleanup_old_logs)
        start_scheduler()
        _scheduler_initialized = True
        print("Scheduler initialized (single-worker mode)")
    else:
        if workers_count > 1:
            print(f"Scheduler disabled: multi-worker environment ({workers_count} workers)")
        else:
            print("Scheduler already initialized in another process")
    
    yield
    
    # Shutdown
    if _scheduler_initialized:
        shutdown_scheduler(wait=True)
        _scheduler_initialized = False
        print("Scheduler shut down")


# 1. Initialize the FastAPI app with lifespan
app = FastAPI(
    title="Trading Assistant",
    redirect_slashes=False,
    lifespan=lifespan
)

# 2. Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://172.16.17.73:3000",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 3. Include all Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(registry.router, prefix=f"{settings.API_V1_STR}/registry", tags=["registry"])
app.include_router(portfolios.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["portfolios"])

# Phase 2 API endpoints (market-data, alerts, freeze are portfolio-scoped)
app.include_router(market_data.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["market-data"])
app.include_router(alerts.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["alerts"])
app.include_router(freeze.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["freeze"])

# Phase 2 API endpoints (notifications is user-scoped, NOT portfolio-scoped)
app.include_router(notifications.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["notifications"])

# Phase 3 API endpoints (Book of Record / Ledger)
app.include_router(ledger.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["ledger"])
app.include_router(snapshots.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["snapshots"])
app.include_router(ledger_import.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["ledger-import"])

# Phase 4 API endpoints (Calculation Engine)
app.include_router(engine.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["engine"])

# Phase 5 API endpoints (Recommendation Execution)
app.include_router(recommendations.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["recommendations"])

# Phase 6 API endpoints (Dashboard)
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/portfolios", tags=["dashboard"])


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    """Readiness probe for orchestrators."""
    return {"status": "ready"}
