#!/usr/bin/env python3
"""09_create_compare_task.py - Create DRS data compare tasks.

Creates object compare and row count compare tasks, then polls for results.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from drs_client import get_drs_client
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("09_create_compare_task")

COMPARE_POLL_INTERVAL = 10
COMPARE_MAX_WAIT = 1800  # 30 minutes


def get_job_id():
    """Read job_id from the creation report."""
    report = load_report("drs_job_create_report")
    if not report:
        logger.error("DRS job creation report not found.")
        sys.exit(1)
    job_id = report.get("details", {}).get("job_id")
    if not job_id:
        logger.error("No job_id found in creation report.")
        sys.exit(1)
    return job_id


def poll_compare_result(client, compare_task_id, task_type):
    """Poll for compare task result.

    Args:
        client: DRS client instance.
        compare_task_id: Compare task ID.
        task_type: Type of compare task (for logging).

    Returns:
        Dictionary with compare result.
    """
    elapsed = 0
    while elapsed < COMPARE_MAX_WAIT:
        time.sleep(COMPARE_POLL_INTERVAL)
        elapsed += COMPARE_POLL_INTERVAL
        try:
            result = client.get_compare_result(compare_task_id)
            status = result.get("status", "").upper()
            if status in ("COMPLETE", "FINISHED", "SUCCESS"):
                logger.info(f"{task_type} compare completed")
                return result
            elif status in ("FAIL", "FAILED", "ERROR"):
                logger.error(f"{task_type} compare failed: {result}")
                return result
            logger.info(f"{task_type} compare in progress... status={status} (elapsed={elapsed}s)")
        except Exception as e:
            logger.warning(f"Error polling {task_type} compare result: {e}")

    logger.error(f"{task_type} compare timeout after {elapsed}s")
    return {"status": "TIMEOUT"}


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    logger.info(f"Creating DRS data compare tasks (dry_run={dry_run})")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would create object compare and row count compare tasks")
        report_data = {
            "job_id": job_id,
            "status": "DRY_RUN",
            "message": "Compare tasks skipped (dry-run mode)",
        }
        generate_report("compare_report", report_data, stage="create_compare", status="SUCCESS")
        append_migration_report("create_compare", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    client = get_drs_client()
    errors = []
    warnings = []

    # Create object compare task
    logger.info("Creating object compare task...")
    obj_compare_result = None
    try:
        obj_task = client.create_compare_task(job_id, compare_type="object")
        obj_task_id = obj_task.get("id") or obj_task.get("compare_task_id")
        if obj_task_id:
            logger.info(f"Object compare task created: {obj_task_id}")
            obj_compare_result = poll_compare_result(client, obj_task_id, "Object")
        else:
            logger.warning(f"No compare task ID returned: {obj_task}")
            warnings.append("Object compare: no task ID returned")
    except Exception as e:
        logger.error(f"Failed to create object compare task: {e}")
        errors.append(f"Object compare task error: {e}")

    # Create row count compare task
    logger.info("Creating row count compare task...")
    row_compare_result = None
    try:
        row_task = client.create_compare_task(job_id, compare_type="data")
        row_task_id = row_task.get("id") or row_task.get("compare_task_id")
        if row_task_id:
            logger.info(f"Row count compare task created: {row_task_id}")
            row_compare_result = poll_compare_result(client, row_task_id, "RowCount")
        else:
            logger.warning(f"No compare task ID returned: {row_task}")
            warnings.append("Row count compare: no task ID returned")
    except Exception as e:
        logger.error(f"Failed to create row count compare task: {e}")
        errors.append(f"Row count compare task error: {e}")

    # Generate report
    overall_status = "FAILED" if errors else ("WARNING" if warnings else "SUCCESS")
    report_data = {
        "job_id": job_id,
        "object_compare": mask_dict(obj_compare_result) if obj_compare_result else None,
        "row_count_compare": mask_dict(row_compare_result) if row_compare_result else None,
    }
    generate_report(
        "compare_report", report_data,
        stage="create_compare", status=overall_status,
        errors=errors, warnings=warnings,
    )
    duration = int(time.time() - start_time)
    append_migration_report("create_compare", overall_status, duration_seconds=duration)

    if overall_status == "FAILED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
