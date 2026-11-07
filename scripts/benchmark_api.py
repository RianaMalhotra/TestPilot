"""Local CI smoke benchmark for TestPilot's health endpoint."""
import argparse
import json
import math
import os
from pathlib import Path
from time import perf_counter_ns
from fastapi.testclient import TestClient
from app.main import app

def p95(values):
    if not values:
        raise ValueError("No measurements")
    return sorted(values)[math.ceil(len(values) * .95) - 1]

def benchmark(count=100):
    if not 1 <= count <= 10000:
        raise ValueError("count must be 1..10000")
    times = []
    with TestClient(app) as client:
        for i in range(count + 10):
            start = perf_counter_ns()
            response = client.get("/health")
            response.raise_for_status()
            if i >= 10:
                times.append((perf_counter_ns() - start) / 1_000_000)
    return {"method": "GET", "route": "/health", "p95_ms": round(p95(times), 3),
            "average_ms": round(sum(times) / len(times), 3), "sample_count": count}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", default="performance-report.json")
    args = parser.parse_args()
    sample = benchmark(args.count)
    sample.update(commit_sha=os.getenv("GITHUB_SHA", "local"),
                  branch=os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF_NAME", "main"))
    Path(args.output).write_text(json.dumps(sample, indent=2) + "\n")
    print(json.dumps(sample, indent=2))

if __name__ == "__main__":
    main()
