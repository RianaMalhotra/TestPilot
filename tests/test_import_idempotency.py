from fastapi.testclient import TestClient
from app.main import app, Base, engine


XML = b'<testsuite><testcase name="example" time="0.01"/></testsuite>'


def test_github_import_is_idempotent():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        args = {
            "data": {
                "commit_sha": "abc123", "branch": "main",
                "github_repository": "owner/repo", "github_run_id": "42",
            },
            "files": {"file": ("report.xml", XML, "application/xml")},
        }
        first = client.post("/runs/junit", **args)
        second = client.post("/runs/junit", **args)
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["already_imported"] is False
        assert second.json()["already_imported"] is True
        assert first.json()["run_id"] == second.json()["run_id"]
        assert client.get("/analytics/summary").json()["runs"] == 1


def test_github_import_requires_both_identifiers():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        result = client.post("/runs/junit", data={
            "commit_sha": "abc123", "github_run_id": "42",
        }, files={"file": ("report.xml", XML, "application/xml")})
        assert result.status_code == 422
