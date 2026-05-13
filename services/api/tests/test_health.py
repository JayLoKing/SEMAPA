"""Tests básicos del API."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    """Endpoint /health debe responder 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi():
    """Schema OpenAPI debe estar disponible."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()
