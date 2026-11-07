"""Run pytest repeatedly at the current checkout and produce JUnit reports.

Run from a trusted repository checkout. Test code is executable code.
Example:
  python -m scripts.rerun_tests --count 3 --output-dir rerun-reports
"""
import argparse
from pathlib import Path
import subprocess
import sys
import subprocess as sp
import httpx


def rerun_tests(count: int, output_dir: Path, pytest_args=()):
    if not 1 <= count <= 20:
        raise ValueError("count must be between 1 and 20")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index in range(1, count + 1):
        report = output_dir / f"rerun-{index}.xml"
        command = [
            sys.executable, "-m", "pytest",
            *pytest_args, f"--junitxml={report}",
        ]
        completed = subprocess.run(command, check=False)
        results.append({
            "attempt": index,
            "exit_code": completed.returncode,
            "report": str(report),
        })
    return results


def upload_reports(results, api, commit_sha, branch="main"):
    """Upload generated JUnit XML files to a running TestPilot API."""
    if not commit_sha or not branch:
        raise ValueError("commit SHA and branch are required")
    uploaded = []
    with httpx.Client(timeout=30) as client:
        for result in results:
            report = Path(result["report"])
            with report.open("rb") as stream:
                response = client.post(
                    f"{api.rstrip('/')}/runs/junit",
                    data={"commit_sha": commit_sha, "branch": branch},
                    files={"file": ("report.xml", stream, "application/xml")},
                )
            response.raise_for_status()
            uploaded.append(response.json())
    return uploaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--output-dir", default="rerun-reports")
    parser.add_argument("pytest_args", nargs="*")
    parser.add_argument("--upload-api", help="Running TestPilot API URL")
    parser.add_argument("--commit-sha", help="Commit SHA (defaults to current Git HEAD)")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    results = rerun_tests(args.count, Path(args.output_dir), args.pytest_args)
    for result in results:
        print(result)
    if args.upload_api:
        sha = args.commit_sha or sp.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        for imported in upload_reports(results, args.upload_api, sha, args.branch):
            print("Imported:", imported)


if __name__ == "__main__":
    main()
