"""End-to-end API workflow with authenticated ingestion and persisted analytics."""
from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_authenticated_junit_to_analytics_and_performance(monkeypatch):
    monkeypatch.setenv("TESTPILOT_API_KEY", "integration-key")
    headers = {"X-API-Key": "integration-key"}
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/analytics/tests").status_code == 401

        for sha, failure, latency in [("commit-a", False, 40), ("commit-b", True, 70)]:
            xml = ('<testsuite><testcase classname="suite" name="check" time="0.01">'
                   + ('<failure message="regression">failed</failure>' if failure else '')
                   + '</testcase></testsuite>')
            response = client.post(
                "/runs/junit", headers=headers,
                data={"commit_sha": sha, "branch": "main"},
                files={"file": ("report.xml", xml, "application/xml")},
            )
            assert response.status_code == 201, response.text
            assert client.get(f'/runs/{response.json()["run_id"]}', headers=headers).status_code == 200
            measurement = client.post("/performance/samples", headers=headers, json={
                "commit_sha": sha, "branch": "main", "method": "GET",
                "route": "/health", "p95_ms": latency, "sample_count": 50,
            })
            assert measurement.status_code == 201, measurement.text

        analytics = client.get("/analytics/tests", headers=headers)
        assert analytics.status_code == 200
        assert analytics.json()[0]["failure_rate"] == 0.5
        assert client.get("/analytics/regressions", headers=headers).json()
        trends = client.get("/performance/trends", headers=headers)
        assert len(trends.json()) == 2
        regressions = client.get("/performance/regressions", headers=headers).json()
        assert len(regressions) == 1
        assert regressions[0]["increase_pct"] == 75.0
