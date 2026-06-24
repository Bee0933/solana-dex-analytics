"""Standalone data-freshness check: runs `dbt source freshness` and alerts on stale data.

Runs as its own Cloud Run Job (container command override) on a 04:00 UTC schedule,
after the 02:00 pipeline run. On WARN or ERROR it logs a structured ERROR and exits
non-zero, which the Cloud Logging error metric turns into an email alert.
"""

import os
import subprocess
from pathlib import Path

from src.config import settings
from src.logging import configure_logging, get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).parents[1]


def _run_dbt(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    cmd = ["dbt", *args, "--project-dir", "dbt", "--profiles-dir", "dbt"]
    logger.info("dbt_starting", cmd=" ".join(cmd))
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False, cwd=str(_REPO_ROOT), env=env
    )
    for line in result.stdout.splitlines():
        if line.strip():
            logger.info("dbt", line=line)
    return result


def run_freshness() -> None:
    env = {**os.environ}
    if settings.google_application_credentials:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    if settings.gcp_project_id:
        env["GCP_PROJECT_ID"] = settings.gcp_project_id

    # packages must be installed before the project compiles in a fresh container
    deps = _run_dbt(["deps"], env)
    if deps.returncode != 0:
        tail = "\n".join(deps.stdout.splitlines()[-30:])
        logger.error("freshness_deps_failed", returncode=deps.returncode, tail=tail)
        raise SystemExit(1)

    result = _run_dbt(["source", "freshness"], env)
    # dbt exits non-zero on ERROR (stale past error_after); a WARN still exits 0,
    # so we also scan the output for it.
    warned = "WARN" in result.stdout
    if result.returncode != 0 or warned:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        logger.error(
            "freshness_check_failed", returncode=result.returncode, warned=warned, tail=tail
        )
        raise SystemExit(1)

    logger.info("freshness_check_passed")


if __name__ == "__main__":
    configure_logging(settings.log_level)
    run_freshness()
