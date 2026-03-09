"""Test script to verify FastAPI OpenAPI schema generation."""
import sys
sys.path.insert(0, '/home/lei-dev/projects/trading-assistant/backend')

from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.openapi.utils import get_openapi

# Minimal app to test
app = APIRouter()

# Simple dependency
def get_db():
    yield "db"

SessionDep = Annotated[str, Depends(get_db)]

def get_current_user():
    return "user"

CurrentUser = Annotated[str, Depends(get_current_user)]

@app.post("/{portfolio_id}/market-data/refresh")
def refresh_market_data(
    portfolio_id: str,
    current_user: CurrentUser,
    db: SessionDep,
):
    return {"job_id": "test"}

# Generate OpenAPI schema
schema = get_openapi(
    title="Test API",
    version="1.0.0",
    routes=[app.routes[0]],
)

# Check for args/kwargs in parameters
refresh_endpoint = schema.get('paths', {}).get('/{portfolio_id}/market-data/refresh', {}).get('post', {})
params = refresh_endpoint.get('parameters', [])

print("Parameters for refresh endpoint:")
for param in params:
    print(f"  - {param.get('name')}: {param.get('in')}")

# Check if args or kwargs are present
param_names = [p.get('name') for p in params]
if 'args' in param_names or 'kwargs' in param_names:
    print("\n❌ ERROR: Found args or kwargs in parameters!")
    sys.exit(1)
else:
    print("\n✓ OK: No args or kwargs in parameters")
    sys.exit(0)
