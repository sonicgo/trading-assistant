from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.freeze import router


def test_freeze_router_imports_and_mounts():
    app = FastAPI()
    app.include_router(router, prefix="/test")
    client = TestClient(app)
    response = client.get("/test/unused-endpoint")
    assert response.status_code in (404, 405)
