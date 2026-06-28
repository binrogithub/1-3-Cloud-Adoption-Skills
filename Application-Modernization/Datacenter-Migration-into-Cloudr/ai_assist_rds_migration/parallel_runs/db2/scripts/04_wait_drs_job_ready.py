#!/usr/bin/env python3
"""04_wait_drs_job_ready.py - Wait for DRS job to reach ready status.

Waits initial_wait seconds, then polls every poll_interval seconds.
Maximum wait: max_wait seconds.
Exit code 2 if CREATE_FAILED, 1 if timeout, 0 if ready.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from drs_client import (
    STATUS_CREATE_FAILED,
    STATUS_CONFIGURATION,
    STATUS_WAITING_FOR_START,
    get_drs_client,
)
from log_utils import get_logger
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("04_wait_drs_job_ready")

READY_STATUSES = {STATUS_CONFIGURATION, STATUS_WAITING_FOR_START}


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
    config = load_config()

    initial_wait = int(os.getenv("WAIT_INITIAL_SEC", config.get("initial_wait", 600)))
    poll_interval = int(os.getenv("WAIT_POLL_SEC", config.get("poll_interval", 30)))
    max_wait = int(os.getenv("WAIT_MAX_SEC", config.get("max_wait", 1800)))

    logger.info(f"Waiting for DRS job to become ready (dry_run={dry_run})")
    logger.info(f"Parameters: initial_wait={initial_wait}s, poll_interval={poll_interval}s, max_wait={max_wait}s")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would wait for job to become ready, then poll status")
        report_data = {
            "job_id": job_id,
            "status": "DRY_RUN",
            "message": "Status polling skipped (dry-run mode)",
        }
        generate_report("drs_job_status_report", report_data, stage="wait_drs_job_ready", status="SUCCESS")
        append_migration_report("wait_drs_job_ready", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    # Initial wait
    logger.info(f"Initial wait: {initial_wait} seconds...")
    time.sleep(initial_wait)

    # Poll for status
    client = get_drs_client()
    elapsed = initial_wait
    last_status = None

    while elapsed < initial_wait + max_wait:
        try:
            result = client.get_job_status(job_id)
            status = result.get("status") or result.get("job", {}).get("status", "UNKNOWN")
            last_status = status
            logger.info(f"Job status: {status} (elapsed: {elapsed}s)")

            if status == STATUS_CREATE_FAILED:
                logger.error("DRS job creation FAILED!")
                report_data = {
                    "job_id": job_id,
                    "status": STATUS_CREATE_FAILED,
                    "elapsed_seconds": elapsed,
                    "api_result": result,
                }
                generate_report(
                    "drs_job_status_report", report_data,
                    stage="wait_drs_job_ready", status="FAILED",
                    errors=[f"DRS job status: {STATUS_CREATE_FAILED}"],
                )
                append_migration_report("wait_drs_job_ready", "FAILED", details={"status": STATUS_CREATE_FAILED})
                sys.exit(2)

            if status in READY_STATUSES:
                logger.info(f"DRS job is ready! Status: {status}")
                report_data = {
                    "job_id": job_id,
                    "status": status,
                    "elapsed_seconds": elapsed,
                }
                generate_report("drs_job_status_report", report_data, stage="wait_drs_job_ready", status="SUCCESS")
                duration = int(time.time() - start_time)
                append_migration_report("wait_drs_job_ready", "SUCCESS", duration_seconds=duration)
                sys.exit(0)

        except Exception as e:
            logger.warning(f"Error querying job status: {e}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    # Timeout
    logger.error(f"Timeout: Job not ready after {elapsed}s. Last status: {last_status}")
    report_data = {
        "job_id": job_id,
        "status": "TIMEOUT",
        "last_status": last_status,
        "elapsed_seconds": elapsed,
    }
    generate_report(
        "drs_job_status_report", report_data,
        stage="wait_drs_job_ready", status="FAILED",
        errors=[f"Timeout after {elapsed}s, last status: {last_status}"],
    )
    append_migration_report("wait_drs_job_ready", "FAILED", details={"timeout": True})
    sys.exit(1)


if __name__ == "__main__":
    main()
