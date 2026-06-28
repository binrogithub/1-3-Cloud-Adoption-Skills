#!/usr/bin/env python3
"""08_monitor_migration.py - Monitor DRS migration status.

Continuously polls migration progress until INCR_TRANS state is reached
or an abnormal state is detected.
"""

import json
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from drs_client import (
    ABNORMAL_STATUSES,
    STATUS_FULL_TRANS,
    STATUS_INCR_TRANS,
    get_drs_client,
)
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("08_monitor_migration")

# Graceful shutdown flag
_shutdown = False


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    global _shutdown
    logger.info("Received shutdown signal, finishing current monitoring cycle...")
    _shutdown = True


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
    poll_interval = config.get("poll_interval", 30)

    logger.info(f"Monitoring DRS migration (dry_run={dry_run}, poll_interval={poll_interval}s)")

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would monitor migration status continuously")
        report_data = {
            "job_id": job_id,
            "status": "DRY_RUN",
            "message": "Monitoring skipped (dry-run mode)",
        }
        generate_report("migration_status_report", report_data, stage="monitor_migration", status="SUCCESS")
        append_migration_report("monitor_migration", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    client = get_drs_client()
    status_history = []
    last_status = None

    while not _shutdown:
        try:
            # Get job status
            result = client.get_job_status(job_id)
            status = result.get("status") or result.get("job", {}).get("status", "UNKNOWN")
            last_status = status

            # Get progress
            try:
                progress = client.get_job_progress(job_id)
            except Exception:
                progress = {}

            # Record status
            status_entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": status,
                "progress": mask_dict(progress),
            }
            status_history.append(status_entry)

            # Display status
            if status == STATUS_FULL_TRANS:
                full_progress = progress.get("full_trans", progress.get("full_progress", {}))
                progress_pct = full_progress.get("progress", "N/A")
                logger.info(f"Status: FULL_TRANS | Full progress: {progress_pct}%")

            elif status == STATUS_INCR_TRANS:
                incr_delay = progress.get("incr_trans", progress.get("incremental_delay", "N/A"))
                if isinstance(incr_delay, dict):
                    incr_delay = incr_delay.get("delay", "N/A")
                logger.info(f"Status: INCR_TRANS | Incremental delay: {incr_delay}s")
                logger.info("Migration has entered incremental sync phase. Monitoring complete.")
                break

            elif status in ABNORMAL_STATUSES:
                logger.error(f"Abnormal status detected: {status}")
                report_data = {
                    "job_id": job_id,
                    "status": status,
                    "status_history": status_history,
                }
                generate_report(
                    "migration_status_report", report_data,
                    stage="monitor_migration", status="FAILED",
                    errors=[f"Abnormal status: {status}"],
                )
                append_migration_report("monitor_migration", "FAILED", details={"status": status})
                sys.exit(1)

            else:
                logger.info(f"Status: {status}")

        except Exception as e:
            logger.warning(f"Error querying migration status: {e}")

        time.sleep(poll_interval)

    # Generate final report
    report_data = {
        "job_id": job_id,
        "final_status": last_status,
        "status_history": status_history,
        "monitoring_duration_seconds": int(time.time() - start_time),
    }
    generate_report("migration_status_report", report_data, stage="monitor_migration", status="SUCCESS")
    duration = int(time.time() - start_time)
    append_migration_report("monitor_migration", "SUCCESS", duration_seconds=duration)

    logger.info("Migration monitoring completed")
    sys.exit(0)


if __name__ == "__main__":
    main()
