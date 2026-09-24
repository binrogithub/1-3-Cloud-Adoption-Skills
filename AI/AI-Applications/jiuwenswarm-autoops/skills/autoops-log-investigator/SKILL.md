---
name: autoops-log-investigator
description: Access the E05 Log Investigator through the constrained AutoOps Project Manager.
version: 1
allowed_roles: [log-investigator]
---

# AutoOps Log Investigator

Route log investigation through `#autoops-project-manager`. For an application
scope, supply a bounded published `--service` name. For “Linux system logs” or
“本机日志”, omit the service so ProjectManager uses the published host-system
scope. This role is read-only and must not perform a repair or service restart.

For a read-only workflow node, use only the published text/terminal log route
needed for the task and then submit the structured result. Do not invoke vision
or image tools, browser tools, code tests, skill evolution, todo management, file
writes, or unrelated exploratory tools. MaaS text models do not accept image
payloads, and log diagnosis never requires them.
