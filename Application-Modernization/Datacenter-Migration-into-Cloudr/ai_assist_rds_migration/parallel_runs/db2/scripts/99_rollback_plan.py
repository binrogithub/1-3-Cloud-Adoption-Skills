#!/usr/bin/env python3
"""99_rollback_plan.py - Generate rollback plan for DRS migration.

Generates a comprehensive rollback plan document including:
- Trigger conditions
- Step-by-step rollback procedure
- Risk assessment
- Estimated rollback time
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_loader import get_source_db_config, get_target_db_config, is_dry_run
from log_utils import get_logger, mask_dict
from report_utils import append_migration_report, generate_report, load_report

logger = get_logger("99_rollback_plan")


def get_job_id():
    """Read job_id from the creation report (if exists)."""
    report = load_report("drs_job_create_report")
    if report:
        return report.get("details", {}).get("job_id")
    return None


def generate_rollback_steps(job_id):
    """Generate rollback steps.

    Args:
        job_id: DRS job ID (may be None if job not yet created).

    Returns:
        List of rollback step dictionaries.
    """
    steps = [
        {
            "step": 1,
            "action": "Stop DRS incremental sync",
            "description": "Call DRS API to stop the migration job, halting incremental data sync",
            "command": f"drs_client.stop_job('{job_id}')" if job_id else "drs_client.stop_job(job_id)",
            "risk": "LOW",
            "requires_approval": False,
            "estimated_time_minutes": 2,
        },
        {
            "step": 2,
            "action": "Verify source database is operational",
            "description": "Connect to source database and verify it is accepting connections and queries",
            "command": "db_client.execute_query('source', 'SELECT 1')",
            "risk": "LOW",
            "requires_approval": False,
            "estimated_time_minutes": 1,
        },
        {
            "step": 3,
            "action": "Switch application connections back to source database",
            "description": "Update application configuration to point database connections to the source RDS instance",
            "command": "Update application config: datasource.url -> source RDS endpoint",
            "risk": "HIGH",
            "requires_approval": True,
            "estimated_time_minutes": 10,
            "notes": "Requires application team coordination. May need restart of application services.",
        },
        {
            "step": 4,
            "action": "Verify application functionality with source database",
            "description": "Run application health checks and verify business operations are working",
            "command": "Application health check / smoke test",
            "risk": "MEDIUM",
            "requires_approval": False,
            "estimated_time_minutes": 5,
        },
        {
            "step": 5,
            "action": "Delete DRS migration job (optional cleanup)",
            "description": "Clean up the DRS migration job to avoid ongoing charges",
            "command": f"drs_client.delete_job('{job_id}')" if job_id else "drs_client.delete_job(job_id)",
            "risk": "LOW",
            "requires_approval": True,
            "estimated_time_minutes": 2,
            "notes": "Only execute after confirming application is stable on source database.",
        },
    ]
    return steps


def generate_risks():
    """Generate risk assessment for rollback.

    Returns:
        List of risk dictionaries.
    """
    return [
        {
            "id": "R001",
            "category": "DATA_LOSS",
            "severity": "MEDIUM",
            "description": "Data written to target database after cutover will be lost when switching back to source",
            "mitigation": "Capture and replay any post-cutover writes from target back to source before rollback",
            "status": "OPEN",
        },
        {
            "id": "R002",
            "category": "DOWNTIME",
            "severity": "HIGH",
            "description": "Application will experience downtime during connection switch",
            "mitigation": "Plan rollback during maintenance window; use blue-green deployment if possible",
            "status": "OPEN",
        },
        {
            "id": "R003",
            "category": "PERFORMANCE",
            "severity": "MEDIUM",
            "description": "Source database may experience increased load after rollback if traffic has grown",
            "mitigation": "Monitor source database performance closely after rollback; scale up if needed",
            "status": "OPEN",
        },
        {
            "id": "R004",
            "category": "COMPATIBILITY",
            "severity": "LOW",
            "description": "Application may need configuration changes to connect back to source database",
            "mitigation": "Keep source database connection configuration documented and readily available",
            "status": "MITIGATED",
        },
    ]


def main():
    """Main entry point."""
    start_time = time.time()
    dry_run = is_dry_run()
    logger.info(f"Generating rollback plan (dry_run={dry_run})")

    job_id = get_job_id()
    src_config = get_source_db_config()
    tgt_config = get_target_db_config()

    # Generate rollback plan
    trigger_conditions = [
        "DRS migration task fails and cannot be recovered",
        "Post-cutover validation reveals severe data inconsistency",
        "Business team confirms need to rollback",
        "Source database becomes unavailable during migration",
        "Migration exceeds acceptable time window",
    ]

    rollback_steps = generate_rollback_steps(job_id)
    risks = generate_risks()

    # Calculate estimated rollback time
    total_time = sum(step.get("estimated_time_minutes", 0) for step in rollback_steps)

    rollback_plan = {
        "trigger_conditions": trigger_conditions,
        "rollback_steps": rollback_steps,
        "estimated_rollback_time_minutes": total_time,
        "data_loss_risk": "MEDIUM",
        "source_database": {
            "host": src_config.get("host", "***"),
            "port": src_config.get("port", "***"),
        },
        "target_database": {
            "host": tgt_config.get("host", "***"),
            "port": tgt_config.get("port", "***"),
        },
        "notes": (
            "Rollback requires application team coordination to switch database connections. "
            "Plan rollback during a maintenance window. "
            "Any data written to the target database after cutover will need to be manually reconciled."
        ),
    }

    # Save rollback plan
    report_path = generate_report("rollback_plan", rollback_plan, stage="rollback_plan", status="SUCCESS")
    logger.info(f"Rollback plan saved to: {report_path}")

    # Also generate risk list
    from report_utils import generate_risk_list
    risk_path = generate_risk_list(risks)
    logger.info(f"Risk list saved to: {risk_path}")

    # Print summary
    logger.info("=== Rollback Plan Summary ===")
    logger.info(f"Trigger conditions: {len(trigger_conditions)}")
    logger.info(f"Rollback steps: {len(rollback_steps)}")
    logger.info(f"Estimated rollback time: {total_time} minutes")
    logger.info(f"Data loss risk: MEDIUM")
    logger.info(f"Risks identified: {len(risks)}")
    for step in rollback_steps:
        approval_tag = " [REQUIRES APPROVAL]" if step.get("requires_approval") else ""
        logger.info(f"  Step {step['step']}: {step['action']} (~{step.get('estimated_time_minutes', '?')}min){approval_tag}")

    duration = int(time.time() - start_time)
    append_migration_report("rollback_plan", "SUCCESS", duration_seconds=duration)

    logger.info("Rollback plan generation completed")
    sys.exit(0)


if __name__ == "__main__":
    main()
