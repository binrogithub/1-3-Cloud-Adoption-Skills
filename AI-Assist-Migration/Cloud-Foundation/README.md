# Cloud Foundation

Complete toolkit for the foundational cloud setup and operations that enable migration and modernization workloads on Huawei Cloud. Covers automation and IaC, DevOps pipelines, landing zone design, operational excellence, and disaster recovery.

---

## What This Package Covers

### The Problem

Before migration workloads can run, you need:

- **Automation tooling** -- hcloud CLI, Terraform, and standardized scripts for repeatable operations
- **DevOps pipelines** -- CodeArts projects, CI/CD pipelines, code repos, build, deploy, and test management
- **Landing zone** -- Multi-account structure, organization governance, IAM, Identity Center, and guardrails
- **Operational excellence** -- Monitoring, alerting, AIOps, inspection automation, and third-party tool integration
- **DR and backup** -- Backup strategy, disaster recovery design, failover planning, and continuity exercises

### The Solution: Skills Organized by Foundation Domain

```
Cloud-Foundation/
|
|-- Automation-and-IaC/                   Automation scripts, Terraform, CLI tooling
|   |-- hcloud-cli/                       KooCLI setup and usage skill
|   +-- huaweicloud-terraform-planner/    Terraform planning and code generation
|
|-- CodeArts-Overview/                    DevOps pipelines and project management
|   |-- huawei-codearts-project-design/   CodeArts Req project creation
|   +-- huawei-codearts-devops-operations/ Repo, Build, Deploy, Pipeline management
|
|-- Landing-Zone-and-Organization-Management/  Multi-account, IAM, governance
|   +-- multi-account-landing-zone/       Landing zone blueprint design
|
|-- Operations-AIOps-and-Tool-Interconnection/  Monitoring, alerting, AIOps
|
+-- DR-and-Backup/                        Backup, DR, failover, continuity
    |-- cbr-backup-restore/               CBR backup and restore operations
    +-- sdrs-cross-region-dr/             SDRS cross-region disaster recovery
```

---

## Scenarios

### Automation and IaC

Automation scripts, Terraform infrastructure-as-code, and CLI tooling for standardized cloud operations.

| Skill | Description |
|-------|-------------|
| hcloud-cli | KooCLI setup, configuration, and usage patterns |
| huaweicloud-terraform-planner | Terraform code generation with provider schema discovery |

See [Automation-and-IaC/README.md](./Automation-and-IaC/README.md) for details.

### CodeArts Overview

Design, create, and operate Huawei Cloud CodeArts projects and DevOps pipelines using hcloud CLI. Covers project design (CodeArts Req) and DevOps operations (Repo, Check, Build, Artifact, TestPlan, Deploy, Pipeline).

| Skill | Description |
|-------|-------------|
| huawei-codearts-project-design | Create and configure CodeArts Req projects, members, and boards |
| huawei-codearts-devops-operations | Manage repos, builds, deployments, and pipelines |

See [CodeArts-Overview/README.md](./CodeArts-Overview/README.md) for details.

### Landing Zone and Organization Management

Multi-account landing zone design, organization governance, IAM, Identity Center, and guardrails.

| Skill | Description |
|-------|-------------|
| multi-account-landing-zone | Landing zone blueprint with account structure, IAM, and guardrails |

See [Landing-Zone-and-Organization-Management/README.md](./Landing-Zone-and-Organization-Management/README.md) for details.

### Operations, AIOps, and Tool Interconnection

Operational excellence through deterministic operations, automation, AIOps practices, and third-party tool integration.

See [Operations-AIOps-and-Tool-Interconnection/README.md](./Operations-AIOps-and-Tool-Interconnection/README.md) for details.

### DR and Backup

Backup strategy, disaster recovery design, failover planning, and continuity exercises for production workloads.

| Skill | Description |
|-------|-------------|
| cbr-backup-restore | CBR backup and restore with policy management and verification |
| sdrs-cross-region-dr | SDRS cross-region DR with protection groups, failover, and failback |

See [DR-and-Backup/README.md](./DR-and-Backup/README.md) for details.

---

## Installation

Each sub-scenario has its own installation instructions. The general pattern:

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r <scenario>/<skill-name> ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r <scenario>/<skill-name> ~/.hermes/skills/foundation/
```

---

## Requirements

| Component | Requirement |
|------------|-----------|
| hcloud CLI | Installed and configured with AK/SK |
| Terraform | Installed (for IaC and landing zone skills) |
| Huawei Cloud | Account with appropriate service permissions |
| AI Agent | OpenCode / Hermes / Claude Code (optional) |

---

*Domains: Automation, DevOps, Landing Zone, Operations, DR*
*Tools: hcloud CLI, Terraform, CodeArts, CBR, SDRS*
*Target: Huawei Cloud foundation services*
