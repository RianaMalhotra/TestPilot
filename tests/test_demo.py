"""Smoke test the isolated demo as a subprocess."""
import subprocess
import sys


def test_demo_runs_and_explains_regression():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.demo"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "Branch regressions" in result.stdout
    assert "Rerun recommendations" in result.stdout
    assert "test_payment" in result.stdout
    assert '"priority_score": 45.0' in result.stdout
