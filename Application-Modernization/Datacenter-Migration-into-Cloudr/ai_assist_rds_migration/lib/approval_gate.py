#!/usr/bin/env python3
"""Approval gate module for DRS migration automation.

Checks for approval files before allowing critical operations.
"""

import sys
from pathlib import Path

from config_loader import APPROVALS_DIR, ensure_dirs
from log_utils import get_logger

logger = get_logger("approval_gate")


def check_approval(approval_name):
    """Check if an approval file exists.

    Args:
        approval_name: Name of the approval (e.g., APPROVED_CREATE_DRS_JOB).

    Returns:
        True if the approval file exists, False otherwise.
    """
    ensure_dirs()
    approval_path = APPROVALS_DIR / approval_name
    return approval_path.exists()


def require_approval(approval_name, operation_desc):
    """Require an approval before proceeding.

    If the approval file does not exist, log an error and exit.

    Args:
        approval_name: Name of the approval file.
        operation_desc: Human-readable description of the operation requiring approval.
    """
    if check_approval(approval_name):
        logger.info(f"Approval granted for: {operation_desc} (file: {approval_name})")
        return

    logger.error(
        f"APPROVAL_REQUIRED: Operation '{operation_desc}' requires approval. "
        f"Create file '{APPROVALS_DIR / approval_name}' to approve."
    )
    print(
        f"\nAPPROVAL REQUIRED: {operation_desc}\n"
        f"To approve, create the file:\n"
        f"  touch {APPROVALS_DIR / approval_name}\n",
        file=sys.stderr,
    )
    sys.exit(1)


def list_pending_approvals():
    """List all approval files and their status.

    Returns:
        Dictionary mapping approval names to their granted/denied status.
    """
    required_approvals = [
        ("APPROVED_CREATE_DRS_JOB", "Create DRS migration task"),
        ("APPROVED_START_DRS_JOB", "Start DRS migration task"),
        ("APPROVED_CUTOVER", "Execute cutover"),
    ]
    result = {}
    for name, desc in required_approvals:
        result[name] = {
            "description": desc,
            "granted": check_approval(name),
            "path": str(APPROVALS_DIR / name),
        }
    return result
