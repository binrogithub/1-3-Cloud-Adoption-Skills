---
name: runbook.execute
version: 1
allowed_roles: [runbook-operator]
executor: rundeck
write: true
---

# runbook.execute

Accept only a configured job name and its schema-validated options. The adapter records intent before submission, never accepts commands or playbook paths, and does not resubmit an unknown request. Return `external_execution_id`, status, time, and bounded output summary.
