#!/usr/bin/env python3
"""11_post_cutover_validate.py - Post-cutover data consistency validation.

Validates data consistency between source and target after cutover.
Only executes read-only queries.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from db_client import (
    close_all_connections,
    get_databases,
    get_sample_data,
    get_table_list,
    get_table_row_count,
)
from log_utils import get_logger
from report_utils import append_migration_report, generate_report

logger = get_logger("11_post_cutover_validate")


def validate_database_objects():
    """Validate database object counts and lists match.

    Returns:
        tuple: (is_consistent, detail_dict)
    """
    try:
        src_dbs = get_databases("source")
        tgt_dbs = get_databases("target")

        missing_in_target = set(src_dbs) - set(tgt_dbs)
        extra_in_target = set(tgt_dbs) - set(src_dbs)

        detail = {
            "source_db_count": len(src_dbs),
            "target_db_count": len(tgt_dbs),
            "missing_in_target": list(missing_in_target),
            "extra_in_target": list(extra_in_target),
        }

        is_consistent = len(missing_in_target) == 0 and len(extra_in_target) == 0
        return is_consistent, detail
    except Exception as e:
        return False, {"error": str(e)}


def validate_table_row_counts():
    """Validate table row counts match between source and target.

    Returns:
        tuple: (is_consistent, detail_dict)
    """
    try:
        src_dbs = get_databases("source")
        mismatches = []
        total_tables = 0

        for db in src_dbs:
            src_tables = get_table_list("source", db)
            tgt_tables = get_table_list("target", db)

            missing_tables = set(src_tables) - set(tgt_tables)
            if missing_tables:
                mismatches.append({
                    "database": db,
                    "missing_tables_in_target": list(missing_tables),
                })

            for table in src_tables:
                if table not in tgt_tables:
                    continue
                total_tables += 1
                src_count = get_table_row_count("source", db, table)
                tgt_count = get_table_row_count("target", db, table)

                # Allow 1% tolerance for approximate counts from information_schema
                if src_count > 0:
                    diff_pct = abs(src_count - tgt_count) / src_count * 100
                    if diff_pct > 1.0:
                        mismatches.append({
                            "database": db,
                            "table": table,
                            "source_count": src_count,
                            "target_count": tgt_count,
                            "diff_percent": round(diff_pct, 2),
                        })

        is_consistent = len(mismatches) == 0
        return is_consistent, {"total_tables_checked": total_tables, "mismatches": mismatches}
    except Exception as e:
        return False, {"error": str(e)}


def validate_sample_data(config):
    """Validate key table sample data matches.

    Args:
        config: Migration configuration.

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
                    "issue": "Sample data content differs",
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

    logger.info(f"Post-cutover validation starting (dry_run={dry_run})")

    if dry_run:
        logger.info("[DRY-RUN] Would validate database objects, row counts, and sample data")
        report_data = {"status": "DRY_RUN", "message": "Validation skipped (dry-run mode)"}
        generate_report("cutover_validation_report", report_data, stage="post_cutover_validate", status="SUCCESS")
        append_migration_report("post_cutover_validate", "SUCCESS", details={"dry_run": True})
        sys.exit(0)

    errors = []
    warnings = []
    check_results = {}

    # 1. Validate database objects
    logger.info("Validating database objects...")
    obj_consistent, obj_detail = validate_database_objects()
    check_results["database_objects"] = {"consistent": obj_consistent, "detail": obj_detail}
    if not obj_consistent:
        errors.append(f"Database objects mismatch: {obj_detail}")
    logger.info(f"  Result: {'CONSISTENT' if obj_consistent else 'INCONSISTENT'}")

    # 2. Validate table row counts
    logger.info("Validating table row counts...")
    row_consistent, row_detail = validate_table_row_counts()
    check_results["table_row_counts"] = {"consistent": row_consistent, "detail": row_detail}
    if not row_consistent:
        warnings.append(f"Table row count mismatches found: {row_detail.get('mismatches', [])}")
    logger.info(f"  Result: {'CONSISTENT' if row_consistent else 'INCONSISTENT'}")

    # 3. Validate sample data
    logger.info("Validating sample data...")
    sample_consistent, sample_detail = validate_sample_data(config)
    check_results["sample_data"] = {"consistent": sample_consistent, "detail": sample_detail}
    if not sample_consistent:
        errors.append(f"Sample data mismatch: {sample_detail}")
    logger.info(f"  Result: {'CONSISTENT' if sample_consistent else 'INCONSISTENT'}")

    # Generate report
    if errors:
        overall_status = "FAILED"
    elif warnings:
        overall_status = "WARNING"
    else:
        overall_status = "SUCCESS"

    report_data = {"check_results": check_results}
    generate_report(
        "cutover_validation_report", report_data,
        stage="post_cutover_validate", status=overall_status,
        errors=errors, warnings=warnings,
    )
    duration = int(time.time() - start_time)
    append_migration_report("post_cutover_validate", overall_status, duration_seconds=duration)

    close_all_connections()

    if overall_status == "FAILED":
        logger.error("Post-cutover validation FAILED - data inconsistency detected")
        sys.exit(1)

    logger.info(f"Post-cutover validation completed: {overall_status}")
    sys.exit(0)


if __name__ == "__main__":
    main()
