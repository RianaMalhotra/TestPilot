# TestPilot

A backend test intelligence platform that analyzes CI test results, detects flaky tests and regressions, tracks failure patterns, and prioritizes test reruns to improve software reliability.

## Features

- Ingest test execution results into a SQLite database via a REST API.
- Track test execution history, failure rates, average runtimes, and status transitions.
- Detect pass-to-fail regressions and rank tests for rerun using a transparent heuristic.
- Automatically test the backend on GitHub Actions.

**Stack:** Python, FastAPI, SQLAlchemy, SQLite, pytest, GitHub Actions.

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
| `GET /health` | Health check |
| `POST /runs` | Record a CI test run |
| `GET /runs/{run_id}` | Retrieve run details |
| `GET /analytics/tests` | Failure rates and status transitions |
| `GET /analytics/regressions` | Detect pass-to-fail changes |
| `GET /recommendations/rerun` | Rank tests for reruns |

The MVP uses a simple transition-based *flakiness heuristic*. An outcome change can also reflect a real code fix or regression; more advanced classification will distinguish these cases.

## Testing

```bash
pytest -q
```

A GitHub Actions workflow runs the tests on pushes and pull requests.

## Roadmap

- Import JUnit XML from pytest and CI pipelines.
- Add build and branch isolation for historical comparisons.
- Classify failure signatures and recurring errors.
- Improve flakiness detection with same-commit reruns.
- Provide GitHub Actions artifact ingestion.

## License

No license has been selected yet.
