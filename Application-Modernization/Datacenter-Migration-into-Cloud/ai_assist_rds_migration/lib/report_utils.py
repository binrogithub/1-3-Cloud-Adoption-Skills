#!/usr/bin/env python3
"""Report generation utilities for DRS migration automation."""

import json
import sys
from datetime import datetime
from pathlib import Path

from config_loader import REPORTS_DIR, ensure_dirs, is_dry_run


def generate_report(report_name, data, stage=None, status=None, errors=None, warnings=None):
    """Generate a JSON format report.

    Args:
        report_name: Name of the report (used as filename).
        data: Report details data.
        stage: Migration stage name.
        status: Overall status (SUCCESS/FAILED/WARNING).
        errors: List of error messages.
        warnings: List of warning messages.

    Returns:
        Path to the generated report file.
    """
    ensure_dirs()
    report = {
        "report_name": report_name,
        "timestamp": datetime.now().isoformat(),
        "dry_run": is_dry_run(),
        "stage": stage or report_name,
        "status": status or "SUCCESS",
        "details": data,
        "errors": errors or [],
        "warnings": warnings or [],
    }
    report_path = REPORTS_DIR / f"{report_name}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return report_path


def append_migration_report(stage, status, details=None, duration_seconds=None):
    """Append a stage result to the overall migration report.

    Args:
        stage: Stage name.
        status: Stage status (SUCCESS/FAILED/WARNING).
        details: Additional details for this stage.
        duration_seconds: Duration of this stage in seconds.
    """
    ensure_dirs()
    report_path = REPORTS_DIR / "migration_report.json"

    # Load existing report or create new one
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    else:
        report = {
            "report_name": "migration_report",
            "timestamp": datetime.now().isoformat(),
            "dry_run": is_dry_run(),
            "source": {
                "host": "149.232.136.255",
                "port": 3306,
                "version": "8.0",
                "instance_type": "rds_ha",
            },
            "target": {
                "host": "***",
                "port": "***",
                "version": "8.0",
            },
            "stages": [],
            "overall_status": "IN_PROGRESS",
            "job_id": None,
            "errors": [],
            "warnings": [],
        }

    # Append stage
    stage_entry = {
        "stage": stage,
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    if duration_seconds is not None:
        stage_entry["duration_seconds"] = duration_seconds
    if details:
        stage_entry["details"] = details
    report["stages"].append(stage_entry)

    # Update overall status
    if status == "FAILED":
        report["overall_status"] = "FAILED"
    elif status == "WARNING" and report["overall_status"] != "FAILED":
        report["overall_status"] = "WARNING"
    elif all(s["status"] == "SUCCESS" for s in report["stages"]):
        report["overall_status"] = "SUCCESS"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)


def update_migration_report_job_id(job_id):
    """Update the job_id in the migration report.

    Args:
        job_id: DRS job ID.
    """
    report_path = REPORTS_DIR / "migration_report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        report["job_id"] = job_id
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)


def generate_risk_list(risks):
    """Generate a risk list report.

    Args:
        risks: List of risk dictionaries, each containing:
            - id: Risk ID (e.g., R001)
            - category: Risk category
            - severity: HIGH/MEDIUM/LOW
            - description: Risk description
            - mitigation: Mitigation strategy
            - status: OPEN/MITIGATED/ACCEPTED

    Returns:
        Path to the generated risk list file.
    """
    ensure_dirs()
    risk_report = {
        "report_name": "risk_list",
        "timestamp": datetime.now().isoformat(),
        "risks": risks,
    }
    risk_path = REPORTS_DIR / "risk_list.json"
    with open(risk_path, "w", encoding="utf-8") as f:
        json.dump(risk_report, f, indent=2, ensure_ascii=False, default=str)
    return risk_path


def load_report(report_name):
    """Load an existing report by name.

    Args:
        report_name: Name of the report (without .json extension).

    Returns:
        Dictionary with report contents, or None if not found.
    """
    report_path = REPORTS_DIR / f"{report_name}.json"
    if not report_path.exists():
        return None
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


def report_status_is(report_name, expected_status):
    """Check if a report's status matches the expected status.

    Args:
        report_name: Name of the report.
        expected_status: Expected status value.

    Returns:
        True if the report exists and its status matches, False otherwise.
    """
    report = load_report(report_name)
    if report is None:
        return False
    return report.get("status") == expected_status


def report_has_no_fail(report_name):
    """Check if a report has no FAIL items in its details.

    Args:
        report_name: Name of the report.

    Returns:
        True if the report exists and has no FAIL items, False otherwise.
    """
    report = load_report(report_name)
    if report is None:
        return False
    errors = report.get("errors", [])
    if errors:
        return False
    # Check details for FAIL status items
    details = report.get("details", {})
    if isinstance(details, dict):
        for key, value in details.items():
            if isinstance(value, dict):
                checks = value.get("checks", [])
                for check in checks:
                    if check.get("status") == "FAIL":
                        return False
    return True
