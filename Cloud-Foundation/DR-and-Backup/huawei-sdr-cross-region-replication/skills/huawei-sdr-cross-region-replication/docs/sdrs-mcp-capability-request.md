# SDRS MCP Capability Request

## Overview

This document proposes a conceptual design for a dedicated SDRS MCP to address the capability gaps identified in the SDRS cross-region disaster recovery skill. This is a design document only — no functional code is generated.

## Motivation

- SDRS is NOT available in hcloud CLI 6.2.9 [NOT_AVAILABLE]
- No existing MCP provides SDRS operations [NOT_AVAILABLE]
- All SDRS operations are currently MANUAL via console [NOT_AVAILABLE]
- Automated execution of failover, reverse reprotection, and failback is BLOCKED [NOT_AVAILABLE]

## API Source

SDRS operations would be based on the Huawei Cloud SDRS API:
- API Endpoint: V2 API for SDRS
- API Documentation: Huawei Cloud API Explorer
- SDK: Huawei Cloud SDK (language TBD)

**IMPORTANT**: The API contract must be validated against the official documentation before any implementation. Tool names, parameters, and return values are candidates only.

## Proposed Tool Candidates

### Read-Only Candidates (Priority 1)

| Tool Name | Description | Status |
|---|---|---|
| list_protection_groups | List all protection groups in a domain | NOT_IMPLEMENTED |
| show_protection_group | Show details of a specific protection group | NOT_IMPLEMENTED |
| list_protected_instances | List protected instances in a protection group | NOT_IMPLEMENTED |
| show_protected_instance | Show details of a specific protected instance | NOT_IMPLEMENTED |
| list_replication_pairs | List replication pairs in a protection group | NOT_IMPLEMENTED |
| show_replication_pair | Show details of a specific replication pair | NOT_IMPLEMENTED |
| show_replication_status | Show replication status and lag for a pair | NOT_IMPLEMENTED |
| list_drills | List DR drills | NOT_IMPLEMENTED |
| show_drill | Show details of a specific DR drill | NOT_IMPLEMENTED |
| list_failover_jobs | List failover jobs | NOT_IMPLEMENTED |
| show_failover_job | Show details of a specific failover job | NOT_IMPLEMENTED |

### Write Candidates (Priority 2 — Require Approval Gates)

| Tool Name | Description | Status |
|---|---|---|
| create_protection_group | Create a protection group | NOT_IMPLEMENTED |
| delete_protection_group | Delete a protection group | NOT_IMPLEMENTED |
| create_protected_instance | Create a protected instance | NOT_IMPLEMENTED |
| delete_protected_instance | Delete a protected instance | NOT_IMPLEMENTED |
| create_replication_pair | Create a replication pair | NOT_IMPLEMENTED |
| delete_replication_pair | Delete a replication pair | NOT_IMPLEMENTED |
| enable_protection | Enable protection for a protection group | NOT_IMPLEMENTED |
| disable_protection | Disable protection for a protection group | NOT_IMPLEMENTED |
| create_dr_drill | Create a DR drill | NOT_IMPLEMENTED |
| delete_dr_drill | Delete a DR drill | NOT_IMPLEMENTED |
| execute_planned_failover | Execute a planned failover | NOT_IMPLEMENTED |
| execute_unplanned_failover | Execute an unplanned failover | NOT_IMPLEMENTED |
| execute_reverse_reprotection | Execute reverse reprotection | NOT_IMPLEMENTED |
| execute_failback | Execute failback | NOT_IMPLEMENTED |

## Approval Gate Design

All write candidates must implement:
- `requires_explicit_approval: true` in tool metadata
- Pre-execution validation (prerequisites, state checks)
- Post-execution verification (status confirmation)
- Evidence recording (timestamps, results, sanitized IDs)
- Rollback guidance on failure

Critical operations (failover, failback) must implement:
- Double confirmation mechanism
- Impact plan requirement
- Timeout and status polling
- Split-brain prevention check

## Implementation Phases

1. **Phase 1**: Implement read-only tools (list_*, show_*)
   - Validate API contract
   - Implement with proper error handling
   - Add unit tests with mocks
   - Status: DRAFT

2. **Phase 2**: Implement write tools with approval gates
   - Add explicit approval mechanism
   - Add pre/post validation
   - Add evidence recording
   - Status: READY_FOR_REVIEW

3. **Phase 3**: Integration testing
   - Test against SDRS API in non-production
   - Validate all tool behaviors
   - Status: READY_WITH_WARNINGS

## Constraints

- All candidate tools are NOT_IMPLEMENTED
- API contract requires validation before implementation
- Do NOT auto-activate any generated MCP
- Do NOT generate functional code until API contract is verified
- Tool names are candidates and may change based on API documentation

## Invocation

When the user requests SDRS automation, invoke mcp-capability-builder with this document as input. The capability builder will:
1. Verify API documentation
2. Validate SDK availability
3. Generate MCP scaffold
4. Create mock implementations
5. Create unit tests
6. Mark as DRAFT or READY_FOR_REVIEW
7. NOT activate automatically
