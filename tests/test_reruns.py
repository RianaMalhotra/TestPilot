from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app, Base, engine
from scripts.rerun_tests import rerun_tests


def test_rerun_invokes_pytest_multiple_times(tmp_path):
    with patch("scripts.rerun_tests.subprocess.run") as run:
        run.return_value.returncode = 0
        results = rerun_tests(3, tmp_path, ["tests/test_api.py"])
    assert len(results) == 3
    assert run.call_count == 3
    assert all("--junitxml=" in " ".join(call.args[0]) for call in run.call_args_list)


def test_invalid_rerun_count(tmp_path):
    with pytest.raises(ValueError):
        rerun_tests(21, tmp_path)


def test_branch_regressions_are_isolated():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        for branch, sha, passed in [
            ("main", "a", True),
            ("feature", "b", False),
            ("main", "c", False),
        ]:
            response = client.post("/runs", json={
                "branch": branch, "commit_sha": sha,
                "results": [{"test_name": "test_x", "passed": passed, "duration_ms": 1}],
            })
            assert response.status_code == 201
        assert len(client.get("/analytics/branch-regressions?branch=main").json()) == 1
        assert client.get("/analytics/branch-regressions?branch=feature").json() == []
