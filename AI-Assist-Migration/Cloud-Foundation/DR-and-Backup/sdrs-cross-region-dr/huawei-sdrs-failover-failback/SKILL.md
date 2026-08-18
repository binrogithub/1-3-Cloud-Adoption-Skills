---
name: huawei-sdrs-failover-failback
version: 1.0.0
description: Parse failover intent, distinguish planned vs unplanned, validate last replication state, execute supervised failover under CRITICAL approval, validate DR site, prevent split brain, execute reverse reprotection, plan and execute failback under separate approval, and produce closure report.
category: migration
risk_level: critical
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
  risk_level: critical
  status: EXPERIMENTAL
  verified_hcloud_version: 6.2.9
  sdrs_cli_support: NOT_AVAILABLE
  sdrs_mcp_support: NOT_AVAILABLE
  scope: failover_and_failback_only
  prerequisite_skill: huawei-sdrs-protection-setup
---

# Purpose

Parse failover intent, distinguish planned vs unplanned failover, validate last replication state, evaluate primary site condition, produce impact plan, obtain CRITICAL approval, execute supervised failover via manual console, validate DR site, measure RPO/RTO, prevent split brain, plan and execute reverse reprotection, plan and execute failback under separate approval, plan DNS restoration, and produce closure report.

# Terminology

| Term | Canonical name | Notes |
|---|---|---|
| SDRS | Storage Disaster Recovery Service | Current canonical name [VERIFIED_FROM_DOCUMENTATION] |
| SDR | Storage Disaster Recovery | Legacy shorthand, alias only [INFERRED] |
| CBR | Cloud Backup and Recovery | Backup service, NOT equivalent to SDRS [VERIFIED_FROM_DOCUMENTATION] |

# Supported scenario

- Source: Validated SDRS protection setup (from huawei-sdrs-protection-setup)
- Target: DR site assuming production role (failover), then original site (failback)
- Mechanism: SDRS planned/unplanned failover, reverse reprotection, and failback via manual console
- Operations: Planned failover, unplanned failover, reverse reprotection, failback
- Risk: CRITICAL — production traffic shift

# When to use this skill

- Executing a planned failover when production is accessible and applications can be quiesced
- Executing an unplanned failover when the primary site is confirmed unavailable or irrecoverable
- Re-establishing reverse replication (reverse reprotection) after failover
- Returning production to the original site (failback)

# When not to use this skill

- Setting up SDRS protection (use huawei-sdrs-protection-setup)
- Executing a DR drill (use huawei-sdrs-dr-drill)
- When protection is not yet established (run huawei-sdrs-protection-setup first)
- When automated SDRS execution is required (no CLI or MCP support exists)
- When the region pair is not supported by SDRS
- When a DR drill is sufficient (use huawei-sdrs-dr-drill instead)

# Required inputs

- Protection group ID (from huawei-sdrs-protection-setup output)
- Failover type: planned or unplanned
- Approval owner for failover operations

# Optional inputs

- Impact plan (affected services, expected downtime, DNS changes, rollback feasibility, data-loss risk)
- DNS cutover strategy
- Recovery order for multi-tier applications
- Failback expectation
- Data retention requirement

# Required MCPs

None. No SDRS MCP exists. SDRS operations are performed via MANUAL console execution.

# Optional MCPs

- huaweicloud-pricing (for cost estimation)
- huaweicloud-ticket (for support ticket creation when issues arise)
- huaweicloud-deploy (for VPC, subnet, security group prerequisites only; NOT for SDRS resources)
- playwright (for console exploration and form field discovery only; NEVER for write operations)

# Tool selection policy

- Use hcloud CLI for read-only verification ONLY
- NEVER use hcloud for SDRS operations (SDRS is NOT available in hcloud CLI 6.2.9)
- NEVER invent commands like `hcloud SDR ...` or `hcloud SDRS ...`
- Use huaweicloud-deploy ONLY for VPC, subnet, security group prerequisites; do NOT declare SDRS support
- Use playwright ONLY for read-only console exploration; NEVER for write operations or dialog acceptance
- NEVER execute write operations without explicit approval
- NEVER hardcode protection group IDs, instance IDs, volume IDs, or gateway IDs
- NEVER update DNS automatically
- NEVER delete production or DR resources automatically

# Safety and approval gates

1. Planned failover requires MANDATORY_EXPLICIT_APPROVAL with impact plan (CRITICAL operation)
2. Unplanned failover requires MANDATORY_EXPLICIT_APPROVAL with impact plan (CRITICAL operation)
3. Reverse reprotection requires explicit approval (changes replication direction)
4. Failback requires explicit approval with separate plan (CRITICAL operation)
5. DNS changes require explicit approval and manual execution (never automatic)
6. No resource deletion is automatic (production or DR site)

# Rules

1. Differentiate clearly between: planned failover (controlled switch, production accessible, lower data-loss risk) and unplanned failover (emergency switch, primary site unavailable, higher data-loss risk). These are distinct operations with different prerequisites, risks, and approval requirements. [VERIFIED_FROM_DOCUMENTATION]

2. Unplanned failover must be used ONLY when the condition of the primary site is confirmed to be unavailable or irrecoverable. It carries higher data-loss risk because the last replication state may be uncertain. [VERIFIED_FROM_DOCUMENTATION]

3. Before failover, confirm the behavior and accessibility of the secondary (DR-site) resources. The DR-site server may be in a stopped state and must be started after failover. Verify that the DR-site network, security groups, and EIP are configured correctly. [VERIFIED_FROM_DOCUMENTATION]

4. Reverse reprotection is NOT equivalent to failback. Reverse reprotection re-establishes replication in the reverse direction (DR site to production site) after failover. Failback is the full process of returning production to the original site, which includes reverse reprotection, synchronization validation, and controlled switchback. [VERIFIED_FROM_DOCUMENTATION]

5. Failback requires a separate plan, synchronization validation, and explicit approval. Do not assume failback is automatic or immediate after reverse reprotection. [VERIFIED_FROM_DOCUMENTATION]

6. Do not update DNS automatically. DNS cutover must be planned, approved, and executed manually or through a separate controlled process; automated DNS changes during failover carry significant risk. [INFERRED]

7. Do not delete production or DR resources automatically. Preserve both sites until explicit cleanup approval; premature deletion may cause irreversible data loss. [INFERRED]

8. Prevent split brain: after failover, ensure the original primary site cannot serve traffic independently. Verify that only one site is active at a time. [INFERRED]

9. Failover requires explicit approval and a documented impact plan including: affected services, expected downtime, DNS changes, rollback feasibility, and data-loss risk assessment. [INFERRED]

10. VERIFY AFTER EVERY STEP: each manual console action should be followed by a verification step. [INFERRED]

11. No hardcoded IDs in any artifact, command, or example. [INFERRED]

12. Do not continue when multiple ambiguous matches exist for a resource. Present all matches and request clarification. [INFERRED]

13. No write operations without explicit approval. [INFERRED]

14. Never include secrets in commands, examples, files, or logs. [INFERRED]

15. Stop on split-brain uncertainty. If both sites appear active and the true production site is ambiguous, do not proceed with either failover or failback. [INFERRED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| Protection group ID | Yes | From huawei-sdrs-protection-setup | Verify protection status is active |
| Replication status | Yes | All pairs replicating | Console verification |
| Failover type | Yes | Planned or unplanned | Specified in intent |
| Approval owner | Yes | Authority for critical operations | Specified in intent |
| Impact plan | Yes | Affected services, downtime, DNS, rollback | Documented before failover |
| DNS cutover plan | Yes | Manual DNS change procedure | Documented before failover |
| huaweicloud-pricing MCP | No | Cost estimation | MCP availability check |
| huaweicloud-ticket MCP | No | Support ticket creation | MCP availability check |
| huaweicloud-deploy MCP | No | Infrastructure prerequisites (VPC/SG) | MCP availability check |
| Playwright | No | Console exploration | Integration availability check |
| mcp-capability-builder shared skill | Yes | Future SDRS MCP design | Path verification |

# Workflow

## STEP 1 — PARSE FAILOVER INTENT

**Classification: AUTOMATED**

**Objective**: Extract and validate failover intent including type (planned/unplanned), protection group ID, and approval owner.

**Inputs**: User request specifying failover type, protection group ID, impact plan, approval owner.

**Preconditions**: Protection setup completed (huawei-sdrs-protection-setup).

**Mechanism**: Parsing logic.

**Approval requirement**: None.

**Verification**: Confirm all required fields present, protection group ID valid, failover type is planned or unplanned.

**Expected result**: Complete failover intent object.

**Stop condition**: Protection group ID missing or invalid, failover type ambiguous.

**Failure action**: STOP and request clarification.

**Evidence artifact**: `artifacts/sdrs-failover-intent.json`

## STEP 2 — VALIDATE LAST REPLICATION STATE

**Classification: ASSISTED**

**Objective**: Validate the last replication state, lag, and health before failover.

**Inputs**: Protection group ID.

**Preconditions**: Step 1 completed.

**Mechanism**: MANUAL console status check.

**Approval requirement**: None.

**Verification**: Replication state documented, lag measured, health confirmed.

**Expected result**: Replication state assessment.

**Stop condition**: Replication not active (for planned failover), or replication state uncertain (for unplanned failover — proceed with warning).

**Failure action**: For planned failover: STOP. For unplanned failover: WARN and document risk.

**Evidence artifact**: `artifacts/sdrs-replication-state.md`

## STEP 3 — EVALUATE PRIMARY SITE

**Classification: ASSISTED**

**Objective**: Evaluate the condition of the primary site.

**Inputs**: Production region, failover type.

**Preconditions**: Step 2 completed.

**Mechanism**: hcloud CLI read-only checks (if accessible), or manual assessment.

**Approval requirement**: None.

**Verification**: Primary site condition documented.

**Expected result**: Primary site assessment (accessible, degraded, or unavailable).

**Evidence artifact**: `artifacts/sdrs-primary-site-assessment.md`

For planned failover: primary site should be accessible.
For unplanned failover: primary site is confirmed unavailable or irrecoverable.

## STEP 4 — IMPACT PLAN

**Classification: AUTOMATED**

**Objective**: Generate comprehensive impact plan for the failover.

**Inputs**: Failover intent, replication state, primary site assessment.

**Preconditions**: Steps 1-3 completed.

**Mechanism**: Plan generation.

**Approval requirement**: None (plan only).

**Verification**: Plan covers all required elements.

**Expected result**: Failover impact plan.

**Stop condition**: Critical information missing.

**Failure action**: STOP. Report missing information.

**Evidence artifact**: `artifacts/sdrs-failover-impact-plan.md`

The plan must include:
- Trigger criteria and authority
- Production site current state
- Last replication status and lag
- Application shutdown procedure (if planned)
- DNS change procedure
- Route change procedure
- Validation procedure
- Communication plan
- Rollback feasibility assessment
- Data-loss risk assessment
- Split-brain prevention measures
- Timestamps for all steps

## STEP 5 — CRITICAL APPROVAL

**Classification: MANUAL**

**Objective**: Obtain MANDATORY EXPLICIT APPROVAL for failover execution.

**Inputs**: Failover impact plan.

**Preconditions**: Step 4 completed.

**Mechanism**: Approval workflow.

**Approval requirement**: MANDATORY_EXPLICIT_APPROVAL.

**Risk**: CRITICAL

**Verification**: Approval recorded with approver identity and timestamp.

**Expected result**: Failover approved for execution.

**Stop condition**: Approval denied.

**Failure action**: STOP. Do not execute failover.

**Evidence artifact**: `artifacts/sdrs-failover-approval.md`

## STEP 6 — EXECUTE FAILOVER

**Classification: MANUAL**

**Objective**: Execute the failover operation via manual console.

**Inputs**: Approved failover plan, explicit approval.

**Preconditions**: Step 5 approval obtained.

**Mechanism**: MANUAL_CONSOLE.

**Risk**: CRITICAL

**Approval requirement**: MANDATORY_EXPLICIT_APPROVAL (already obtained in Step 5).

**Verification**: Failover operation completed in console.

**Expected result**: Failover executed, DR site now serving production.

**Stop condition**: Failover operation fails in console.

**Failure action**: STOP. Preserve both sites. Report failure. Do NOT delete resources.

**Evidence artifact**: `artifacts/sdrs-failover-result.md**

## STEP 7 — VALIDATE DR SITE

**Classification: ASSISTED**

**Objective**: Validate DR site is functioning correctly after failover.

**Inputs**: Failover result.

**Preconditions**: Step 6 completed.

**Mechanism**: Manual verification and automated checks.

**Approval requirement**: None.

**Verification**: DR site servers running, applications functional, network correct.

**Expected result**: DR site validation report.

**Stop condition**: Critical validation failure.

**Failure action**: STOP. Assess state. Do NOT delete resources.

**Evidence artifact**: `artifacts/sdrs-failover-validation.md**

After failover, verify:
- DR site servers are running
- Replication state reflects failover
- Applications are functional at DR site
- Network connectivity is correct
- DNS points to DR site (manual update)
- RPO measured (data loss assessment)
- RTO measured (recovery time)
- Production site resources are preserved
- Split brain prevented (original primary not serving traffic)
- Incident timeline documented

## STEP 8 — MEASURE RPO AND RTO

**Classification: ASSISTED**

**Objective**: Measure actual RPO and RTO achieved during failover.

**Inputs**: Failover timestamps, replication lag data.

**Preconditions**: Step 7 completed.

**Mechanism**: Calculation from timestamps and replication data.

**Approval requirement**: None.

**Expected result**: RPO and RTO measurements.

**Evidence artifact**: `artifacts/sdrs-failover-rpo-rto.md`

## STEP 9 — PREVENT SPLIT BRAIN

**Classification: ASSISTED**

**Objective**: Confirm that the original primary site is not serving traffic independently.

**Inputs**: Primary site assessment, DR site status.

**Preconditions**: Step 7 completed.

**Mechanism**: Manual verification.

**Approval requirement**: None.

**Verification**: Only one site is active and serving traffic.

**Expected result**: Split brain prevention confirmed.

**Stop condition**: Both sites appear active — AMBIGUOUS STATE.

**Failure action**: STOP on split-brain uncertainty. Do not proceed with reverse reprotection or failback. Escalate immediately.

**Evidence artifact**: `artifacts/sdrs-split-brain-check.md**

## STEP 10 — REVERSE REPROTECTION

**Classification: MANUAL**

**Objective**: Re-establish replication in the reverse direction (DR site to production site) after failover.

**Inputs**: Failover result, protection group status.

**Preconditions**: Step 9 completed. Split brain prevented.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT.

**Verification**: Reverse replication is active, lag is within threshold.

**Expected result**: Reverse replication protecting the new primary (DR site).

**Stop condition**: Reverse reprotection unavailable or fails.

**Failure action**: Alert. DR site is unprotected. Escalate immediately.

**Evidence artifact**: `artifacts/sdrs-reverse-reprotection-result.md**

IMPORTANT: Reverse reprotection is NOT failback. It only re-establishes replication. Failback is a separate, subsequent operation.

## STEP 11 — FAILBACK PLANNING

**Classification: AUTOMATED**

**Objective**: Plan the failback process to return production to the original site.

**Inputs**: Reverse reprotection status, original production site status.

**Preconditions**: Step 10 completed. Reverse replication is active.

**Mechanism**: Plan generation.

**Approval requirement**: None (plan only).

**Verification**: Plan is complete and consistent.

**Expected result**: Failback plan ready for approval.

**Stop condition**: Reverse replication not active, or original site not ready.

**Failure action**: STOP. Remain at DR site. Report failback prerequisites not met.

**Evidence artifact**: `artifacts/sdrs-failback-plan.md**

Failback plan includes:
- Recovery of original primary site infrastructure
- Resynchronization validation (replication lag is zero or minimal)
- Consistency validation at original site
- Application shutdown or quiescence at DR site
- Reverse direction failover (DR site to production site)
- DNS restoration to original production
- Application verification at original site
- RPO and RTO measurement
- Rollback alternative (remain at DR site)
- Explicit approval from approval_owner

## STEP 12 — FAILBACK APPROVAL

**Classification: MANUAL**

**Objective**: Obtain explicit approval for failback execution. This is a SEPARATE approval from failover.

**Inputs**: Failback plan.

**Preconditions**: Step 11 completed.

**Mechanism**: Approval workflow.

**Approval requirement**: EXPLICIT (separate from failover approval).

**Risk**: CRITICAL

**Verification**: Approval recorded with approver identity and timestamp.

**Expected result**: Failback approved for execution.

**Stop condition**: Approval denied.

**Failure action**: STOP. Remain at DR site.

**Evidence artifact**: `artifacts/sdrs-failback-approval.md**

## STEP 13 — EXECUTE FAILBACK

**Classification: MANUAL**

**Objective**: Return production to the original site with a controlled process.

**Inputs**: Approved failback plan.

**Preconditions**: Step 12 approval obtained. Reverse replication is active.

**Mechanism**: MANUAL_CONSOLE.

**Approval requirement**: EXPLICIT (already obtained in Step 12).

**Verification**: Production site is active, applications are functional, replication is re-established in original direction.

**Expected result**: Production running at original site, replication active.

**Stop condition**: Synchronization not complete, or original site not ready.

**Failure action**: STOP. Remain at DR site. Report failback failure.

**Evidence artifact**: `artifacts/sdrs-failback-result.md**

## STEP 14 — DNS RESTORATION PLAN

**Classification: AUTOMATED**

**Objective**: Plan DNS restoration to point to the original production site.

**Inputs**: Failback result, original DNS configuration.

**Preconditions**: Step 13 completed.

**Mechanism**: Plan generation.

**Approval requirement**: EXPLICIT for DNS changes.

**Verification**: DNS plan documented with before/after state.

**Expected result**: DNS restoration plan.

**Evidence artifact**: `artifacts/sdrs-dns-restoration-plan.md**

DNS changes are NEVER automatic. They require explicit approval and manual execution.

## STEP 15 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-14.

**Preconditions**: All completed steps.

**Mechanism**: Report generation logic.

**Approval requirement**: None.

**Expected result**: Final closure report.

**Evidence artifact**: `artifacts/sdrs-failover-failback-report.md`

Generate: final summary, failover result, failback result (if executed), RPO/RTO measurements, DNS changes, unresolved risks, manual actions required, capability gaps identified, MCP recommendation, ticket recommendation, next drill date recommendation.

Do NOT delete resources automatically.

# Scope boundary

This skill is responsible for failover and failback ONLY. It preserves:
- planned != unplanned failover
- reverse reprotection != failback
- failback requires separate approval
- no automatic DNS
- no automatic deletion
- preserve both sites
- stop on split-brain uncertainty

# Capability gap handling

Known capability gaps (failover-specific):
- GAP-SDR-001: No SDRS CLI support. Failover operations are MANUAL_CONSOLE. [NOT_AVAILABLE]
- GAP-SDR-002: No SDRS MCP exists. [NOT_AVAILABLE]
- GAP-SDR-003: Failover, reverse reprotection, and failback are critical operations with no automation safeguard. [NOT_AVAILABLE]
- GAP-SDR-005: SDRS is not in huaweicloud-deploy supported services. [VERIFIED_FROM_CODE]

# Output artifacts

- artifacts/sdrs-failover-intent.json
- artifacts/sdrs-replication-state.md
- artifacts/sdrs-primary-site-assessment.md
- artifacts/sdrs-failover-impact-plan.md
- artifacts/sdrs-failover-approval.md
- artifacts/sdrs-failover-result.md
- artifacts/sdrs-failover-validation.md
- artifacts/sdrs-failover-rpo-rto.md
- artifacts/sdrs-split-brain-check.md
- artifacts/sdrs-reverse-reprotection-result.md
- artifacts/sdrs-failback-plan.md
- artifacts/sdrs-failback-approval.md
- artifacts/sdrs-failback-result.md
- artifacts/sdrs-dns-restoration-plan.md
- artifacts/sdrs-failover-failback-report.md

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| Failover rejected | Protection status or replication state | Console task status | Verify protection status, replication state, approval |
| Unplanned failover uncertain state | Primary site condition unknown | Manual assessment | Assess data loss risk, verify DR site consistency |
| Reverse reprotection unavailable | SDRS version or region support | Console capability check | Check SDRS version, region support, gateway |
| Split brain detected | Both sites serving traffic | Network and DNS check | STOP. Escalate. Do not proceed. |
| Failback blocked | Reverse replication not complete | Console replication status | Verify reverse replication is active and synchronized |
| DNS not updated | Manual DNS step skipped | DNS query test | Execute DNS restoration plan manually |

See also: `references/rollback.md` and scenario-level `../references/known-issues.md`

# Failure handling

- Failover rejected: Check protection status, replication state, approval. Verify all prerequisites.
- Unplanned failover uncertain state: Assess data loss risk. Verify DR site data consistency. Do not assume primary is lost.
- Reverse reprotection unavailable: Check SDRS version, region support, gateway. DR site is unprotected — escalate.
- Failback blocked: Check reverse replication status, original site capacity, synchronization. Remain at DR site.
- Split brain: STOP. Do not proceed. Escalate immediately. Assess both sites manually.

# Recovery procedure

1. If failure during failover: Both sites may be in uncertain state. DO NOT modify either site automatically. Assess state of both sites manually. Decide next action based on data consistency assessment.
2. If failure during reverse reprotection: DR site is unprotected. This is a critical state. Establish reverse reprotection as soon as possible. If not possible, consider alternative protection (CBR backup).
3. If failure during failback: Remain at DR site. Verify DR site is functional. Re-attempt failback only after resolving the failure cause. Do not force failback.

# Evidence and traceability

- All manual console actions documented with timestamps and results
- Approval decisions recorded with approver identity and timestamp
- RPO and RTO measurements recorded
- DNS changes documented with before/after state
- Split brain check documented
- Failover and failback timelines documented
- No secrets in any artifact

# Known limitations

- No SDRS CLI support in hcloud 6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations are MANUAL via console [NOT_AVAILABLE]
- Failover is a critical operation with no automation safeguard [NOT_AVAILABLE]
- DNS cutover is manual [INFERRED]
- SDRS is NOT supported by huaweicloud-deploy MCP [VERIFIED_FROM_CODE]
- hcloud CLI v6.2.9 verified; v7.2.12 validation pending [VERSION_DEPENDENT]

# Status justification

Status: EXPERIMENTAL

Evidence:
- SDRS service is NOT available in hcloud CLI v6.2.9 [NOT_AVAILABLE]
- No SDRS MCP exists [NOT_AVAILABLE]
- All SDRS operations must be performed manually via console [NOT_AVAILABLE]
- Failover is a critical operation with no automation safeguard [NOT_AVAILABLE]
- No cloud-side tests were executed [NOT_VERIFIED]
- The workflow provides value as a controlled runbook for manual execution [INFERRED]
- Capability builder integration enables future MCP design [VERIFIED_FROM_CODE]
