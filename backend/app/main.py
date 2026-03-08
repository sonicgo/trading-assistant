from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.endpoints import auth, registry, portfolios, market_data, alerts, freeze, notifications

# 1. Initialize the FastAPI app first
app = FastAPI(
    title="Trading Assistant",
    # This prevents the 307/308 redirect behavior globally
    redirect_slashes=False 
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

@app.get("/health")
def health_check():
    return {"status": "ok"}
