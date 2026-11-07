# TestPilot

A backend test intelligence platform that analyzes CI test results, detects flaky tests and regressions, tracks failure patterns, and prioritizes test reruns to improve software reliability.

## Features

- Ingest JSON results or JUnit XML reports from pytest/CI into SQLite via a REST API.
- Track test execution history, failure rates, average runtimes, status transitions, and per-run trends.
- Record branch metadata and detect pass-to-fail changes within a selected branch.
- Cluster recurring failures using normalized error-message signatures.
- Detect pass-to-fail regressions and rank tests for rerun using a transparent heuristic.
- Automatically test the backend on GitHub Actions.

**Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, GitHub Actions.

## Production deployment

A Render Blueprint (`render.yaml`) defines a Python web service and managed PostgreSQL database. It uses `alembic upgrade head` before deployment, starts Uvicorn, and checks `/ready`. Review hosting costs and service availability before applying the Blueprint. This repository does **not** provision a deployment automatically.

For any public deployment, set `TESTPILOT_REQUIRE_AUTH=1` and a strong `TESTPILOT_API_KEY`. When the key is set, the API requires `X-API-Key` for ingestion, analytics, recommendations, and individual run retrieval. `/health` and `/ready` remain public for monitoring. Set `TESTPILOT_REQUIRE_MIGRATIONS=1` to require the latest Alembic revision in the readiness check.

PostgreSQL uses the psycopg 3 driver. Validate the Render plan, database connection, and migration lifecycle before production use. Do not store secrets in source control.

## Quick start

Requires Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000/docs to explore the interactive API documentation.

## Example: submit a run

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"commit_sha":"abc123","results":[{"test_name":"tests/test_login.py::test_login","passed":false,"duration_ms":12.5,"error_message":"AssertionError"}]}'
```

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process health check |
| `GET /ready` | Database readiness check |
| `POST /runs` | Record a CI test run as JSON |
| `POST /runs/junit` | Upload JUnit XML (multipart form) |
| `GET /runs/{run_id}` | Retrieve run details |
| `GET /analytics/tests` | Failure rates and status transitions |
| `GET /analytics/regressions` | Detect pass-to-fail changes |
| `GET /recommendations/rerun` | Rank tests for reruns |
| `GET /analytics/failure-clusters` | Group similar failure messages |
| `GET /analytics/trends` | View per-run pass rates |
| `GET /analytics/summary` | View overall reliability statistics |
| `GET /analytics/flakiness` | Classify inconsistent outcomes on identical commits |
| `GET /analytics/branch-regressions?branch=main` | Detect regressions within one branch |

Failure clusters use first-line message normalization (numbers and hexadecimal addresses), not semantic similarity. The original `/analytics/tests` endpoint retains a simple transition-based *flakiness heuristic*. The dedicated `/analytics/flakiness` endpoint instead requires repeated executions on the same commit to identify inconsistent outcomes. An outcome change can also reflect a real code fix or regression; more advanced classification will distinguish these cases.

## Import a real pytest report

Generate a JUnit report:

```bash
python -m pytest --junitxml=report.xml
```

With the API running, import it:

```bash
curl -X POST http://127.0.0.1:8000/runs/junit -F 'commit_sha=abc123' -F 'file=@report.xml'
```

Skipped testcases are excluded; failed/error testcases are recorded as failures. Maximum upload size is 5 MiB. This MVP imports reports manually; automatic CI artifact ingestion is a future milestone.

## GitHub Actions artifact integration

The CI workflow generates `report.xml` and uploads it as the `testpilot-junit` artifact, even if tests fail. To ingest a completed workflow run into a locally running TestPilot server:

```bash
export GITHUB_TOKEN=your_github_token
python -m scripts.import_github_artifact --repo RianaMalhotra/TestPilot --run-id YOUR_RUN_ID
```

On Windows PowerShell, set the token with `$env:GITHUB_TOKEN="..."`. The token must have permission to read Actions artifacts (for private repositories, Actions: read). Never commit tokens. The importer retrieves the run's commit SHA, downloads its JUnit artifact, validates the archive, and submits the XML to the backend. This is a **manual command**, not a background webhook or scheduled ingestion service. Artifact retention is 14 days.

## API authentication and scheduled ingestion

Set `TESTPILOT_API_KEY` on the TestPilot backend to require an `X-API-Key` header for `POST /runs` and `POST /runs/junit`. If the variable is unset, writes remain unauthenticated for local development; **set it in any public deployment**. Analytics endpoints and run details require the same key when configured; health and readiness checks remain public.

The `Import CI Reports` GitHub Actions workflow runs every six hours (or manually). To enable it, configure repository variable `TESTPILOT_API_URL` with your deployed HTTPS backend URL and secret `TESTPILOT_API_KEY` with the same key configured on the backend. The workflow does nothing until the URL variable is configured. GitHub-hosted runners cannot reach a backend running only on localhost.

## Poll GitHub Actions artifacts

Poll the most recent completed workflow runs and ingest their JUnit artifacts into a running TestPilot API:

```bash
export GITHUB_TOKEN=your_github_token
python -m scripts.poll_github_artifacts --repo RianaMalhotra/TestPilot --api http://127.0.0.1:8000
```

The API now records GitHub repository and workflow run ID in a unique database table, making repeated imports idempotent even if the local state file is lost. The poller also remembers successfully imported run IDs in `.testpilot-poll-state.json` to avoid unnecessary downloads. Failed imports remain retryable. Schedule the command externally (cron, Task Scheduler, or a persistent worker) for ongoing ingestion. It does not run continuously on its own. The state file is local, not shared across machines; concurrent pollers may repeat network requests, but the API deduplicates imports by repository and workflow run ID. Only runs among the latest 20 completed runs (configurable with `--limit`) are examined per poll. The GitHub token must have Actions read access to the repository.

## Repeat test executions

Run pytest three times on the same checkout to generate separate JUnit reports:

```bash
python -m scripts.rerun_tests --count 3 --output-dir rerun-reports
```

Use `--count` from 1 to 20. Each execution creates a separate `rerun-N.xml` file. To automatically upload each generated report to a running TestPilot API:

```bash
python -m scripts.rerun_tests --count 3 --upload-api http://127.0.0.1:8000 --branch main
```

The command uses the current Git HEAD unless you specify `--commit-sha`. All reruns are recorded against the same commit and branch. The API must be running locally first. The command runs local test code, so only use trusted checkouts.

**Versioned database migrations (Alembic):** For a new database, run `alembic upgrade head` before starting the API. Run `alembic upgrade head` to apply the initial schema and the GitHub import-tracking revision. For an existing database that already has both `runs.branch` and `results`, use `alembic stamp head` once after backing up the database. For a legacy database without `runs.branch`, start the earlier compatibility version of TestPilot once to add the column before stamping, or migrate the column manually. **Do not run `alembic upgrade head` against an existing unversioned database**; it will attempt to recreate existing tables. The API retains `create_all` for development convenience, but production deployments should migrate before startup.

## Testing

```bash
pytest -q
```

A GitHub Actions workflow runs the tests on pushes and pull requests.

## Roadmap

- Import JUnit XML artifacts from GitHub Actions using the GitHub API.
- Add build and branch isolation for historical comparisons.
- Improve failure clustering with stack-trace-aware signatures and similarity scoring.
- Add follow-up Alembic revisions for future schema changes.
- Add authenticated analytics access, rate limits, and production monitoring.
