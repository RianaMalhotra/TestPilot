# TestPilot

**Automated CI test intelligence and performance regression detection**

TestPilot is a backend-first platform that ingests pytest/JUnit results, tracks test reliability across commits, detects regressions and flaky outcomes, and recommends which tests to rerun. It also records API latency measurements and compares p95 performance across builds.

**Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL/SQLite · pytest · GitHub Actions**

## Why I built it

CI pipelines can tell you **that a test failed**, but they don't always explain whether the failure is new, recurring, or inconsistent. When a suite grows, manually comparing reports across commits and deciding which tests to rerun becomes time-consuming.

I built TestPilot to turn individual CI test reports into a searchable history of software reliability. The goal is to help developers answer three practical questions: **What broke? Has it happened before? What should I investigate or rerun first?**

## What it does

TestPilot is a backend API for analyzing automated test results and spotting changes in software quality over time.

- **Tracks test reliability:** Records pass/fail results, execution times, failure rates, and trends across commits and branches.
- **Detects functional regressions:** Identifies tests that previously passed but now fail.
- **Investigates flaky tests:** Looks for inconsistent outcomes when the same test is executed repeatedly on the **same commit**.
- **Groups recurring failures:** Clusters failures using normalized error-message signatures to make repeated issues easier to recognize.
- **Recommends reruns:** Ranks tests using an explainable heuristic so developers can focus on the most useful next checks.
- **Monitors API performance:** Records p95 latency by commit and flags slowdowns relative to previous measurements.
- **Supports CI workflows:** Imports JUnit XML reports from GitHub Actions and produces local API benchmark artifacts.

TestPilot is intentionally **backend-first**: its outputs are available through REST endpoints and interactive FastAPI documentation rather than a custom dashboard.

## How it works

1. **Collect:** pytest generates a JUnit XML report in GitHub Actions. An importer can retrieve the artifact and send it to TestPilot, or a developer can submit JUnit XML or JSON directly.
2. **Store:** FastAPI validates the incoming data, then SQLAlchemy persists runs, individual test outcomes, commit/branch metadata, and performance samples in SQLite or PostgreSQL. GitHub imports are deduplicated using repository and workflow-run identifiers.
3. **Analyze:** API endpoints compare historical outcomes to calculate failure trends, identify pass-to-fail regressions, classify same-commit inconsistency, and group similar error messages.
4. **Prioritize:** A transparent rerun recommendation heuristic surfaces tests worth investigating. Performance endpoints compare recorded p95 latency samples across commits.
5. **Observe:** Structured request logs, request IDs, slow-request warnings, and process-local metrics help diagnose API behavior.

### System architecture

```mermaid
flowchart LR
    A["pytest / GitHub Actions"] -->|"JUnit report"| B["Artifact importer"]
    D["Manual JSON / XML upload"] --> C["FastAPI REST API"]
    B --> C
    C --> E[("SQLite / PostgreSQL")]
    E --> F["Test history and failure analysis"]
    E --> G["Flakiness and regression detection"]
    E --> H["Rerun recommendations"]
    I["CI API smoke benchmark"] -->|"JSON artifact"| J["Optional performance sample upload"]
    J --> C
    E --> K["Latency trends and slowdown detection"]
    C --> L["Structured logs and request metrics"]
```

**Tech stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/SQLite, pytest, httpx, GitHub Actions, and Render deployment configuration.

**Important distinction:** GitHub Actions produces the performance benchmark report, but it is not automatically imported into the historical performance database. The scheduled JUnit importer also requires a deployed, reachable API and configured credentials.

## Run locally

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate    # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive API documentation.

```bash
# Separate terminal: ingest a test run
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"commit_sha":"demo123","branch":"main","results":[{"test_name":"tests/test_login.py::test_login","passed":false,"duration_ms":12.5,"error_message":"AssertionError"}]}'

# Inspect analytics
curl http://127.0.0.1:8000/analytics/summary
```

If `TESTPILOT_API_KEY` is set, supply `-H "X-API-Key: YOUR_KEY"` on protected requests.

## Demo walkthrough

The integration test provides a deterministic demo of the complete pipeline without requiring external services:

```bash
python -m pytest -q tests/test_integration_e2e.py
python -m scripts.validate_deployment
python -m scripts.benchmark_api
```

For a guided demonstration, show these endpoints in `/docs`:

1. `POST /runs/junit` — import a JUnit report with a commit SHA.
2. `GET /analytics/tests` and `GET /analytics/regressions` — explain test history and regressions.
3. `GET /analytics/flakiness` — compare repeated executions on the same commit.
4. `GET /recommendations/rerun` — inspect test prioritization.
5. `POST /performance/samples` followed by `GET /performance/regressions` — compare p95 measurements.
6. `GET /metrics` — inspect in-process request statistics.

To create a real JUnit report, run `python -m pytest --junitxml=report.xml` and upload it to `POST /runs/junit` as multipart form data with `commit_sha` and `file` fields.

## CI integration

The **Backend CI** workflow runs tests on pushes and pull requests, uploads `testpilot-junit`, and runs a 100-request local benchmark after tests pass, uploading `testpilot-performance`. Both artifacts are retained for 14 days.

For manual ingestion, set `GITHUB_TOKEN` with Actions read permission, then run:

```bash
python -m scripts.import_github_artifact --repo RianaMalhotra/TestPilot --run-id YOUR_RUN_ID
```

The `Import CI Reports` workflow can poll every six hours. To activate it, configure repository variable `TESTPILOT_API_URL` with your **deployed HTTPS backend** and secret `TESTPILOT_API_KEY` matching the backend. Until configured, scheduled ingestion cannot reach a server. The poller skips workflows other than `Backend CI`; persistent database deduplication prevents duplicate imports.

## Deployment and security

`render.yaml` describes a Render Python web service and managed PostgreSQL database. It runs `alembic upgrade head` before startup and checks `GET /ready`. **No production deployment has been created or verified by this repository.** Review hosting costs before applying the Blueprint.

Set `TESTPILOT_REQUIRE_AUTH=1` and a strong `TESTPILOT_API_KEY` in production. The key protects ingestion, analytics, run details, performance endpoints, and metrics. `/health` and `/ready` are public. `TESTPILOT_REQUIRE_MIGRATIONS=1` enforces the expected Alembic revision in readiness checks. `TESTPILOT_SLOW_REQUEST_MS` sets the slow-request logging threshold (default 1000 ms).

SQLite is suitable for local development; PostgreSQL is intended for persistent hosting. The API uses `create_all` for development convenience; run Alembic migrations before production startup. If upgrading an existing unversioned SQLite database, back it up and reconcile its schema before stamping or migrating.

## Technical notes and limitations

- Same-commit inconsistency is evidence of flakiness, not proof of the underlying cause.
- Failure clustering uses normalized first-line error signatures, not semantic embeddings.
- Latency regression comparisons use the preceding recorded sample for each branch/method/route when the commit changes; they do not account for statistical variance or machine differences.
- The CI benchmark measures an **in-process test client**, not deployed network performance. CI runner contention can change measurements.
- `GET /metrics` uses process-local counters and the latest 500 latency samples per route; statistics reset on restart and are not aggregated across workers.
- GitHub artifact polling uses local state for efficiency and persistent database deduplication for correctness. The state file is not shared between CI runners.
- There is no deployed UI; this is intentionally a backend/API project.

## Validation

```bash
python -m pytest -q
python -m scripts.validate_deployment
```

GitHub Actions provides the current CI result in the [Actions tab](https://github.com/RianaMalhotra/TestPilot/actions).

## Resume-ready description

**TestPilot — CI Test Intelligence & Regression Analytics | Python, FastAPI, PostgreSQL, pytest, GitHub Actions**

Built a backend platform to ingest and deduplicate CI/JUnit test reports, analyze historical test failures and same-commit flakiness, detect functional and API latency regressions, and prioritize reruns. Implemented authenticated REST APIs, Alembic migrations, structured observability, GitHub Actions artifact ingestion, and automated integration/benchmark tests.
