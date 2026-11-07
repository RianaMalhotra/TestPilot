from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import Depends, FastAPI, HTTPException, File, Form, UploadFile
from defusedxml import ElementTree as SafeET
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./testpilot.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if DATABASE_URL == "sqlite://" else None,
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    commit_sha: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    results: Mapped[list["Result"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    test_name: Mapped[str] = mapped_column(String(500), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    duration_ms: Mapped[float] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    run: Mapped[Run] = relationship(back_populates="results")


class TestResultIn(BaseModel):
    test_name: str = Field(min_length=1, max_length=500)
    passed: bool
    duration_ms: float = Field(ge=0)
    error_message: str | None = Field(default=None, max_length=2000)


class RunIn(BaseModel):
    commit_sha: str = Field(min_length=1, max_length=100)
    results: list[TestResultIn] = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="TestPilot",
    description="Backend test intelligence and regression analytics",
    version="0.1.0",
    lifespan=lifespan,
)


def get_db():
    with SessionLocal() as session:
        yield session


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/runs", status_code=201)
def create_run(payload: RunIn, db: Session = Depends(get_db)):
    names = [r.test_name for r in payload.results]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=422, detail="Duplicate test names in a run")
    run = Run(commit_sha=payload.commit_sha)
    run.results = [Result(**r.model_dump()) for r in payload.results]
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, "tests_recorded": len(run.results)}


@app.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run.id,
        "commit_sha": run.commit_sha,
        "results": [
            {
                "test_name": r.test_name,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
            }
            for r in run.results
        ],
    }


@app.get("/analytics/tests")
def test_analytics(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Result, Run.created_at)
        .join(Run)
        .order_by(Run.created_at, Run.id, Result.id)
    ).all()
    history = {}
    for result, _ in rows:
        history.setdefault(result.test_name, []).append(result)
    output = []
    for name, results in history.items():
        statuses = [r.passed for r in results]
        failures = statuses.count(False)
        transitions = sum(a != b for a, b in zip(statuses, statuses[1:]))
        output.append(
            {
                "test_name": name,
                "executions": len(results),
                "failures": failures,
                "failure_rate": round(failures / len(results), 3),
                "flaky": transitions > 0,
                "status_transitions": transitions,
                "average_duration_ms": round(
                    sum(r.duration_ms for r in results) / len(results), 2
                ),
            }
        )
    return sorted(
        output, key=lambda x: (-x["failure_rate"], -x["status_transitions"], x["test_name"])
    )


@app.get("/analytics/regressions")
def regressions(db: Session = Depends(get_db)):
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    latest = {}
    detected = []
    for run in runs:
        for result in run.results:
            prior = latest.get(result.test_name)
            if prior is not None and prior["passed"] and not result.passed:
                detected.append(
                    {
                        "test_name": result.test_name,
                        "run_id": run.id,
                        "commit_sha": run.commit_sha,
                        "previous_run_id": prior["run_id"],
                    }
                )
            latest[result.test_name] = {"passed": result.passed, "run_id": run.id}
    return detected


@app.get("/recommendations/rerun")
def rerun_recommendations(db: Session = Depends(get_db)):
    analytics = test_analytics(db)
    # Heuristic: frequent failures and changing outcomes increase rerun priority.
    ranked = [
        {
            **item,
            "priority_score": round(
                item["failure_rate"] * 70 + min(item["status_transitions"], 3) * 10, 1
            ),
        }
        for item in analytics
    ]
    return sorted(ranked, key=lambda x: (-x["priority_score"], x["test_name"]))


@app.post("/runs/junit", status_code=201)
async def import_junit(
    file: UploadFile = File(...),
    commit_sha: str = Form(..., min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    """Import JUnit XML from pytest or another CI test runner."""
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=422, detail="Upload a .xml test report")
    # Limit uploads to 5 MiB, even if Content-Length is absent.
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Report exceeds 5 MiB")
    try:
        root = SafeET.fromstring(raw)
    except (SafeET.ParseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid or unsafe JUnit XML") from exc
    if root.tag not in ("testsuite", "testsuites"):
        raise HTTPException(status_code=422, detail="Expected testsuite or testsuites root")

    parsed = []
    seen = set()
    for case in root.iter("testcase"):
        name = case.get("name")
        if not name:
            raise HTTPException(status_code=422, detail="Testcase missing name")
        classname = case.get("classname", "")
        test_name = f"{classname}::{name}" if classname else name
        if test_name in seen or len(test_name) > 500:
            raise HTTPException(status_code=422, detail="Duplicate or oversized test name")
        seen.add(test_name)
        try:
            duration = float(case.get("time", "0")) * 1000
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid testcase duration") from exc
        if not 0 <= duration < float("inf"):
            raise HTTPException(status_code=422, detail="Invalid testcase duration")
        failure = next((child for child in case if child.tag in ("failure", "error")), None)
        skipped = any(child.tag == "skipped" for child in case)
        if skipped:
            continue  # Skipped tests have no pass/fail result.
        message = (failure.get("message") or failure.text or "")[:2000] if failure is not None else None
        parsed.append(Result(test_name=test_name, passed=failure is None,
                             duration_ms=duration, error_message=message))
    if not parsed:
        raise HTTPException(status_code=422, detail="No executed testcases found")
    run = Run(commit_sha=commit_sha, results=parsed)
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, "tests_recorded": len(parsed), "format": "junit"}


def _failure_signature(message: str | None) -> str:
    """Normalize common volatile details so repeated failures group together."""
    import re

    normalized = (message or "Unknown failure").strip().splitlines()[0][:500]
    normalized = re.sub(r"0x[0-9a-fA-F]+", "<hex>", normalized)
    normalized = re.sub(r"\b\d+\b", "<num>", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or "Unknown failure"


@app.get("/analytics/failure-clusters")
def failure_clusters(db: Session = Depends(get_db)):
    """Group failures by normalized first-line error signatures."""
    rows = db.execute(
        select(Result, Run.commit_sha)
        .join(Run)
        .where(Result.passed.is_(False))
        .order_by(Result.run_id, Result.id)
    ).all()
    clusters = {}
    for result, sha in rows:
        signature = _failure_signature(result.error_message)
        group = clusters.setdefault(signature, {
            "signature": signature,
            "occurrences": 0,
            "affected_tests": set(),
            "commits": set(),
        })
        group["occurrences"] += 1
        group["affected_tests"].add(result.test_name)
        group["commits"].add(sha)
    return sorted(
        [{
            "signature": group["signature"],
            "occurrences": group["occurrences"],
            "affected_tests": sorted(group["affected_tests"]),
            "distinct_commits": len(group["commits"]),
        } for group in clusters.values()],
        key=lambda item: (-item["occurrences"], item["signature"]),
    )


@app.get("/analytics/trends")
def run_trends(db: Session = Depends(get_db)):
    """Per-run pass/fail history in ingestion order."""
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    output = []
    for run in runs:
        total = len(run.results)
        failures = sum(not result.passed for result in run.results)
        output.append({
            "run_id": run.id,
            "commit_sha": run.commit_sha,
            "total": total,
            "passed": total - failures,
            "failed": failures,
            "pass_rate": round((total - failures) / total, 3) if total else None,
        })
    return output


@app.get("/analytics/summary")
def reliability_summary(db: Session = Depends(get_db)):
    """High-level reliability snapshot across ingested runs."""
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    all_results = [result for run in runs for result in run.results]
    failed = sum(not result.passed for result in all_results)
    tests = test_analytics(db)
    return {
        "runs": len(runs),
        "executions": len(all_results),
        "failures": failed,
        "overall_pass_rate": (
            round((len(all_results) - failed) / len(all_results), 3)
            if all_results else None
        ),
        "unique_tests": len(tests),
        "tests_with_status_changes": sum(item["flaky"] for item in tests),
        "failure_clusters": len(failure_clusters(db)),
    }


@app.get("/analytics/flakiness")
def flakiness_report(db: Session = Depends(get_db)):
    """Classify tests using repeated executions on the same commit.

    A pass and failure on the same commit is strong evidence of an
    inconsistent test outcome. Cross-commit transitions alone are not.
    """
    rows = db.execute(
        select(Result, Run.commit_sha)
        .join(Run)
        .order_by(Run.id, Result.id)
    ).all()
    history = {}
    for result, sha in rows:
        test = history.setdefault(result.test_name, {})
        test.setdefault(sha, []).append(result.passed)

    output = []
    for name, commits in history.items():
        inconsistent = sorted(
            sha for sha, statuses in commits.items()
            if len(statuses) >= 2 and len(set(statuses)) > 1
        )
        repeated = sum(len(statuses) >= 2 for statuses in commits.values())
        total = sum(map(len, commits.values()))
        if inconsistent:
            classification = "confirmed_inconsistent"
        elif repeated:
            classification = "no_inconsistency_observed"
        else:
            classification = "insufficient_same_commit_data"
        output.append({
            "test_name": name,
            "classification": classification,
            "executions": total,
            "commits_observed": len(commits),
            "commits_with_repeated_executions": repeated,
            "inconsistent_commits": inconsistent,
        })
    return sorted(output, key=lambda item: item["test_name"])
