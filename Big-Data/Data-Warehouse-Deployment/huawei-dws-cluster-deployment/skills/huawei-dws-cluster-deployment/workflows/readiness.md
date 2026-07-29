# Readiness Workflow

## Purpose

Validate all prerequisites and quotas before cluster deployment.

## Inputs

- Architecture plan
- Discovery results
- Intent parameters

## Steps

1. **Validate DWS quota**
   - Check cluster quota in region
   - Approval: None
   - Verification: Quota sufficient for planned cluster

2. **Validate node quota**
   - Check compute node quota
   - Approval: None
   - Verification: Quota >= planned node count

3. **Validate storage quota**
   - Check storage quota
   - Approval: None
   - Verification: Quota >= planned storage

4. **Validate EIP quota** (if public access)
   - Check EIP quota
   - Approval: None
   - Verification: Quota sufficient

5. **Validate network readiness**
   - VPC exists and is in correct region
   - Subnet exists and has sufficient IPs
   - Security group exists and has no 0.0.0.0/0 rules
   - Approval: None
   - Verification: All network resources valid

6. **Validate node type availability**
   - Planned node type is in ListNodeTypes response
   - Approval: None
   - Verification: Node type available in region

7. **Validate AZ availability**
   - Planned AZ supports the selected node type
   - Approval: None
   - Verification: AZ available

8. **Validate version availability**
   - Planned version is available in region
   - Approval: None
   - Verification: Version available

9. **Validate password handling**
   - Secure input mechanism established
   - Password meets complexity requirements
   - Approval: None
   - Verification: Mechanism confirmed

10. **Validate IAM permissions**
    - DWS create permissions confirmed
    - Approval: None
    - Verification: Permissions sufficient

11. **Validate naming**
    - Cluster name meets constraints (4-64 chars, letter start)
    - Cluster name is unique
    - Database name meets constraints
    - Approval: None
    - Verification: Names valid and unique

12. **Validate budget**
    - Cost estimate within budget (if budget specified)
    - Approval: None
    - Verification: Budget not exceeded

## Outputs

- artifacts/dws-readiness-report.md

## Result

- READY: All checks pass
- READY_WITH_WARNINGS: Non-blocking issues found
- NOT_READY: Blocking issues found
- BLOCKED: Cannot proceed

## Stop Conditions

- NOT_READY or BLOCKED result
- Do NOT proceed to execution

## Failure Handling

- Report all failing checks
- Suggest remediation for each
- Allow re-check after remediation
