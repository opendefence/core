"""Test the REST API"""

from fastapi.testclient import TestClient

from opendefence_core.api.app import app


def test_health() -> None:
    """Health check answers ok"""
    client = TestClient(app)
    response = client.get("/api/v3/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
