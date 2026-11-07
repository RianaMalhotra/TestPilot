"""Poll completed GitHub Actions runs and import unseen JUnit artifacts.

State is persisted locally; schedule this command externally for continuous polling.
"""
import argparse
import json
import os
from pathlib import Path

import httpx

from scripts.import_github_artifact import import_run

API_ROOT = "https://api.github.com"


def poll(repo, api, token, state_path, limit=20, importer=import_run, api_key=None):
    if not token:
        raise ValueError("GITHUB_TOKEN is required")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    state_path = Path(state_path)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    processed = set(state.get(repo, []))
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"{API_ROOT}/repos/{repo}/actions/runs",
            headers=headers,
            params={"status": "completed", "per_page": limit},
        )
        response.raise_for_status()
        runs = response.json()["workflow_runs"]
    imported = []
    # Oldest first to preserve chronology in TestPilot.
    for run in reversed(runs):
        # Other workflows (including the importer) do not upload JUnit artifacts.
        if run.get("name", "Backend CI") != "Backend CI":
            continue
        run_id = run["id"]
        if run_id in processed:
            continue
        try:
            result = importer(repo, run_id, api, token) if api_key is None else importer(
                repo, run_id, api, token, api_key=api_key
            )
        except (ValueError, httpx.HTTPError) as exc:
            # Keep failed imports retryable; report failures to the caller.
            raise RuntimeError(f"Failed to import GitHub run {run_id}: {exc}") from exc
        processed.add(run_id)
        state[repo] = sorted(processed)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = state_path.with_suffix(state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(state_path)
        imported.append({"github_run_id": run_id, "testpilot": result})
    return imported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--state", default=".testpilot-poll-state.json")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    for item in poll(args.repo, args.api, os.getenv("GITHUB_TOKEN", ""), args.state, args.limit,
                     api_key=os.getenv("TESTPILOT_API_KEY")):
        print(item)


if __name__ == "__main__":
    main()
