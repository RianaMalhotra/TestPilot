import logging
from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_metrics_and_request_ids(monkeypatch, caplog):
    monkeypatch.setenv("TESTPILOT_API_KEY", "metrics-secret")
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with caplog.at_level(logging.INFO, logger="testpilot.requests"):
            response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID")
        assert '"event": "http_request"' in caplog.text
        assert client.get("/metrics").status_code == 401
        metrics = client.get("/metrics", headers={
            "X-API-Key": "metrics-secret"
        })
        assert metrics.status_code == 200
        assert any(item["route"] == "/health" for item in metrics.json()["requests"])
