import os
import subprocess
from pathlib import Path
from typing import Any

from prefect import task

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).parents[2]


class DbtRunError(Exception):
    pass


@task(retries=1, retry_delay_seconds=120)
def run_dbt_build(
    dbt_project_dir: str = "dbt",
    dbt_profiles_dir: str = "dbt",
    target: str = "dev",
    fail_fast: bool = False,
    full_refresh: bool = False,
) -> dict[str, Any]:
    cmd = [
        "dbt", "build",
        "--project-dir", dbt_project_dir,
        "--profiles-dir", dbt_profiles_dir,
        "--target", target,
    ]
    if fail_fast:
        cmd.append("--fail-fast")
    if full_refresh:
        cmd.append("--full-refresh")

    env = {**os.environ}
    if settings.google_application_credentials:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
    if settings.gcp_project_id:
        env["GCP_PROJECT_ID"] = settings.gcp_project_id

    deps_cmd = [
        "dbt", "deps",
        "--project-dir", dbt_project_dir,
        "--profiles-dir", dbt_profiles_dir,
    ]
    logger.info("dbt_deps_starting", cmd=" ".join(deps_cmd))
    deps_result = subprocess.run(
        deps_cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=env,
    )
    for line in deps_result.stdout.splitlines():
        if line.strip():
            logger.info("dbt", line=line)
    if deps_result.returncode != 0:
        last_lines = "\n".join(deps_result.stdout.splitlines()[-20:])
        raise DbtRunError(
            f"dbt deps exited with code {deps_result.returncode}\n{last_lines}"
        )

    logger.info("dbt_build_starting", cmd=" ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=env,
    )

    for line in result.stdout.splitlines():
        if line.strip():
            logger.info("dbt", line=line)

    if result.stderr:
        for line in result.stderr.splitlines():
            if line.strip():
                logger.warning("dbt_stderr", line=line)

    if result.returncode != 0:
        last_lines = "\n".join(result.stdout.splitlines()[-50:])
        raise DbtRunError(
            f"dbt build exited with code {result.returncode}\n{last_lines}"
        )

    logger.info("dbt_build_complete")
    return {"returncode": result.returncode}
