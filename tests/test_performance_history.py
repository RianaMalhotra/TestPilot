from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_performance_trends_and_regressions():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        for commit, latency in [("first", 100), ("second", 150), ("third", 120)]:
            result = client.post("/performance/samples", json={
                "commit_sha": commit, "branch": "main", "method": "GET",
                "route": "/health", "p95_ms": latency, "sample_count": 20
            })
            assert result.status_code == 201, result.text
        trends = client.get("/performance/trends?route=/health")
        assert trends.status_code == 200
        assert [item["p95_ms"] for item in trends.json()] == [100, 150, 120]
        regressions = client.get("/performance/regressions?threshold_pct=20")
        assert regressions.status_code == 200
        assert len(regressions.json()) == 1
        assert regressions.json()[0]["increase_pct"] == 50


def test_rejects_invalid_performance_samples():
    with TestClient(app) as client:
        response = client.post("/performance/samples", json={
            "commit_sha": "abc", "method": "GET", "route": "/health",
            "p95_ms": -1, "sample_count": 0
        })
        assert response.status_code == 422
