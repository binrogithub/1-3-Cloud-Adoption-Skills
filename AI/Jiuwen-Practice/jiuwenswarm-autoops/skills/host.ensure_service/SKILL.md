---
name: host.ensure_service
version: 1
allowed_roles: [ansible-operator]
executor: rundeck
authorization_requirement: preauthorized-host-service-action
---

# host.ensure_service

This capability will be invoked through E01 `runbook.execute` only. It accepts a host and service only when both match the published policy and authorization has not expired. It never accepts a playbook path, shell command, package name, or an arbitrary service name.
