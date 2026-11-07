from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_same_commit_flakiness_classification():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        for sha, values in [
            ("commit-a", {"flaky": True, "regression": True, "stable": True}),
            ("commit-a", {"flaky": False, "stable": True}),
            ("commit-b", {"regression": False}),
        ]:
            response = client.post("/runs", json={
                "commit_sha": sha,
                "results": [
                    {"test_name": name, "passed": passed, "duration_ms": 1}
                    for name, passed in values.items()
                ],
            })
            assert response.status_code == 201, response.text

        report = {
            item["test_name"]: item
            for item in client.get("/analytics/flakiness").json()
        }
        assert report["flaky"]["classification"] == "confirmed_inconsistent"
        assert report["flaky"]["inconsistent_commits"] == ["commit-a"]
        assert report["regression"]["classification"] == "insufficient_same_commit_data"
        assert report["regression"]["inconsistent_commits"] == []
        assert report["stable"]["classification"] == "no_inconsistency_observed"


def test_flakiness_empty_database():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        assert client.get("/analytics/flakiness").json() == []
