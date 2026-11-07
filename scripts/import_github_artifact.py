"""Import a GitHub Actions JUnit artifact into a running TestPilot API.

Usage:
  GITHUB_TOKEN=... python -m scripts.import_github_artifact \\
    --repo RianaMalhotra/TestPilot --run-id 123456 --api http://127.0.0.1:8000
"""
import argparse
from io import BytesIO
import os
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile

import httpx

API_ROOT = "https://api.github.com"
MAX_ARCHIVE = 10 * 1024 * 1024
MAX_XML = 5 * 1024 * 1024


def extract_report(content: bytes) -> bytes:
    if len(content) > MAX_ARCHIVE:
        raise ValueError("Artifact archive exceeds 10 MiB")
    try:
        with ZipFile(BytesIO(content)) as archive:
            candidates = [
                item for item in archive.infolist()
                if not item.is_dir()
                and PurePosixPath(item.filename).name == "report.xml"
            ]
            if len(candidates) != 1:
                raise ValueError("Expected exactly one report.xml")
            item = candidates[0]
            if item.file_size > MAX_XML:
                raise ValueError("JUnit report exceeds 5 MiB")
            with archive.open(item) as stream:
                report = stream.read(MAX_XML + 1)
            if len(report) > MAX_XML:
                raise ValueError("JUnit report exceeds 5 MiB")
            return report
    except BadZipFile as exc:
        raise ValueError("Invalid GitHub artifact ZIP") from exc


def import_run(repo: str, run_id: int, api: str, token: str, artifact_name="testpilot-junit", api_key=None):
    if not token:
        raise ValueError("GITHUB_TOKEN is required")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        run_response = client.get(
            f"{API_ROOT}/repos/{repo}/actions/runs/{run_id}", headers=headers
        )
        run_response.raise_for_status()
        sha = run_response.json()["head_sha"]
        branch = run_response.json().get("head_branch") or "main"
        artifacts_response = client.get(
            f"{API_ROOT}/repos/{repo}/actions/runs/{run_id}/artifacts",
            headers=headers,
            params={"per_page": 100},
        )
        artifacts_response.raise_for_status()
        matches = [
            artifact for artifact in artifacts_response.json()["artifacts"]
            if artifact["name"] == artifact_name and not artifact["expired"]
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one unexpired {artifact_name} artifact")
        archive_response = client.get(
            matches[0]["archive_download_url"], headers=headers
        )
        archive_response.raise_for_status()
        report = extract_report(archive_response.content)
        upload = client.post(
            f"{api.rstrip('/')}/runs/junit",
            data={"commit_sha": sha, "branch": branch,
                  "github_repository": repo, "github_run_id": str(run_id)},
            files={"file": ("report.xml", report, "application/xml")},
            headers={"X-API-Key": api_key} if api_key else {},
        )
        upload.raise_for_status()
        return upload.json()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repo")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(import_run(args.repo, args.run_id, args.api, os.getenv("GITHUB_TOKEN", ""),
                     api_key=os.getenv("TESTPILOT_API_KEY")))


if __name__ == "__main__":
    main()
