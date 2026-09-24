---
name: autoops-runbook-operator
description: Access an allowlisted E01 Rundeck runbook through the AutoOps Project Manager.
version: 1
allowed_roles: [runbook-operator]
---

# AutoOps Runbook Operator

Route runbook work through `#autoops-project-manager` with a published job name and target. Project Manager requires an operator-created, task-scoped approval record and its `--authorization-id` before E01 submission; a model-added `--execute` is never sufficient.

For a read-only workflow node, use only the published text/terminal route needed
for the task and then submit the structured result. Do not invoke vision or image
tools, browser tools, code tests, skill evolution, todo management, file writes,
or unrelated exploratory tools. A read-only inspection must never change host state.
