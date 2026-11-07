"""Validate deployment files without contacting the hosting provider."""
from pathlib import Path


def validate():
    render = Path("render.yaml").read_text()
    requirements = Path("requirements.txt").read_text()
    workflow = Path(".github/workflows/import-ci.yml").read_text()
    required = [
        "preDeployCommand: alembic upgrade head",
        "healthCheckPath: /ready",
        "TESTPILOT_REQUIRE_AUTH",
        "TESTPILOT_REQUIRE_MIGRATIONS",
        "TESTPILOT_API_KEY",
        "DATABASE_URL",
    ]
    missing = [item for item in required if item not in render]
    if "psycopg[binary]" not in requirements:
        missing.append("psycopg dependency")
    if "TESTPILOT_API_URL" not in workflow:
        missing.append("scheduled importer API URL")
    if missing:
        raise SystemExit(f"Deployment validation failed: {', '.join(missing)}")
    print("Deployment configuration checks passed")


if __name__ == "__main__":
    validate()
