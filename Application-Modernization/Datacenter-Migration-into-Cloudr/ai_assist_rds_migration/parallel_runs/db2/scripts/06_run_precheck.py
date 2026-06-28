#!/usr/bin/env python3
"""06_run_precheck.py - Run DRS precheck and wait for results.

Triggers precheck, polls for results, and classifies as PASS/WARN/FAIL.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from drs_client import get_drs_client
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("06_run_precheck")


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


def classify_precheck_results(results):
    """Classify precheck results into PASS/WARN/FAIL categories.

    Args:
        results: Raw precheck results from DRS API.

    Returns:
        tuple: (checks_list, errors_list, warnings_list)
    """
    checks = []
    errors = []
    warnings = []

    # Parse precheck results - structure varies by DRS API version
    precheck_items = results.get("results", results.get("precheck_results", []))
    if isinstance(precheck_items, dict):
        precheck_items = precheck_items.get("list", [])

    for item in precheck_items:
        item_name = item.get("name", item.get("check_name", "unknown"))
        item_status = item.get("status", item.get("result", "unknown")).upper()
        item_message = item.get("message", item.get("reason", ""))

        if item_status in ("PASS", "OK", "SUCCESS"):
            checks.append({"item": item_name, "status": "PASS", "message": item_message})
        elif item_status in ("FAIL", "ERROR", "FAILED", "CRITICAL"):
            checks.append({"item": item_name, "status": "FAIL", "message": item_message})
            errors.append(f"{item_name}: {item_message}")
        elif item_status in ("WARN", "WARNING", "ALARM"):
            checks.append({"item": item_name, "status": "WARN", "message": item_message})
            warnings.append(f"{item_name}: {item_message}")
        else:
            checks.append({"item": item_name, "status": "WARN", "message": f"Unknown status: {item_status}. {item_message}"})
            warnings.append(f"{item_name}: Unknown status - {item_message}")

    return checks, errors, warnings


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    config = load_config()

    precheck_poll_interval = int(os.getenv("PRECHECK_POLL_SEC", config.get("precheck_poll_interval", 10)))
    precheck_max_wait = int(os.getenv("PRECHECK_MAX_WAIT_SEC", config.get("precheck_max_wait", 600)))

    logger.info(f"Running DRS precheck (dry_run={dry_run})")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would trigger DRS precheck and poll for results")
        report_data = {
            "job_id": job_id,
            "status": "DRY_RUN",
            "message": "Precheck skipped (dry-run mode)",
        }
        generate_report("precheck_report", report_data, stage="precheck", status="SUCCESS")
        append_migration_report("precheck", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    client = get_drs_client()

    # Trigger precheck
    logger.info("Triggering DRS precheck...")
    try:
        client.run_precheck(job_id)
        logger.info("Precheck triggered successfully")
    except Exception as e:
        logger.error(f"Failed to trigger precheck: {e}")
        generate_report(
            "precheck_report", {"job_id": job_id, "error": str(e)},
            stage="precheck", status="FAILED", errors=[str(e)],
        )
        append_migration_report("precheck", "FAILED", details={"error": str(e)})
        sys.exit(1)

    # Poll for precheck results
    logger.info(f"Polling for precheck results (interval={precheck_poll_interval}s, max={precheck_max_wait}s)...")
    elapsed = 0
    while elapsed < precheck_max_wait:
        time.sleep(precheck_poll_interval)
        elapsed += precheck_poll_interval

        try:
            result = client.get_precheck_result(job_id)
            precheck_status = result.get("status", result.get("precheck_status", "")).upper()

            if precheck_status in ("COMPLETE", "FINISHED", "SUCCESS"):
                logger.info("Precheck completed, analyzing results...")
                checks, errors, warnings = classify_precheck_results(result)

                overall_status = "FAILED" if errors else ("WARNING" if warnings else "SUCCESS")
                report_data = {
                    "job_id": job_id,
                    "checks": checks,
                    "precheck_raw": mask_dict(result),
                }
                generate_report(
                    "precheck_report", report_data,
                    stage="precheck", status=overall_status,
                    errors=errors, warnings=warnings,
                )
                duration = int(time.time() - start_time)
                append_migration_report("precheck", overall_status, duration_seconds=duration)

                if overall_status == "FAILED":
                    logger.error("DRS precheck FAILED")
                    sys.exit(1)
                logger.info(f"DRS precheck completed: {overall_status}")
                sys.exit(0)

            elif precheck_status in ("FAIL", "FAILED", "ERROR"):
                logger.error(f"Precheck failed with status: {precheck_status}")
                generate_report(
                    "precheck_report", {"job_id": job_id, "status": "FAILED", "result": mask_dict(result)},
                    stage="precheck", status="FAILED", errors=[f"Precheck status: {precheck_status}"],
                )
                append_migration_report("precheck", "FAILED")
                sys.exit(1)

            logger.info(f"Precheck in progress... status={precheck_status} (elapsed={elapsed}s)")

        except Exception as e:
            logger.warning(f"Error polling precheck results: {e}")

    # Timeout
    logger.error(f"Precheck timeout after {elapsed}s")
    generate_report(
        "precheck_report", {"job_id": job_id, "status": "TIMEOUT"},
        stage="precheck", status="FAILED", errors=[f"Timeout after {elapsed}s"],
    )
    append_migration_report("precheck", "FAILED", details={"timeout": True})
    sys.exit(1)


if __name__ == "__main__":
    main()
