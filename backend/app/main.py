from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.endpoints import auth, registry, portfolios

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

@app.get("/health")
def health_check():
    return {"status": "ok"}