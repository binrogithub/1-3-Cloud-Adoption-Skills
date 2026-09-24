---
name: autoops-metrics-observer
description: Query a configured Prometheus metric profile through the AutoOps Project Manager.
version: 1
allowed_roles: [metrics-observer]
---

# AutoOps Metrics Observer (E04)

Use the published `metrics.query.v1` capability through `#autoops-project-manager`.
The adapter accepts a service and a configured profile such as `service_up`,
`service_errors`, or `service_latency`; it never accepts arbitrary PromQL.

This role is read-only. It cannot run a shell command, call Rundeck, execute
Ansible, modify Prometheus, or start a recovery action. A successful HTTP query
with an empty result is `empty`, not proof that the service is healthy. Report
the profile, effective time window, sample timestamps, and `evidence_ref`.
