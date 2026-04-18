---
name: cfw-finance-skill
description: Use this skill when configuring Huawei Cloud Firewall (CFW) for financial institutions such as banks, insurance companies, or fintech platforms. Triggers include: CFW setup for banking, PCI DSS compliance firewall, financial network segmentation, IPS configuration for finance, ACL rules for banking services, intrusion prevention for payment systems, cloud firewall hardening for regulated industries, or any scenario requiring enterprise-grade firewall protection with financial regulatory compliance (PCI DSS, ISO 27001, NIST, local banking regulations).
---

# CFW Finance Skill

## Overview

This skill provides a structured, repeatable method for configuring Huawei Cloud Firewall (CFW) to meet the stringent security and compliance requirements of financial institutions. It covers the complete lifecycle from instance creation through security policy configuration, IPS tuning, access control, logging, and alarm setup — all aligned with PCI DSS, ISO 27001, NIST Cybersecurity Framework, and regional banking regulations.

The skill is designed for AI agent invocation, enabling rapid, compliant CFW deployment without manual console operations.

## Use This Skill When

- Deploying CFW for a bank, insurance, fintech, or payment processor
- Configuring intrusion prevention for financial transaction systems
- Implementing network segmentation for PCI DSS compliance
- Setting up ACL rules for banking services (HTTPS, API gateways, internal networks)
- Hardening cloud firewall for regulated financial workloads
- Enabling logging, monitoring, and alarm for audit readiness
- Migrating financial workloads to Huawei Cloud and needing perimeter protection
- An AI agent needs to automate CFW configuration end-to-end

## Quick Start

### Prerequisites

- Huawei Cloud CLI (`hcloud`) installed and authenticated
- CFW instance created (or use the script to create one)
- Region and project ID identified
- IAM permissions: `cfw:*:*`, `vpc:*:*`, `eip:*:*`, `lts:*:*`

### Default Workflow

```
1. Validate prerequisites          → scripts/cfw_preflight_check.sh
2. Create/verify CFW instance       → scripts/cfw_create_instance.sh
3. Configure ACL rules (finance)    → scripts/cfw_finance_acl_rules.sh
4. Enable IPS protection mode       → scripts/cfw_ips_configure.sh
5. Enable virtual patching          → scripts/cfw_ips_configure.sh
6. Enable LTS logging               → scripts/cfw_logging_configure.sh
7. Configure alarms                 → scripts/cfw_alarm_configure.sh
8. Validate configuration           → scripts/cfw_validate_config.sh
```

### One-Command Deployment

```bash
bash scripts/cfw_finance_deploy.sh \
  --region="<region>" \
  --fw-instance-id="<fw_instance_id>" \
  --object-id="<object_id>"
```

## Core Rules

### R1: Defense-in-Depth Layering

CFW must implement all four security layers for financial workloads:

| Layer | Scope | CFW Feature |
|-------|-------|-------------|
| L1 - Network | IP filtering, geo-blocking, rate limiting | ACL rules |
| L2 - Transport | Port and protocol control | ACL service rules |
| L3 - Application | App identification and control | Application ID |
| L4 - Content | IPS, anti-virus, URL filtering | IPS + AV + URL |

### R2: IPS Must Be in Protection Mode

Financial institutions **must not** run IPS in observation mode in production. The default must be **strict protection mode (mode=1)**. Observation mode is only acceptable in pre-production validation.

### R3: Virtual Patching Must Be Enabled

Zero-day vulnerability protection via virtual patching is mandatory for financial workloads. This provides immediate protection before vendor patches can be applied.

### R4: Default Deny for Inbound Traffic

All inbound ACL rules must follow deny-first ordering:
1. Explicit deny rules (malicious sources, high-risk regions)
2. Explicit allow rules (legitimate services only)
3. Implicit default deny

### R5: HTTPS-Only for Banking Services

Banking customer-facing services must use HTTPS (port 443). HTTP (port 80) rules must be limited to redirect-only or internal services, never for transaction processing.

### R6: Comprehensive Logging

All log types must be enabled with retention periods meeting financial audit requirements:

| Log Type | Minimum Retention | Storage |
|----------|-------------------|---------|
| Attack Logs | 365 days | LTS + OBS |
| IPS Logs | 365 days | LTS + OBS |
| ACL Logs | 180 days | LTS |
| Flow Logs | 90 days | LTS |
| System Logs | 90 days | LTS |

### R7: Alarm Configuration

All three alarm types must be enabled for financial workloads:
- **Attack alarms**: CRITICAL, HIGH, MEDIUM severity
- **Bandwidth alarms**: Threshold-based alerts
- **Resource alarms**: Capacity warnings

### R8: No Credentials in Scripts

All scripts must use environment variables or IAM authentication. Never hardcode AK/SK, passwords, or tokens. Use `<placeholder>` patterns in documentation.

## Workflow Decision Tree

| Task Shape | Route | Reference |
|------------|-------|-----------|
| New CFW instance for bank | Full deploy workflow | [references/finance-compliance.md](references/finance-compliance.md) |
| Add ACL rules to existing CFW | ACL-only workflow | [references/acl-rule-patterns.md](references/acl-rule-patterns.md) |
| IPS tuning for payment systems | IPS-only workflow | [references/ips-finance-tuning.md](references/ips-finance-tuning.md) |
| Enable logging and alarms | Monitoring workflow | [references/logging-and-alarm.md](references/logging-and-alarm.md) |
| Compliance audit check | Validation workflow | scripts/cfw_validate_config.sh |
| Troubleshoot CFW issues | Diagnostic workflow | [references/troubleshooting.md](references/troubleshooting.md) |

## Default Deliverables

1. **CFW instance** running with Standard or Professional edition
2. **ACL rule set** with finance-specific allow/deny rules
3. **IPS configuration** in strict protection mode with virtual patching
4. **LTS logging** enabled with finance-grade retention
5. **Alarm configuration** for attack, bandwith, and resource events
6. **Validation report** confirming all compliance checks pass
7. **Configuration audit trail** for regulatory review

## Script Use

| Script | Purpose | Usage |
|--------|---------|-------|
| `cfw_preflight_check.sh` | Validate prerequisites and CLI auth | `bash scripts/cfw_preflight_check.sh --region=<region>` |
| `cfw_create_instance.sh` | Create CFW instance with finance defaults | `bash scripts/cfw_create_instance.sh --region=<region> --name=<name>` |
| `cfw_finance_acl_rules.sh` | Apply finance-specific ACL rules | `bash scripts/cfw_finance_acl_rules.sh --region=<region> --fw-instance-id=<id> --object-id=<id>` |
| `cfw_ips_configure.sh` | Enable IPS protection mode + virtual patching | `bash scripts/cfw_ips_configure.sh --region=<region> --object-id=<id>` |
| `cfw_logging_configure.sh` | Enable LTS logging | `bash scripts/cfw_logging_configure.sh --region=<region> --fw-instance-id=<id>` |
| `cfw_alarm_configure.sh` | Configure all alarm types | `bash scripts/cfw_alarm_configure.sh --region=<region> --fw-instance-id=<id>` |
| `cfw_validate_config.sh` | Validate full configuration compliance | `bash scripts/cfw_validate_config.sh --region=<region> --fw-instance-id=<id> --object-id=<id>` |
| `cfw_finance_deploy.sh` | One-command full deployment | `bash scripts/cfw_finance_deploy.sh --region=<region> --fw-instance-id=<id> --object-id=<id>` |

## Reference Use

- **[finance-compliance.md](references/finance-compliance.md)**: PCI DSS, ISO 27001, NIST mapping to CFW features
- **[acl-rule-patterns.md](references/acl-rule-patterns.md)**: Finance-specific ACL rule templates and patterns
- **[ips-finance-tuning.md](references/ips-finance-tuning.md)**: IPS rule categories and tuning for financial workloads
- **[logging-and-alarm.md](references/logging-and-alarm.md)**: Logging retention and alarm configuration for audit
- **[troubleshooting.md](references/troubleshooting.md)**: Common CFW issues and diagnostic procedures

## Validation Gates

| Gate | Check | Pass Criteria |
|------|-------|---------------|
| G1 | CFW instance running | `status == 2` |
| G2 | ACL rules present | `total_rules >= 3` |
| G3 | IPS protection mode | `mode == 1` (strict) |
| G4 | Virtual patching | `virtual_patches_status == 1` |
| G5 | Basic defense | `basic_defense_status == 1` |
| G6 | LTS logging | `lts_enable == 1` |
| G7 | Attack alarms | `enable_status == 1` for type 0 |
| G8 | Bandwidth alarms | `enable_status == 1` for type 1 |
| G9 | Resource alarms | `enable_status == 1` for type 2 |

## Sanitization Rules

- Never output real AK/SK, project IDs, or instance IDs in deliverables
- Replace all identifiers with `<placeholder>` patterns
- Strip region-specific endpoints from examples
- Do not include customer names, account numbers, or internal hostnames
- All scripts must read credentials from environment variables only

## Response Shape

When this skill is invoked, structure the response as:

```
1. Configuration status summary (table)
2. Validation gate results (pass/fail)
3. Next steps (if any gates failed)
4. Compliance mapping (which requirements are met)
```

## When Not to Overcomplicate

- For non-financial workloads, use the standard CFW configuration instead
- For development/test environments, observation mode IPS is acceptable
- If only a single service needs protection, a minimal ACL rule set suffices
- Do not add geo-blocking rules unless explicitly required by policy
- Do not create custom IPS signatures unless existing ones are insufficient
