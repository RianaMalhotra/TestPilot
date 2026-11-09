"""Run a self-contained TestPilot demo against an isolated temporary SQLite database.

No production data or existing local database is modified.
"""
import json
import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def main():
    with tempfile.TemporaryDirectory(prefix="testpilot-demo-") as directory:
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(directory) / "demo.db")
        os.environ.pop("TESTPILOT_REQUIRE_MIGRATIONS", None)
        os.environ.pop("TESTPILOT_REQUIRE_AUTH", None)
        os.environ.pop("TESTPILOT_API_KEY", None)
        from app.main import app

        with TestClient(app) as client:
            for sha, passed, duration in [
                ("a1b2c3", True, 12),
                ("d4e5f6", False, 15),
            ]:
                response = client.post("/runs", json={
                    "commit_sha": sha,
                    "branch": "demo",
                    "results": [{
                        "test_name": "tests/test_checkout.py::test_payment",
                        "passed": passed,
                        "duration_ms": duration,
                        "error_message": None if passed else "AssertionError",
                    }],
                })
                response.raise_for_status()

            for title, path in [
                ("Branch regressions", "/analytics/branch-regressions?branch=demo"),
                ("Rerun recommendations", "/recommendations/rerun"),
                ("Same-commit flakiness classification", "/analytics/flakiness"),
            ]:
                response = client.get(path)
                response.raise_for_status()
                print("\\n" + title)
                print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
