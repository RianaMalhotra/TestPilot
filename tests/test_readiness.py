import pytest
from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_analytics_auth_when_key_configured(monkeypatch):
    monkeypatch.setenv("TESTPILOT_API_KEY", "private-key")
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        assert client.get("/analytics/summary").status_code == 401
        assert client.get("/analytics/summary", headers={
            "X-API-Key": "private-key"
        }).status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200


def test_secure_mode_requires_key(monkeypatch):
    monkeypatch.setenv("TESTPILOT_REQUIRE_AUTH", "1")
    monkeypatch.delenv("TESTPILOT_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TESTPILOT_API_KEY"):
        with TestClient(app):
            pass
