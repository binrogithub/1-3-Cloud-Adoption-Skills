#!/usr/bin/env python3
"""05_test_connection.py - Test DRS database connections.

Tests both source and target database connections via DRS API.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run
from drs_client import get_drs_client
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("05_test_connection")


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
    logger.info(f"Testing DRS database connections (dry_run={dry_run})")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    errors = []
    src_result = None
    tgt_result = None

    if dry_run:
        logger.info("[DRY-RUN] Would test source and target database connections via DRS API")
        report_data = {
            "job_id": job_id,
            "source_connection": {"status": "DRY_RUN", "message": "Skipped"},
            "target_connection": {"status": "DRY_RUN", "message": "Skipped"},
        }
        generate_report("connection_test_report", report_data, stage="test_connection", status="SUCCESS")
        append_migration_report("test_connection", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    client = get_drs_client()

    # Test source connection
    logger.info("Testing source database connection...")
    try:
        src_result = client.test_connection(job_id, endpoint_type="so")
        src_status = src_result.get("status", "UNKNOWN")
        if src_status in ("success", "SUCCESS", "true"):
            logger.info("Source database connection: SUCCESS")
        else:
            logger.error(f"Source database connection FAILED: {src_result}")
            errors.append(f"Source connection failed: {json.dumps(mask_dict(src_result), ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Source connection test error: {e}")
        errors.append(f"Source connection error: {e}")
        src_result = {"error": str(e)}

    # Test target connection
    logger.info("Testing target database connection...")
    try:
        tgt_result = client.test_connection(job_id, endpoint_type="ta")
        tgt_status = tgt_result.get("status", "UNKNOWN")
        if tgt_status in ("success", "SUCCESS", "true"):
            logger.info("Target database connection: SUCCESS")
        else:
            logger.error(f"Target database connection FAILED: {tgt_result}")
            errors.append(f"Target connection failed: {json.dumps(mask_dict(tgt_result), ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Target connection test error: {e}")
        errors.append(f"Target connection error: {e}")
        tgt_result = {"error": str(e)}

    # Generate report
    overall_status = "FAILED" if errors else "SUCCESS"
    report_data = {
        "job_id": job_id,
        "source_connection": mask_dict(src_result) if src_result else None,
        "target_connection": mask_dict(tgt_result) if tgt_result else None,
    }
    generate_report(
        "connection_test_report", report_data,
        stage="test_connection", status=overall_status, errors=errors,
    )

    duration = int(time.time() - start_time)
    append_migration_report("test_connection", overall_status, duration_seconds=duration)

    if overall_status == "FAILED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
