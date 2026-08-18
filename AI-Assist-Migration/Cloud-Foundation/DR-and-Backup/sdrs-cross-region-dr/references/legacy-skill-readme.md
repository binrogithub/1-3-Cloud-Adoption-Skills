# huawei-sdr-cross-region-replication

## Purpose

Discover, plan, execute under human supervision, validate and recover Huawei Cloud cross-region and cross-AZ disaster recovery scenarios using SDRS (Storage Disaster Recovery Service).

## Canonical service name

**SDRS** — Storage Disaster Recovery Service

## Aliases

- SDR (legacy shorthand)
- SDRS (current canonical)
- Storage Disaster Recovery Service (full name)

**Note**: BRS (Business Recovery Service) is a separate service and is NOT equivalent to SDRS. CBR (Cloud Backup and Recovery) is a backup service and is NOT equivalent to SDRS.

## Supported scenario

- Cross-region disaster recovery for Huawei Cloud ECS instances
- Cross-AZ disaster recovery for Huawei Cloud ECS instances
- SDRS protection groups, protected instances, and replication pairs
- DR gateway configuration (cross-region)
- DR drills, planned failover, unplanned failover, reverse reprotection, and failback

## Architecture

```
Production Region                              DR Region
┌──────────────────────┐                       ┌──────────────────────┐
│  ECS Instance A      │                       │  ECS Instance A'     │
│  ├─ EVS Volume 1 ────┼── Replication Pair ──>│  ├─ EVS Volume 1'   │
│  └─ EVS Volume 2 ────┼── Replication Pair ──>│  └─ EVS Volume 2'   │
└──────────────────────┘                       └──────────────────────┘
         │                                                │
         │              Protection Group                  │
         └────────────────┬─────────────────┬───────────┘
                          │                 │
                   ┌──────▼──────┐   ┌──────▼──────┐
                   │ DR Gateway  │──>│ DR Gateway  │
                   │ (Production)│   │ (DR Site)   │
                   └─────────────┘   └─────────────┘
                          │                 │
                   ┌──────▼──────┐   ┌──────▼──────┐
                   │    VPC      │   │    VPC      │
                   │  Subnet     │   │  Subnet     │
                   │  SG / EIP   │   │  SG / EIP   │
                   └─────────────┘   └─────────────┘
```

Failover path:
```
Production (failed) ──Failover──> DR Site (active)
                                      │
                              Reverse Reprotection
                                      │
Production (replica) <──Failback── DR Site (primary)
```

## Rules summary

1. DISCOVER BEFORE CREATE: resolve names to IDs, never hardcode
2. VERIFY AFTER EVERY STEP: every action has a follow-up verification
3. Every write operation requires explicit approval
4. Failover is CRITICAL: requires MANDATORY_EXPLICIT_APPROVAL with impact plan
5. Reverse reprotection is NOT failback (separate operations)
6. Failback requires a separate plan and approval
7. DR drill is NOT a production failover
8. DNS changes are never automatic
9. No resource deletion is automatic
10. Validate region pair before designing
11. Cross-region requires DR gateway and async replication
12. Do not offer sync/async as options without confirming support
13. Never include secrets in commands, examples, or logs
14. Never use invented hcloud SDR or SDRS commands

## Prerequisites

| Tool or resource | Required | Purpose |
|---|---|---|
| hcloud CLI 6.2.9 | Yes | Discovery of ECS, EVS, VPC |
| Huawei Cloud auth | Yes | API access for discovery |
| Production region | Yes | Source site |
| DR region | Yes | Target site |
| SDRS availability | Yes | Service in both regions |
| Source ECS + EVS | Yes | Resources to protect |
| Target VPC + subnet | Yes | DR site network |
| DR gateway | Conditional | Cross-region replication |
| RPO/RTO targets | Yes | Acceptable data loss/recovery time |
| Approval owner | Yes | Authority for critical operations |

## Workflow summary

1. Parse Intent → 2. Validate Service/Topology → 3. Discover Production → 4. Discover DR Site → 5. Dependency Analysis → 6. RPO/RTO Plan → 7. Architecture Plan → 8. Readiness Review → 9. Prepare Gateway → 10. Configure Protection → 11. Monitor Replication → 12. Prepare DR Drill → 13. Execute DR Drill → 14. Plan Failover → 15. Execute Failover → 16. Reverse Reprotection → 17. Failback → 18. Closure

## Automation classification

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Service validation | ASSISTED | Documentation + console |
| Source discovery | ASSISTED | hcloud CLI read-only |
| DR discovery | ASSISTED | hcloud CLI + console |
| Dependency analysis | AUTOMATED | Logic |
| RPO/RTO planning | ASSISTED | Analysis |
| Architecture planning | AUTOMATED | Logic |
| Readiness | ASSISTED | Checklist |
| Gateway setup | MANUAL | Console |
| Protection configuration | MANUAL | Console |
| Replication monitoring | ASSISTED | Console periodic check |
| DR drill | MANUAL | Console |
| Failover | MANUAL | Console (CRITICAL) |
| Reverse reprotection | MANUAL | Console |
| Failback | MANUAL | Console (CRITICAL) |
| Closure | AUTOMATED | Logic |

## hcloud limitation

SDRS is NOT available in hcloud CLI 6.2.9. No `hcloud SDR` or `hcloud SDRS` commands exist. hcloud is used ONLY for discovery of related resources (ECS, EVS, VPC, subnet, security group, EIP).

## MCP capability gap

No dedicated SDRS MCP exists. No existing MCP provides SDRS operations. All SDRS operations are MANUAL via console. The skill invokes mcp-capability-builder to design a future SDRS MCP candidate.

## Optional integrations

| MCP/Integration | Purpose | Constraint |
|---|---|---|
| huaweicloud-pricing | Cost estimation | Read-only |
| huaweicloud-ticket | Support tickets | create_ticket requires approval |
| huaweicloud-deploy | VPC/SG prerequisites only | No SDRS support |
| playwright | Console exploration | Read-only, no writes |
| mcp-capability-builder | Future MCP design | Required shared skill |

## Approval gates

- Protection group creation
- Protected instance creation
- Replication pair creation
- Enable protection
- DR drill execution
- Planned failover (CRITICAL)
- Unplanned failover (CRITICAL)
- Reverse reprotection
- Failback (CRITICAL)
- Gateway installation
- DNS changes

## Outputs

- artifacts/sdr-intent.json
- artifacts/sdr-capability-assessment.md
- artifacts/sdr-source-inventory.json
- artifacts/sdr-target-inventory.json
- artifacts/sdr-application-dependency-map.md
- artifacts/sdr-rpo-rto-plan.md
- artifacts/sdr-architecture-plan.md
- artifacts/sdr-readiness-report.md
- artifacts/sdr-gateway-result.md
- artifacts/sdr-protection-result.md
- artifacts/sdr-replication-status-report.md
- artifacts/sdr-drill-plan.md
- artifacts/sdr-drill-result.md
- artifacts/sdr-failover-plan.md
- artifacts/sdr-failover-result.md
- artifacts/sdr-reverse-reprotection-plan.md
- artifacts/sdr-failback-plan.md
- artifacts/sdr-final-report.md

## Known limitations

- No SDRS CLI or MCP (all operations manual)
- SDRS availability varies by region
- Cross-region requires async replication only
- DR gateway required for cross-region
- DNS cutover is manual
- No automated monitoring or alerting
- Failover is critical with no automation safeguard
- hcloud 7.2.12 compatibility not yet verified

## Troubleshooting

See [docs/known-issues.md](references/known-issues.md) for detailed troubleshooting.

| Symptom | Action |
|---|---|
| SDRS not in region | Verify region support, consider alternative |
| Region pair unsupported | Check supported pairs, select alternative DR region |
| Gateway install fails | Check network, ports, OS, IAM |
| Protection fails | Check ECS compatibility, OS, disk type, quotas |
| Replication lag high | Check bandwidth, data rate, gateway health |
| Failover rejected | Check protection status, replication, approval |

## Maturity status

**EXPERIMENTAL**

No SDRS CLI or MCP support. All operations manual via console. Skill provides controlled runbook, discovery, planning, and capability gap documentation. Automated execution is BLOCKED. Manual execution is supported.

## Evidence

| Evidence | Type |
|---|---|
| SDRS NOT available in hcloud CLI 6.2.9 | NOT_AVAILABLE |
| No SDRS MCP exists | NOT_AVAILABLE |
| Related services (ECS, EVS, VPC) available in hcloud CLI | VERIFIED_FROM_LOCAL_HELP |
| SDRS not in huaweicloud-deploy supported services | VERIFIED_FROM_CODE |
| mcp-capability-builder available for future MCP design | VERIFIED_FROM_CODE |
