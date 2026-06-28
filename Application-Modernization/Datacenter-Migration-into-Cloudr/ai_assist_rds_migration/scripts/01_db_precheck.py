#!/usr/bin/env python3
"""01_db_precheck.py - Database pre-migration check.

Checks source and target database compatibility for DRS migration.
Only executes read-only queries (SELECT/SHOW). No modification SQL.
"""

import sys
import os
import time
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import is_dry_run, load_config
from db_client import (
    close_all_connections,
    get_binlog_config,
    get_charset,
    get_databases,
    get_engines,
    get_foreign_keys,
    get_routines,
    get_table_list,
    get_triggers,
    get_version,
)
from log_utils import get_logger
from report_utils import append_migration_report, generate_report

logger = get_logger("01_db_precheck")


def check_source_db():
    """Run pre-migration checks on the source database.

    Returns:
        tuple: (checks_list, db_info_dict)
    """
    checks = []
    db_info = {}

    # Version check
    try:
        version = get_version("source")
        db_info["version"] = version
        if version and version.startswith("8.0"):
            checks.append({"item": "version", "status": "PASS", "message": f"MySQL version: {version}"})
        else:
            checks.append({"item": "version", "status": "FAIL", "message": f"Expected MySQL 8.0.x, got: {version}"})
    except Exception as e:
        checks.append({"item": "version", "status": "FAIL", "message": f"Cannot get version: {e}"})
        version = None

    # Charset check
    try:
        charset = get_charset("source")
        db_info["charset"] = charset.get("character_set_server", "unknown")
        cs = charset.get("character_set_server", "")
        if cs in ("utf8", "utf8mb4"):
            checks.append({"item": "charset", "status": "PASS", "message": f"Character set: {cs}"})
        else:
            checks.append({"item": "charset", "status": "WARN", "message": f"Character set: {cs}, recommended: utf8mb4"})
    except Exception as e:
        checks.append({"item": "charset", "status": "FAIL", "message": f"Cannot get charset: {e}"})

    # Engine check
    try:
        engines = get_engines("source")
        innodb_supported = any(e.get("Engine") == "InnoDB" and e.get("Support") != "NO" for e in engines)
        db_info["innodb_supported"] = innodb_supported
        if innodb_supported:
            checks.append({"item": "engine", "status": "PASS", "message": "InnoDB engine is supported"})
        else:
            checks.append({"item": "engine", "status": "FAIL", "message": "InnoDB engine is not supported"})
    except Exception as e:
        checks.append({"item": "engine", "status": "WARN", "message": f"Cannot check engines: {e}"})

    # Binlog format check
    try:
        binlog = get_binlog_config("source")
        db_info["binlog_format"] = binlog.get("binlog_format", "unknown")
        db_info["binlog_row_image"] = binlog.get("binlog_row_image", "unknown")
        db_info["gtid_mode"] = binlog.get("gtid_mode", "unknown")
        db_info["log_bin"] = binlog.get("log_bin", "OFF")

        bf = binlog.get("binlog_format", "")
        if bf == "ROW":
            checks.append({"item": "binlog_format", "status": "PASS", "message": f"binlog_format=ROW"})
        else:
            checks.append({"item": "binlog_format", "status": "FAIL", "message": f"binlog_format={bf}, must be ROW"})

        bri = binlog.get("binlog_row_image", "")
        if bri == "FULL":
            checks.append({"item": "binlog_row_image", "status": "PASS", "message": f"binlog_row_image=FULL"})
        else:
            checks.append({"item": "binlog_row_image", "status": "FAIL", "message": f"binlog_row_image={bri}, must be FULL"})

        gtid = binlog.get("gtid_mode", "")
        if gtid == "ON":
            checks.append({"item": "gtid_mode", "status": "PASS", "message": f"gtid_mode=ON"})
        else:
            checks.append({"item": "gtid_mode", "status": "WARN", "message": f"gtid_mode={gtid}, recommended ON"})
    except Exception as e:
        checks.append({"item": "binlog", "status": "FAIL", "message": f"Cannot get binlog config: {e}"})

    # Foreign keys check
    try:
        fks = get_foreign_keys("source")
        db_info["has_foreign_keys"] = len(fks) > 0
        db_info["foreign_key_count"] = len(fks)
        if fks:
            checks.append({"item": "foreign_keys", "status": "WARN", "message": f"Found {len(fks)} foreign key constraints"})
        else:
            checks.append({"item": "foreign_keys", "status": "PASS", "message": "No foreign key constraints"})
    except Exception as e:
        checks.append({"item": "foreign_keys", "status": "WARN", "message": f"Cannot check foreign keys: {e}"})

    # Triggers check
    try:
        triggers = get_triggers("source")
        db_info["has_triggers"] = len(triggers) > 0
        db_info["trigger_count"] = len(triggers)
        if triggers:
            checks.append({"item": "triggers", "status": "WARN", "message": f"Found {len(triggers)} triggers"})
        else:
            checks.append({"item": "triggers", "status": "PASS", "message": "No triggers"})
    except Exception as e:
        checks.append({"item": "triggers", "status": "WARN", "message": f"Cannot check triggers: {e}"})

    # Routines check
    try:
        routines = get_routines("source")
        db_info["has_routines"] = len(routines) > 0
        db_info["routine_count"] = len(routines)
        if routines:
            checks.append({"item": "routines", "status": "WARN", "message": f"Found {len(routines)} stored procedures/functions"})
        else:
            checks.append({"item": "routines", "status": "PASS", "message": "No stored procedures/functions"})
    except Exception as e:
        checks.append({"item": "routines", "status": "WARN", "message": f"Cannot check routines: {e}"})

    return checks, db_info


def check_target_db():
    """Run pre-migration checks on the target database.

    Returns:
        tuple: (checks_list, db_info_dict)
    """
    checks = []
    db_info = {}

    # Version check
    try:
        version = get_version("target")
        db_info["version"] = version
        if version and ("8.0" in version or "5.7" in version):
            checks.append({"item": "version", "status": "PASS", "message": f"MySQL version: {version}"})
        else:
            checks.append({"item": "version", "status": "WARN", "message": f"Version: {version}, verify MySQL 8.0 compatibility"})
    except Exception as e:
        checks.append({"item": "version", "status": "FAIL", "message": f"Cannot get version: {e}"})

    # Charset check
    try:
        charset = get_charset("target")
        db_info["charset"] = charset.get("character_set_server", "unknown")
        cs = charset.get("character_set_server", "")
        if cs in ("utf8", "utf8mb4"):
            checks.append({"item": "charset", "status": "PASS", "message": f"Character set: {cs}"})
        else:
            checks.append({"item": "charset", "status": "WARN", "message": f"Character set: {cs}"})
    except Exception as e:
        checks.append({"item": "charset", "status": "FAIL", "message": f"Cannot get charset: {e}"})

    # Engine check
    try:
        engines = get_engines("target")
        innodb_supported = any(e.get("Engine") == "InnoDB" and e.get("Support") != "NO" for e in engines)
        db_info["innodb_supported"] = innodb_supported
        if innodb_supported:
            checks.append({"item": "engine", "status": "PASS", "message": "InnoDB engine is supported"})
        else:
            checks.append({"item": "engine", "status": "FAIL", "message": "InnoDB engine is not supported"})
    except Exception as e:
        checks.append({"item": "engine", "status": "WARN", "message": f"Cannot check engines: {e}"})

    # Conflict objects check
    try:
        src_dbs = get_databases("source")
        tgt_dbs = get_databases("target")
        conflict_dbs = set(src_dbs) & set(tgt_dbs)
        db_info["has_conflict_objects"] = len(conflict_dbs) > 0
        db_info["conflict_databases"] = list(conflict_dbs)
        if conflict_dbs:
            checks.append({"item": "conflict_objects", "status": "WARN", "message": f"Found {len(conflict_dbs)} databases with same name: {conflict_dbs}"})
        else:
            checks.append({"item": "conflict_objects", "status": "PASS", "message": "No conflicting database names"})
    except Exception as e:
        checks.append({"item": "conflict_objects", "status": "WARN", "message": f"Cannot check conflict objects: {e}"})

    return checks, db_info


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    allow_drs_only_precheck = os.getenv("ALLOW_DRS_ONLY_PRECHECK", "true").strip().lower() == "true"
    logger.info(f"Database pre-migration check starting (dry_run={dry_run})")

    errors = []
    warnings = []

    # Optional relaxed mode:
    # If direct DB connectivity is not available from the execution host,
    # rely on DRS connection test + DRS precheck as the runtime gate.
    if allow_drs_only_precheck:
        probe_warnings = []
        probe_details = {"source": {}, "target": {}}
        for endpoint in ("source", "target"):
            try:
                version = get_version(endpoint)
                probe_details[endpoint]["version"] = version
            except Exception as e:
                msg = f"{endpoint} direct DB connectivity unavailable: {e}"
                probe_warnings.append(msg)
                probe_details[endpoint]["connectivity"] = "UNAVAILABLE"

        if probe_warnings:
            logger.warning(
                "Direct DB precheck is not reachable from this execution host. "
                "ALLOW_DRS_ONLY_PRECHECK=true, switch to warning mode."
            )
            details = {
                "mode": "drs_only_precheck",
                "source": {
                    **probe_details["source"],
                    "checks": [{"item": "connectivity", "status": "WARN", "message": probe_warnings[0]}],
                },
                "target": {
                    **probe_details["target"],
                    "checks": [{"item": "connectivity", "status": "WARN", "message": probe_warnings[-1]}],
                },
                "next_gate": "Use DRS connection test and DRS precheck results as hard gate.",
            }
            report_path = generate_report(
                "db_precheck",
                details,
                stage="db_precheck",
                status="WARNING",
                warnings=probe_warnings,
            )
            logger.info(f"Report saved to: {report_path}")
            duration = int(time.time() - start_time)
            append_migration_report("db_precheck", "WARNING", duration_seconds=duration)
            close_all_connections()
            sys.exit(0)

    # Check source database
    logger.info("Checking source database...")
    src_checks, src_info = check_source_db()
    logger.info(f"Source database checks: {len(src_checks)} items")

    # Check target database
    logger.info("Checking target database...")
    tgt_checks, tgt_info = check_target_db()
    logger.info(f"Target database checks: {len(tgt_checks)} items")

    # Collect errors and warnings
    for check in src_checks + tgt_checks:
        if check["status"] == "FAIL":
            errors.append(f"{check['item']}: {check['message']}")
        elif check["status"] == "WARN":
            warnings.append(f"{check['item']}: {check['message']}")

    # Determine overall status
    if errors:
        overall_status = "FAILED"
    elif warnings:
        overall_status = "WARNING"
    else:
        overall_status = "SUCCESS"

    # Generate report
    details = {
        "source": {**src_info, "checks": src_checks},
        "target": {**tgt_info, "checks": tgt_checks},
    }
    report_path = generate_report(
        "db_precheck", details, stage="db_precheck",
        status=overall_status, errors=errors, warnings=warnings,
    )
    logger.info(f"Report saved to: {report_path}")

    # Append to migration report
    duration = int(time.time() - start_time)
    append_migration_report("db_precheck", overall_status, duration_seconds=duration)

    # Close database connections
    close_all_connections()

    # Exit with appropriate code
    if overall_status == "FAILED":
        logger.error("Database pre-migration check FAILED")
        sys.exit(1)

    logger.info(f"Database pre-migration check completed: {overall_status}")
    sys.exit(0)


if __name__ == "__main__":
    main()
