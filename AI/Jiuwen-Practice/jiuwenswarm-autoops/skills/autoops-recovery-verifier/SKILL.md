---
name: autoops-recovery-verifier
description: Verify an approved AutoOps service recovery through the constrained ProjectManager flow.
version: 1
allowed_roles: [recovery-verifier]
---

# AutoOps Recovery Verifier

Use the published verification adapter only. It is read-only and cannot restart,
stop, install, configure, or otherwise change a service.

Verification is valid only when the current TUI session already contains the
recovery `task_id`, `step_id`, target, and service. If the operator merely says
that a recovery was executed but this session has no such task context, return a
non-empty `Continuity Gap` report and stop. Do not list tasks, inspect SQLite,
read files, search scripts, or invent identifiers to reconstruct state.

Invoke:

`python3 /root/Jiuwenswarm_AutoOps/scripts/verify-service-recovery.py --task-id "<task-id>" --step-id "verify-service" --target "<target>" --service "autoops-demo"`

Report the returned `verification_status` separately from the preceding Runbook
execution status. `INCONCLUSIVE` is not a successful recovery.
