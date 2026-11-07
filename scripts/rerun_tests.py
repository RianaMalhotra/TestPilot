"""Run pytest repeatedly at the current checkout and produce JUnit reports.

Run from a trusted repository checkout. Test code is executable code.
Example:
  python -m scripts.rerun_tests --count 3 --output-dir rerun-reports
"""
import argparse
from pathlib import Path
import subprocess
import sys


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--output-dir", default="rerun-reports")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args()
    for result in rerun_tests(
        args.count, Path(args.output_dir), args.pytest_args
    ):
        print(result)


if __name__ == "__main__":
    main()
