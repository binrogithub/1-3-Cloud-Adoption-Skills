#!/usr/bin/env python3
"""10_cutover_check.py - Pre-cutover readiness check.

Checks all conditions required before cutover:
- Full migration complete (INCR_TRANS status)
- Incremental delay below threshold
- Object compare consistent
- Row count compare consistent
- Key table sampling consistent
- Approval: APPROVED_CUTOVER
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from approval_gate import require_approval
from config_loader import is_dry_run, load_config
from db_client import close_all_connections, get_databases, get_sample_data, get_table_list, get_table_row_count
from drs_client import STATUS_INCR_TRANS, get_drs_client
from log_utils import get_logger
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("10_cutover_check")


def get_job_id():
    """Read job_id from the creation report."""
    report = load_report("drs_job_create_report")
    if not report:
        logger.error("DRS job creation report not found.")
        sys.exit(1)
    return report.get("details", {}).get("job_id")


def check_full_migration_complete(client, job_id):
    """Check if full migration is complete (status is INCR_TRANS).

    Returns:
        tuple: (is_complete, detail_dict)
    """
    try:
        result = client.get_job_status(job_id)
        status = result.get("status") or result.get("job", {}).get("status", "UNKNOWN")
        is_complete = status == STATUS_INCR_TRANS
        return is_complete, {"status": status, "expected": STATUS_INCR_TRANS}
    except Exception as e:
        return False, {"error": str(e)}


def check_incr_delay(client, job_id, threshold):
    """Check if incremental delay is below threshold.

    Returns:
        tuple: (is_below_threshold, detail_dict)
    """
    try:
        progress = client.get_job_progress(job_id)
        incr_info = progress.get("incr_trans", progress.get("incremental_delay", {}))
        if isinstance(incr_info, dict):
            delay = incr_info.get("delay", incr_info.get("delay_millis", -1))
            if isinstance(delay, str):
                delay = int(delay) if delay.isdigit() else -1
        else:
            delay = incr_info if isinstance(incr_info, (int, float)) else -1

        is_below = delay >= 0 and delay <= threshold
        return is_below, {"delay": delay, "threshold": threshold}
    except Exception as e:
        return False, {"error": str(e)}


def check_compare_consistent(compare_type):
    """Check if compare results are consistent.

    Args:
        compare_type: 'object' or 'row_count'

    Returns:
        tuple: (is_consistent, detail_dict)
    """
    report = load_report("compare_report")
    if not report:
        return False, {"error": "Compare report not found"}

    details = report.get("details", {})
    compare_data = details.get(f"{compare_type}_compare", {})
    if not compare_data:
        return False, {"error": f"No {compare_type} compare data"}

    status = compare_data.get("status", "").upper()
    if status in ("COMPLETE", "SUCCESS"):
        # Check for differences
        diff_count = compare_data.get("diff_count", compare_data.get("different_count", 0))
        is_consistent = diff_count == 0
        return is_consistent, {"status": status, "diff_count": diff_count}

    return False, {"status": status}


def check_sample_tables(config):
    """Check key table sampling consistency.

    Returns:
        tuple: (is_consistent, detail_dict)
    """
    sample_tables = config.get("sample_tables", [])
    if not sample_tables:
        return True, {"message": "No sample tables configured"}

    inconsistencies = []
    for table_ref in sample_tables:
        try:
            if "." in table_ref:
                db_name, table_name = table_ref.split(".", 1)
            else:
                continue

            src_data = get_sample_data("source", db_name, table_name, limit=10)
            tgt_data = get_sample_data("target", db_name, table_name, limit=10)

            if len(src_data) != len(tgt_data):
                inconsistencies.append({
                    "table": table_ref,
                    "issue": f"Row count mismatch: source={len(src_data)}, target={len(tgt_data)}",
                })
            elif src_data != tgt_data:
                inconsistencies.append({
                    "table": table_ref,
                    "issue": "Sample data content mismatch",
                })
        except Exception as e:
            inconsistencies.append({"table": table_ref, "issue": str(e)})

    is_consistent = len(inconsistencies) == 0
    return is_consistent, {"inconsistencies": inconsistencies}


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    config = load_config()
    incr_delay_threshold = config.get("incr_delay_threshold", 5)

    logger.info(f"Running cutover readiness check (dry_run={dry_run})")

    job_id = get_job_id()
    logger.info(f"Job ID: {job_id}")

    if dry_run:
        logger.info("[DRY-RUN] Would check all cutover conditions:")
        logger.info("  1. Full migration complete (INCR_TRANS)")
        logger.info(f"  2. Incremental delay < {incr_delay_threshold}s")
        logger.info("  3. Object compare consistent")
        logger.info("  4. Row count compare consistent")
        logger.info("  5. Key table sampling consistent")
        logger.info("  6. Approval: APPROVED_CUTOVER")
        report_data = {"job_id": job_id, "status": "DRY_RUN", "message": "Cutover check skipped (dry-run mode)"}
        generate_report("cutover_check_report", report_data, stage="cutover_check", status="SUCCESS")
        append_migration_report("cutover_check", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    unmet_conditions = []
    check_results = {}

    # 1. Check full migration complete
    logger.info("Checking full migration complete...")
    client = get_drs_client()
    complete, detail = check_full_migration_complete(client, job_id)
    check_results["full_migration_complete"] = {"passed": complete, "detail": detail}
    if not complete:
        unmet_conditions.append(f"Full migration not complete: {detail}")
    logger.info(f"  Result: {'PASS' if complete else 'FAIL'} - {detail}")

    # 2. Check incremental delay
    logger.info(f"Checking incremental delay < {incr_delay_threshold}s...")
    below_threshold, detail = check_incr_delay(client, job_id, incr_delay_threshold)
    check_results["incr_delay_below_threshold"] = {"passed": below_threshold, "detail": detail}
    if not below_threshold:
        unmet_conditions.append(f"Incremental delay above threshold: {detail}")
    logger.info(f"  Result: {'PASS' if below_threshold else 'FAIL'} - {detail}")

    # 3. Check object compare
    logger.info("Checking object compare consistency...")
    obj_consistent, detail = check_compare_consistent("object")
    check_results["object_compare_consistent"] = {"passed": obj_consistent, "detail": detail}
    if not obj_consistent:
        unmet_conditions.append(f"Object compare not consistent: {detail}")
    logger.info(f"  Result: {'PASS' if obj_consistent else 'FAIL'} - {detail}")

    # 4. Check row count compare
    logger.info("Checking row count compare consistency...")
    row_consistent, detail = check_compare_consistent("row_count")
    check_results["row_count_compare_consistent"] = {"passed": row_consistent, "detail": detail}
    if not row_consistent:
        unmet_conditions.append(f"Row count compare not consistent: {detail}")
    logger.info(f"  Result: {'PASS' if row_consistent else 'FAIL'} - {detail}")

    # 5. Check sample tables
    logger.info("Checking key table sampling consistency...")
    sample_consistent, detail = check_sample_tables(config)
    check_results["sample_tables_consistent"] = {"passed": sample_consistent, "detail": detail}
    if not sample_consistent:
        unmet_conditions.append(f"Sample tables not consistent: {detail}")
    logger.info(f"  Result: {'PASS' if sample_consistent else 'FAIL'} - {detail}")

    # 6. Check approval
    logger.info("Checking cutover approval...")
    try:
        require_approval("APPROVED_CUTOVER", "Execute cutover")
        check_results["cutover_approval"] = {"passed": True}
    except SystemExit:
        check_results["cutover_approval"] = {"passed": False}
        unmet_conditions.append("Cutover approval not granted")
        # Don't exit here, collect all unmet conditions first

    # Generate report
    if unmet_conditions:
        overall_status = "FAILED"
        cutover_ready = False
        logger.error("CUTOVER NOT READY - Unmet conditions:")
        for cond in unmet_conditions:
            logger.error(f"  - {cond}")
    else:
        overall_status = "SUCCESS"
        cutover_ready = True
        logger.info("CUTOVER READY - All conditions met")

    report_data = {
        "job_id": job_id,
        "cutover_ready": cutover_ready,
        "check_results": check_results,
    }
    generate_report(
        "cutover_check_report", report_data,
        stage="cutover_check", status=overall_status,
        errors=unmet_conditions,
    )
    duration = int(time.time() - start_time)
    append_migration_report("cutover_check", overall_status, duration_seconds=duration)

    close_all_connections()

    if not cutover_ready:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
