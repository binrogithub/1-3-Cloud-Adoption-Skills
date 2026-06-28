#!/usr/bin/env python3
"""03_create_drs_job.py - Create DRS migration task.

Requires approval: APPROVED_CREATE_DRS_JOB
"""

import json
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
    update_migration_report_job_id,
)

logger = get_logger("03_create_drs_job")


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    logger.info(f"Creating DRS migration job (dry_run={dry_run})")

    # Check approval
    require_approval("APPROVED_CREATE_DRS_JOB", "Create DRS migration task")

    # Load payload
    payload_report = load_report("drs_payload")
    if not payload_report:
        logger.error("DRS payload not found. Run 02_generate_drs_payload.py first.")
        sys.exit(1)

    payload = payload_report.get("details", {})
    if not payload:
        logger.error("DRS payload is empty.")
        sys.exit(1)

    job_name = (payload.get("base_info") or {}).get("name") or payload.get("job_name")
    logger.info(f"Loaded DRS payload for job: {job_name or 'unknown'}")

    if dry_run:
        logger.info("[DRY-RUN] Would create DRS job with the following parameters:")
        logger.info(json.dumps(mask_dict(payload), indent=2, ensure_ascii=False))
        report_data = {
            "job_id": "dry-run-no-job-id",
            "job_name": job_name,
            "status": "DRY_RUN",
            "message": "Job creation skipped (dry-run mode)",
        }
        report_path = generate_report(
            "drs_job_create_report", report_data,
            stage="create_drs_job", status="SUCCESS",
        )
        append_migration_report("create_drs_job", "SUCCESS", details={"dry_run": True})
        logger.info(f"Report saved to: {report_path}")
        sys.exit(0)

    # Create DRS job
    try:
        client = get_drs_client()
        result = client.create_job(payload)
        job_id = result.get("id") or result.get("job_id") or result.get("job", {}).get("id")
        if not job_id:
            logger.error(f"No job_id in API response: {result}")
            sys.exit(1)

        logger.info(f"DRS job created successfully: job_id={job_id}")
        report_data = {
            "job_id": job_id,
            "job_name": job_name,
            "status": "CREATED",
            "api_result": mask_dict(result),
        }
        report_path = generate_report(
            "drs_job_create_report", report_data,
            stage="create_drs_job", status="SUCCESS",
        )
        update_migration_report_job_id(job_id)
        append_migration_report("create_drs_job", "SUCCESS", details={"job_id": job_id})
    except Exception as e:
        logger.error(f"Failed to create DRS job: {e}")
        report_data = {"error": str(e), "status": "FAILED"}
        generate_report("drs_job_create_report", report_data, stage="create_drs_job", status="FAILED", errors=[str(e)])
        append_migration_report("create_drs_job", "FAILED", details={"error": str(e)})
        sys.exit(1)

    duration = int(time.time() - start_time)
    append_migration_report("create_drs_job", "SUCCESS", duration_seconds=duration)
    logger.info(f"Report saved to: {report_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
