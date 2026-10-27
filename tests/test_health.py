from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_simple_health_and_dashboard_head():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.head("/dashboard/").status_code == 200
