from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_failure_clustering_and_trends():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        for sha, name, passed, message in [
            ("a", "test_one", False, "Timeout after 10 seconds"),
            ("b", "test_two", False, "Timeout after 30 seconds"),
            ("c", "test_one", True, None),
        ]:
            response = client.post("/runs", json={
                "commit_sha": sha,
                "results": [{
                    "test_name": name,
                    "passed": passed,
                    "duration_ms": 1.0,
                    "error_message": message,
                }],
            })
            assert response.status_code == 201, response.text
        clusters = client.get("/analytics/failure-clusters").json()
        assert len(clusters) == 1
        assert clusters[0]["signature"] == "Timeout after <num> seconds"
        assert clusters[0]["occurrences"] == 2
        assert clusters[0]["affected_tests"] == ["test_one", "test_two"]
        trends = client.get("/analytics/trends").json()
        assert [r["pass_rate"] for r in trends] == [0.0, 0.0, 1.0]
        summary = client.get("/analytics/summary").json()
        assert summary["runs"] == 3
        assert summary["executions"] == 3
        assert summary["failure_clusters"] == 1
        assert summary["tests_with_status_changes"] == 1


def test_empty_analytics():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        assert client.get("/analytics/trends").json() == []
        assert client.get("/analytics/failure-clusters").json() == []
        assert client.get("/analytics/summary").json()["overall_pass_rate"] is None
