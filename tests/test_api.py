import os

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ingestion_and_analytics():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        def submit(sha, passed):
            response = client.post(
                "/runs",
                json={
                    "commit_sha": sha,
                    "results": [
                        {
                            "test_name": "tests/test_login.py::test_login",
                            "passed": passed,
                            "duration_ms": 12.5,
                        }
                    ],
                },
            )
            assert response.status_code == 201

        submit("abc123", True)
        submit("def456", False)
        stats = client.get("/analytics/tests").json()[0]
        assert stats["failure_rate"] == 0.5
        assert stats["flaky"] is True
        assert len(client.get("/analytics/regressions").json()) == 1
        assert client.get("/recommendations/rerun").json()[0]["priority_score"] == 45.0
        assert client.get("/runs/999").status_code == 404


def test_duplicate_names_rejected():
    with TestClient(app) as client:
        item = {"test_name": "same", "passed": True, "duration_ms": 1}
        assert client.post(
            "/runs", json={"commit_sha": "abc", "results": [item, item]}
        ).status_code == 422
