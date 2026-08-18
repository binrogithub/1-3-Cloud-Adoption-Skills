# huawei-database-usage-operations

## Purpose

Use already-deployed Huawei Cloud database instances — RDS, DDS, GeminiDB, TaurusDB, and GaussDB — via hcloud CLI (KooCLI): find an instance, read its connection details, and assign it an Elastic IP (EIP) for public access. Deploys the EIP itself via the EIP service and binds it using each database service's own confirmed mechanism (a dedicated bind operation where one exists, or the generic EIP-to-port association where it does not, as for RDS). Never invents a bind operation and documents the one service, GaussDB, where no public-cloud EIP-bind capability could be confirmed.

This skill does not create database instances — see the companion `huawei-database-deploy-operations` skill for that. It is usage-and-exposure-focused: finding an instance, reading it, and binding a public IP to it.

## Services covered

| Service | `hcloud` service name | EIP-bind mechanism |
|---|---|---|
| EIP | `EIP` | N/A — the resource being bound |
| RDS | `RDS` | Generic `EIP AssociatePublicips` against the instance's private network port — no dedicated RDS operation |
| DDS | `DDS` | Dedicated, per-node bind operation |
| GeminiDB | `NoSQL` | Dedicated, per-node bind operation (most fully confirmed) |
| TaurusDB | `GaussDBforMySQL` | Dedicated, per-instance bind operation (fully confirmed, including operation name) |
| GaussDB | `GaussDB` (unconfirmed) | Not confirmed — critical capability gap |

## Confirmed vs. unconfirmed operations per service

| Service | Confirmed (full parameter table / example) | Unconfirmed |
|---|---|---|
| EIP | Deploy, query, bind, unbind — all HTTP method/path/parameters | Literal `hcloud EIP <operation>` name strings |
| RDS | The bind pattern itself (user guide + Terraform provider docs) | The VPC port-query operation's name/syntax |
| DDS | Bind operation's HTTP method/path/body (via regional mirror) | Literal operation name |
| GeminiDB (NoSQL) | Bind operation's full parameter table — most fully confirmed | Literal operation name |
| TaurusDB (GaussDBforMySQL) | Bind operation's full example AND literal name (`UpdateGaussMySqlInstanceEip`) | — |
| GaussDB | Nothing — only a private-cloud (Huawei Cloud Stack) reference found | Everything |

## Architecture

```
Operation Intent (target_service, action, instance/node, EIP params)
                │
      hcloud <SERVICE_NAME> --help   (confirm operations available)
                │
      Find the target instance (and node, for DDS/GeminiDB)
                │
        ┌───────┴────────┬─────────────────┐
        │                │                 │
     find only        connect only     bind-eip
        │                │                 │
   (stop here)    surface details    Explicit approval
                                            │
                              Deploy or reuse EIP (EIP CreateEip)
                                            │
                    RDS: resolve network port (VPC ListPorts) first
                                            │
                Bind: service-specific op, or generic EIP AssociatePublicips
                                            │
                         Verify: re-run find, confirm public IP
                                            │
              Reminder: security group must separately allow the port
```

## Known capability gaps

| Gap ID | Service | Decision |
|---|---|---|
| GAP-DB-USE-101 | EIP | PROBE_HELP_BEFORE_USE (literal operation names) |
| GAP-DB-USE-102 | RDS | PROBE_HELP_BEFORE_USE (VPC port-query operation) |
| GAP-DB-USE-103 | DDS | PROBE_HELP_BEFORE_USE (bind operation confirmed via regional mirror, name unconfirmed) |
| GAP-DB-USE-104 | GeminiDB (NoSQL) | PROBE_HELP_BEFORE_USE (parameters confirmed, name unconfirmed) |
| GAP-DB-USE-105 | GaussDB | USE_MANUAL_CONSOLE_FALLBACK (nothing confirmed at public-cloud level) |

GaussDB (`GAP-DB-USE-105`) is this skill's most significant gap, directly analogous to GaussDB's create-instance gap in the companion deployment skill: the only "Binding or Unbinding an EIP" reference found was for the Huawei Cloud Stack private-cloud edition, not the public cloud. See `SKILL.md` → "Per-service operations" and "Capability gap handling" for full detail on every gap.

## Rules summary

1. Each service has its own distinct `hcloud` service name; there is no generic `Database` service name and no dedicated MCP for any of them, or for EIP
2. RDS has no dedicated EIP-bind operation — it binds via the generic EIP service against its private network port
3. Every bind-EIP request body is passed via `--cli-jsonInput=<file>` for consistency, even where a flattened form might work
4. Any operation not in a service's confirmed-operations table must be probed live (`hcloud <SERVICE_NAME> <OPERATION> --help`)
5. FIND BEFORE BIND: resolve the current instance/node ID and status via a read operation, never hardcode
6. VERIFY AFTER EVERY BIND, and always surface the reminder that the security group must separately allow the client IP on the database port (this skill never modifies the security group)
7. Every bind-eip action, and every EIP deployment, requires explicit approval
8. This skill never creates a database instance or a networking resource — it only uses what already exists
9. Never include secrets in commands, examples, or logs
10. The five database modules, and the EIP module, are independent of each other

## Required tools

| Tool | Purpose |
|---|---|
| hcloud CLI (KooCLI) | All operations across EIP and all five database services |
| Huawei Cloud auth (AK/SK) | API access |
| An already-existing database instance | This skill uses, but does not create, instances |

## Workflow summary

1. Parse Intent → 2. Discover Auth/Region → 3. Find the Target Instance → 4. Run the Requested Action (find / connect / bind-eip, from `SKILL.md` → "Per-service operations") → 5. Closure

## Automation level by phase

| Phase | Automation | Mechanism |
|---|---|---|
| Parse intent | AUTOMATED | Logic |
| Discovery (auth/region) | ASSISTED | hcloud CLI read-only |
| Instance find | ASSISTED | hcloud CLI read-only |
| Connect (surface details) | ASSISTED | Logic on already-read data |
| EIP deploy | ASSISTED | hcloud CLI + approval |
| EIP bind | ASSISTED | hcloud CLI + approval |
| Verification | ASSISTED | hcloud CLI read-only |
| Closure | AUTOMATED | Logic |

## hcloud / verification status

- Verified from: official public API Reference pages for EIP (V1 create; V3 query/associate/disassociate), GeminiDB/NoSQL, and TaurusDB/GaussDBforMySQL; a regional mirror of the standard DDS API Reference for DDS; and RDS's own user guide plus the official Terraform provider's documented pattern for RDS. For GaussDB, only a private-cloud (Huawei Cloud Stack) reference, a different product edition from the public cloud.
- Live CLI test performed: **No** (authoring environment had web-search/fetch access to public and regionally-mirrored documentation only)

## MCP dependencies

| MCP | Required | Purpose |
|---|---|---|
| huaweicloud-ticket | No | Support escalation if a capability gap blocks a requested action and manual escalation is desired |

No dedicated MCP exists for EIP or any of the five database services. All operations via hcloud CLI.

## Approval gates

- Any bind-eip action, for any of the five services
- Deploying a new EIP
- Reuse of an existing EIP instead of deploying a new one
- Unbinding an EIP (if requested, outside the primary workflow)

## Outputs

- artifacts/db-use-intent.json
- artifacts/db-use-auth-discovery.json
- artifacts/db-use-instance-resolution.json
- artifacts/db-use-execution-result.json
- artifacts/db-use-verification.json
- artifacts/db-use-final-report.md

## Known limitations

- GaussDB's EIP-bind (and instance-find) capability is entirely unresolved at the public-cloud level (`GAP-DB-USE-105`)
- Several operations across EIP, RDS, DDS, and GeminiDB have their HTTP method/path/parameters confirmed but not their literal `hcloud` operation-name strings
- This skill's scope excludes database-instance creation, VPC/subnet/security-group creation or modification (including the inbound rule that actually opens the database port), in-instance database/schema/user management, backup/restore, and specification changes
- No live hcloud CLI or tenant test was performed during authoring

## Troubleshooting

See `SKILL.md` → "Troubleshooting" for the full table.

| Symptom | Action |
|---|---|
| An operation is missing from `hcloud <SERVICE_NAME> --help` | Use the console |
| Bind succeeds but instance is still unreachable | Check the security group's inbound rule for the client IP/port (out of this skill's scope to fix) |
| EIP already bound elsewhere | Unbind it first (`EIP DisassociatePublicips` or the service's own unbind call) |
| RDS port resolution returns zero/multiple ports | Re-resolve `private_ips` via `RDS ListInstances` and retry |
| GaussDB bind-eip requested | Route to the console; `GAP-DB-USE-105` is unresolved |

## Maturity status

**READY_WITH_WARNINGS**

TaurusDB's bind-EIP operation is the most fully confirmed in this skill — both its parameters and its literal operation name (`UpdateGaussMySqlInstanceEip`) came directly from its own API Reference page. GeminiDB's bind operation has a fully confirmed parameter table. DDS's bind operation was confirmed via a regional documentation mirror. RDS has no dedicated bind operation at all — it uses the generic EIP-to-port mechanism, a pattern confirmed via RDS's own user guide and the official Terraform provider. GaussDB has no operation confirmed at the public-cloud level at all — its one capability gap is critical-path for any GaussDB bind-eip action and is routed to the console. All bind-eip actions and EIP deployments require approval, and this skill never modifies networking resources, including the security-group rule that actually opens the database port to a client.

## Evidence

| Evidence | Type |
|---|---|
| EIP deploy/query/bind/unbind confirmed via their own public API Reference pages | VERIFIED_FROM_PUBLIC_API_DOCS |
| TaurusDB `UpdateGaussMySqlInstanceEip` confirmed with full example AND literal operation name | VERIFIED_FROM_PUBLIC_API_DOCS |
| GeminiDB bind-EIP operation confirmed with full parameter table | VERIFIED_FROM_PUBLIC_API_DOCS |
| RDS's port-based bind pattern confirmed via user guide + Terraform provider docs | VERIFIED_FROM_PUBLIC_API_DOCS |
| DDS bind-EIP operation confirmed via a regional documentation mirror | PARTIAL |
| GaussDB EIP-bind capability | NOT_CONFIRMED (only a private-cloud/Huawei Cloud Stack reference found) |
| No dedicated MCP exists for EIP or any of the five database services | VERIFIED_FROM_PUBLIC_API_DOCS |
| Live hcloud CLI / tenant execution | NOT_LIVE_TESTED |
