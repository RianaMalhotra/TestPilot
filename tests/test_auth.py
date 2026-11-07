import pytest
from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_write_endpoints_require_api_key(monkeypatch):
    monkeypatch.setenv("TESTPILOT_API_KEY", "secret-value")
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        payload = {"commit_sha": "abc", "results": [
            {"test_name": "test_one", "passed": True, "duration_ms": 1}
        ]}
        assert client.post("/runs", json=payload).status_code == 401
        assert client.post("/runs", json=payload,
                           headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.post("/runs", json=payload,
                           headers={"X-API-Key": "secret-value"}).status_code == 201
        assert client.post("/runs/junit", data={"commit_sha": "abc"},
                           files={"file": ("report.xml", b"<testsuite/>")}).status_code == 401
        assert client.get("/health").status_code == 200
