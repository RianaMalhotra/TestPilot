import pytest
from scripts.benchmark_api import benchmark, p95

def test_p95():
    assert p95([1, 2, 3, 4, 5]) == 5
    with pytest.raises(ValueError):
        p95([])

def test_benchmark():
    result = benchmark(3)
    assert result["sample_count"] == 3
    assert result["route"] == "/health"
    assert result["p95_ms"] >= 0
