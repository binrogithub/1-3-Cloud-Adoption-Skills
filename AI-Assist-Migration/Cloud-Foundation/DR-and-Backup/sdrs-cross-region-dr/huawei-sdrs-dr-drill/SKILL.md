---
name: huawei-sdrs-dr-drill
version: 1.0.0
description: Consume validated SDRS protection setup, parse drill intent, validate replication readiness, define isolated drill scope, execute supervised DR drill, validate recovered resources, measure RPO/RTO, and produce drill report.
category: migration
risk_level: high
status: EXPERIMENTAL
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Cloud-Foundation
  family: DR-and-Backup
  service: SDRS
  canonical_name: Storage Disaster Recovery Service
  aliases:
    - SDR
    - SDRS
    - Storage Disaster Recovery Service
  risk_level: high
  status: EXPERIMENTAL
  verified_hcloud_version: 6.2.9
  sdrs_cli_support: NOT_AVAILABLE
  sdrs_mcp_support: NOT_AVAILABLE
  scope: dr_drill_only
  prerequisite_skill: huawei-sdrs-protection-setup
  next_skill: huawei-sdrs-failover-failback
---

# Purpose

Consume validated SDRS protection setup from huawei-sdrs-protection-setup, parse drill intent, validate replication readiness, define an isolated drill scope that does NOT modify production, obtain explicit approval, execute a supervised DR drill via manual console, validate recovered servers, disks, network, and application at the DR site, measure RPO and RTO, execute cleanup, and produce a drill report.

**DR DRILL IS NOT PRODUCTION FAILOVER.** A drill creates temporary resources for testing and must be cleaned up. It does not modify production traffic routing.

# Terminology

| Term | Canonical name | Notes |
|---|---|---|
| SDRS | Storage Disaster Recovery Service | Current canonical name [VERIFIED_FROM_DOCUMENTATION] |
| SDR | Storage Disaster Recovery | Legacy shorthand, alias only [INFERRED] |
| CBR | Cloud Backup and Recovery | Backup service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |

# Supported scenario

- Source: Validated SDRS protection setup (from huawei-sdrs-protection-setup)
- Target: DR site with temporary drill resources
- Mechanism: SDRS DR drill via manual console
- Operations: Drill execution, validation, cleanup
- Constraint: Does NOT modify production traffic, DNS, or routing

# When to use this skill

- Executing a periodic DR drill to validate protection effectiveness
- Measuring actual RPO and RTO in a non-production context
- Validating DR site server boot, disk consistency, and application functionality
- Testing DR procedures without affecting production

# When not to use this skill

- Setting up SDRS protection (use huawei-sdrs-protection-setup)
- Executing production failover (use huawei-sdrs-failover-failback)
- Executing failback (use huawei-sdrs-failover-failback)
- When protection is not yet established (run huawei-sdrs-protection-setup first)
- When automated SDRS execution is required (no CLI or MCP support exists)
- When the region pair is not supported by SDRS

# Required inputs

- Protection group ID (from huawei-sdrs-protection-setup output)
- Approval owner for drill operation

# Optional inputs

- Drill scope (which instances, which applications)
- Validation plan (what to verify at DR site)
- DNS isolation strategy
- RPO/RTO measurement method
- Cleanup plan
- Business validation criteria

# Required MCPs

None. No SDRS MCP exists. SDRS operations are performed via MANUAL console execution.

# Optional MCPs

- huaweicloud-pricing (for cost estimation of temporary drill resources)
- huaweicloud-ticket (for support ticket creation if issues arise)
- playwright (for console exploration and form field discovery only; NEVER for write operations)

# Tool selection policy

- Use hcloud CLI for read-only verification ONLY
- NEVER use hcloud for SDRS operations (SDRS is NOT available in hcloud CLI 6.2.9)
- NEVER invent commands like `hcloud SDR ...` or `hcloud SDRS ...`
- Use playwright ONLY for read-only console exploration; NEVER for write operations or dialog acceptance
- NEVER execute write operations without explicit approval
- NEVER modify production DNS, routing, or traffic during a drill

# Safety and approval gates

1. DR drill requires explicit approval (creates temporary DR resources)
2. DNS isolation must be confirmed before drill execution
3. No production traffic modification permitted
4. Cleanup plan must be defined before drill execution
5. No resource deletion is automatic (production or DR site)

# Rules

1. A DR drill is NOT equivalent to a production failover. A drill creates temporary resources for testing and must be cleaned up. It does not modify production traffic routing. [VERIFIED_FROM_DOCUMENTATION]

2. Before executing a drill, confirm protection is active and replication is healthy. A drill against degraded replication produces misleading results. [VERIFIED_FROM_DOCUMENTATION]

3. The drill scope must be explicitly defined: which instances, which applications, what validation criteria, and what cleanup procedure. [INFERRED]

4. DNS isolation is mandatory during a drill. The drill must NOT affect production DNS resolution. [INFERRED]

5. After drill completion, cleanup must remove all temporary drill resources. Verify cleanup completion. [INFERRED]

6. VERIFY AFTER EVERY STEP: each manual console action should be followed by a verification step. [INFERRED]

7. No write operations without explicit approval. [INFERRED]

8. Never include secrets in commands, examples, files, or logs. [INFERRED]

9. Do not continue when multiple ambiguous matches exist for a resource. Present all matches and request clarification. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| Protection group ID | Yes | From huawei-sdrs-protection-setup | Verify protection status is active |
| Replication status | Yes | All pairs replicating | Console verification |
| Approval owner | Yes | Authority for drill operation | Specified in intent |
| DNS isolation plan | Yes | Prevent production impact | Documented before drill |
| Cleanup plan | Yes | Remove drill resources after test | Documented before drill |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| Playwright | No | Console exploration | Integration availability check |
| mcp-capability-builder shared skill | Yes | Future SDRS MCP design | Path verification |

# Workflow

## STEP 1 — PARSE DRILL INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate drill intent including scope, validation criteria, and cleanup plan.

**Inputs**: Protection group ID, drill scope, validation plan, approval owner.

**Preconditions**: Protection setup completed (huawei-sdrs-protection-setup).

**Mechanism**: Parsing logic.

**Approval requirement**: None.

**Verification**: Confirm all required fields are present, protection group ID is valid.

**Expected result**: Complete drill intent object.

**Stop condition**: Protection group ID missing or invalid, critical information missing.

**Failure action**: STOP and request clarification.

**Evidence artifact**: `artifacts/sdrs-drill-intent.json`

## STEP 2 — VALIDATE REPLICATION READINESS

**Classification: ASSISTED**

**Objective**: Confirm all replication pairs are active, lag is within threshold, and protection group is healthy.

**Inputs**: Protection group ID.

**Preconditions**: Step 1 completed.

**Mechanism**: MANUAL console status check.

**Approval requirement**: None.

**Verification**: All replication pairs active, lag within threshold, protection group status is healthy.

**Expected result**: Replication readiness confirmation.

**Stop condition**: Replication not active, lag exceeds threshold, protection group unhealthy.

**Failure action**: STOP. Report replication issues. Recommend resolving before drill.

**Evidence artifact**: `artifacts/sdrs-drill-readiness.md`

## STEP 3 — DEFINE DRILL SCOPE

**Classification: AUTOMATED**

**Objective**: Define the isolated drill scope, validation plan, DNS isolation, and cleanup procedure.

**Inputs**: Drill intent, replication readiness.

**Preconditions**: Step 2 completed.

**Mechanism**: Plan generation.

**Approval requirement**: None (plan only).

**Verification**: Plan is complete, DNS isolation confirmed, cleanup procedure defined.

**Expected result**: DR drill plan ready for approval.

**Stop condition**: Cannot define DNS isolation, or cleanup procedure undefined.

**Failure action**: STOP. Report scope definition failure.

**Evidence artifact**: `artifacts/sdrs-drill-plan.md`

The drill plan must include:
- Defined scope (which instances, which applications)
- Isolation mechanism (does not modify production)
- Validation plan (what to verify at DR site)
- Cleanup plan (how to remove drill resources)
- DNS isolation (drill must not affect production DNS)
- Business validation criteria
- RPO and RTO measurement method
- Approval from approval_owner

## STEP 4 — OBTAIN APPROVAL

**Classification: MANUAL**

**Objective**: Obtain explicit approval for drill execution.

**Inputs**: Drill plan.

**Preconditions**: Step 3 completed.

**Mechanism**: Approval workflow.

**Approval requirement**: EXPLICIT.

**Verification**: Approval recorded with approver identity and timestamp.

**Expected result**: Drill approved for execution.

**Stop condition**: Approval denied.

**Failure action**: STOP. Do not execute drill.

**Evidence artifact**: `artifacts/sdrs-drill-approval.md`

## STEP 5 — EXECUTE DR DRILL

**Classification: MANUAL**

**Objective**: Execute the DR drill via manual console.

**Inputs**: Approved drill plan.

**Preconditions**: Step 4 approval obtained.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: Already obtained in Step 4.

**Verification**: Drill resources created at DR site.

**Expected result**: DR site servers started from replicated disks.

**Stop condition**: Drill creation fails, or DR server cannot boot.

**Failure action**: Report drill failure. Execute cleanup. Do NOT affect production.

**Evidence artifact**: `artifacts/sdrs-drill-execution.md**

IMPORTANT: A drill is NOT a production failover. Do not modify production DNS or routing.

## STEP 6 — VALIDATE DRILL RESULTS

**Classification: ASSISTED**

**Objective**: Validate recovered servers, disks, network, and application at the DR site.

**Inputs**: Drill execution results, validation plan.

**Preconditions**: Step 5 completed.

**Mechanism**: Manual verification and automated checks where possible.

**Approval requirement**: None.

**Verification**: All validation criteria pass.

**Expected result**: Drill validation report with pass/fail for each criterion.

**Stop condition**: Critical validation failure.

**Failure action**: Document failure. Proceed to cleanup.

**Evidence artifact**: `artifacts/sdrs-drill-validation.md`

Verify at DR site:
- Recovered servers boot successfully
- Disk state is consistent
- Application start order is correct
- Network connectivity is functional
- Security groups are applied correctly
- DNS isolation is maintained
- Data consistency is acceptable
- Application tests pass
- RPO is within target
- RTO is within target

## STEP 7 — MEASURE RPO AND RTO

**Classification: ASSISTED**

**Objective**: Measure actual RPO and RTO achieved during the drill.

**Inputs**: Drill timestamps, replication lag data.

**Preconditions**: Step 6 completed.

**Mechanism**: Calculation from timestamps and replication data.

**Approval requirement**: None.

**Expected result**: RPO and RTO measurements.

**Evidence artifact**: `artifacts/sdrs-drill-rpo-rto.md`

## STEP 8 — CLEANUP DRILL RESOURCES

**Classification: MANUAL**

**Objective**: Remove all temporary drill resources created during the drill.

**Inputs**: Drill plan, drill execution results.

**Preconditions**: Step 6 completed (or Step 5 failed).

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: None (cleanup of temporary resources).

**Verification**: All drill resources removed. DR site returned to pre-drill state.

**Expected result**: Drill cleanup complete.

**Stop condition**: Cleanup fails for some resources.

**Failure action**: Document remaining drill resources. Report manual cleanup required.

**Evidence artifact**: `artifacts/sdrs-drill-cleanup.md**

## STEP 9 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final drill report with results, measurements, and recommendations.

**Inputs**: All artifacts from Steps 1-8.

**Preconditions**: All completed steps.

**Mechanism**: Report generation logic.

**Approval requirement**: None.

**Expected result**: Final drill report.

**Evidence artifact**: `artifacts/sdrs-drill-report.md`

Generate: drill summary, validation results, RPO/RTO measurements, issues found, cleanup status, recommendations, next drill date, next skill reference (huawei-sdrs-failover-failback for production failover if drill was successful).

Do NOT delete production or DR site resources automatically.

# Scope boundary

This skill is responsible for DR drill execution ONLY. It MUST explicitly state:

**DR DRILL != PRODUCTION FAILOVER**

It MUST NOT perform:
- Production DNS cutover
- Planned failover
- Unplanned failover
- Failback

It may reference huawei-sdrs-failover-failback for production failover operations.

# Capability gap handling

Known capability gaps (drill-specific):
- GAP-SDR-001: No SDRS CLI support. Drill operations are MANUAL_CONSOLE. [NOT_AVAILABLE]
- GAP-SDR-002: No SDRS MCP exists. [NOT_AVAILABLE]
- GAP-SDR-004: Replication monitoring requires manual console checks. [NOT_AVAILABLE]

# Output artifacts

- artifacts/sdrs-drill-intent.json
- artifacts/sdrs-drill-readiness.md
- artifacts/sdrs-drill-plan.md
- artifacts/sdrs-drill-approval.md
- artifacts/sdrs-drill-execution.md
- artifacts/sdrs-drill-validation.md
- artifacts/sdrs-drill-rpo-rto.md
- artifacts/sdrs-drill-cleanup.md
- artifacts/sdrs-drill-report.md

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| Replication not active | Protection setup incomplete | Console status check | Complete protection setup first |
| Drill creation fails | Quotas or capacity | Console error | Check quotas, capacity at DR site |
| DR server cannot boot | Network, OS, or disk issue | Console error | Check DR site network, security groups, OS image |
| DNS isolation failure | DNS configuration error | DNS query test | Verify DNS isolation before drill |
| Cleanup incomplete | Resource dependencies | Console resource list | Manual cleanup of remaining resources |
| Console field differs from docs | Documentation lag | Console field inspection | Use console as source of truth |

See also: scenario-level `../references/known-issues.md`

# Failure handling

- Replication not active: Do not execute drill. Report to huawei-sdrs-protection-setup for remediation.
- Drill creation fails: Check quotas, capacity, protection status. Do not affect production.
- Drill server cannot boot: Check DR site network, security groups, OS image. Do not affect production.
- Cleanup failure: Document remaining resources. Report manual cleanup required. Do not delete production resources.

# Recovery procedure

1. If failure during drill execution: Drill resources may exist. Clean up drill resources manually. Verify production is unaffected. Document drill failure.
2. If failure during cleanup: Document remaining drill resources. These are temporary and do not affect production. Schedule manual cleanup.

# Evidence and traceability

- All manual console actions documented with timestamps and results
- Approval decisions recorded with approver identity and timestamp
- RPO and RTO measurements recorded
- DNS isolation verified and documented
- No secrets in any artifact

# Known limitations

- No SDRS CLI support in hcloud 6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations are MANUAL via console [NOT_AVAILABLE]
- Drill does not test actual DNS cutover [INFERRED]
- Drill cleanup may leave temporary resources if interrupted [INFERRED]
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending [VERSION_DEPENDENT]

# Status justification

Status: EXPERIMENTAL

Evidence:
- SDRS service is NOT available in hcloud CLI v6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations must be performed manually via console [NOT_AVAILABLE]
- No cloud-side tests were executed [NOT_VERIFIED]
- The workflow provides value as a controlled runbook for manual drill execution [INFERRED]
- Capability builder integration enables future MCP design [VERIFIED_FROM_CODE]
