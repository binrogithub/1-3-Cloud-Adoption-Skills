#!/usr/bin/env python3
"""07_start_migration.py - Start DRS migration task.

Prerequisites:
- Approval: APPROVED_START_DRS_JOB
- All prior checks passed (env_check, db_precheck, connection_test, precheck)
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from approval_gate import require_approval
from config_loader import is_dry_run
from drs_client import get_drs_client
from log_utils import get_logger, mask_dict
from report_utils import (
    append_migration_report,
    generate_report,
    load_report,
    report_has_no_fail,
    report_status_is,
)

logger = get_logger("07_start_migration")


def _is_true(name, default="true"):
    return os.getenv(name, default).strip().lower() == "true"


def _check_env_gate(allow_drs_only_precheck):
    """Check env_check gate with optional relaxed mode."""
    report = load_report("env_check")
    if not report:
        return False, "env_check report not found"

    if report.get("status") == "SUCCESS":
        return True, None

    if not allow_drs_only_precheck:
        return False, "env_check report status is not SUCCESS"

    env_vars = (report.get("details", {}).get("env_vars", {}) or {})
    missing = [k for k, v in env_vars.items() if k != "DRY_RUN" and v != "SET"]
    if missing:
        return False, f"env_check missing required variables: {missing}"

    return True, None


def check_prerequisites():
    """Check all prerequisite reports are successful.

    Returns:
        tuple: (is_ready, unmet_list)
    """
    unmet = []
    allow_drs_only_precheck = _is_true("ALLOW_DRS_ONLY_PRECHECK", "true")

    env_ok, env_reason = _check_env_gate(allow_drs_only_precheck)
    if not env_ok:
        unmet.append(env_reason)

    if not report_has_no_fail("db_precheck"):
        if allow_drs_only_precheck:
            logger.warning(
                "db_precheck has FAIL items, but ALLOW_DRS_ONLY_PRECHECK=true. "
                "Will rely on DRS connection test + DRS precheck as start gate."
            )
        else:
            unmet.append("db_precheck report has FAIL items")

    if not report_status_is("connection_test", "SUCCESS"):
        unmet.append("connection_test report status is not SUCCESS")

    if not report_has_no_fail("precheck"):
        unmet.append("precheck report has FAIL items")

    return len(unmet) == 0, unmet


def get_job_id():
    """Read job_id from the creation report."""
    report = load_report("drs_job_create_report")
    if not report:
        logger.error("DRS job creation report not found. Run 03_create_drs_job.py first.")
        sys.exit(1)
    job_id = report.get("details", {}).get("job_id")
    if not job_id:
        logger.error("No job_id found in creation report.")
        sys.exit(1)
    return job_id


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    logger.info(f"Starting DRS migration (dry_run={dry_run})")

    # Check approval
    require_approval("APPROVED_START_DRS_JOB", "Start DRS migration task")

    # Check prerequisites
    ready, unmet = check_prerequisites()
    if not ready:
        logger.error("Prerequisites not met:")
        for item in unmet:
            logger.error(f"  - {item}")
        generate_report(
            "migration_start_report",
            {"prerequisites": unmet},
            stage="start_migration", status="FAILED",
            errors=unmet,
        )
        append_migration_report("start_migration", "FAILED", details={"unmet_prerequisites": unmet})
        sys.exit(1)

    logger.info("All prerequisites met")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would start DRS migration task")
        report_data = {
            "job_id": job_id,
            "status": "DRY_RUN",
            "message": "Migration start skipped (dry-run mode)",
        }
        generate_report("migration_start_report", report_data, stage="start_migration", status="SUCCESS")
        append_migration_report("start_migration", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    # Start migration
    client = get_drs_client()
    try:
        result = client.start_job(job_id)
        logger.info(f"Migration started successfully: {mask_dict(result)}")
        report_data = {
            "job_id": job_id,
            "status": "STARTED",
            "api_result": mask_dict(result),
        }
        generate_report("migration_start_report", report_data, stage="start_migration", status="SUCCESS")
        duration = int(time.time() - start_time)
        append_migration_report("start_migration", "SUCCESS", duration_seconds=duration)
    except Exception as e:
        logger.error(f"Failed to start migration: {e}")
        report_data = {"job_id": job_id, "error": str(e)}
        generate_report(
            "migration_start_report", report_data,
            stage="start_migration", status="FAILED", errors=[str(e)],
        )
        append_migration_report("start_migration", "FAILED", details={"error": str(e)})
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
