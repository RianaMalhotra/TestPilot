import json
import logging
from fastapi.testclient import TestClient
from app.main import app


def test_latency_metrics_and_slow_request_log(monkeypatch, caplog):
    monkeypatch.setenv("TESTPILOT_SLOW_REQUEST_MS", "0")
    monkeypatch.setenv("TESTPILOT_API_KEY", "monitoring-key")
    with TestClient(app) as client:
        with caplog.at_level(logging.INFO, logger="testpilot.requests"):
            response = client.get("/health")
        assert response.status_code == 200
        entries = [json.loads(record.message) for record in caplog.records
                   if record.name == "testpilot.requests"]
        assert any(entry["event"] == "slow_request" for entry in entries)
        result = client.get("/metrics", headers={"X-API-Key": "monitoring-key"})
        assert result.status_code == 200
        samples = [item for item in result.json()["latency"]
                   if item["method"] == "GET" and item["route"] == "/health"]
        assert samples
        assert samples[0]["samples"] >= 1
        assert samples[0]["p95_ms"] >= 0
