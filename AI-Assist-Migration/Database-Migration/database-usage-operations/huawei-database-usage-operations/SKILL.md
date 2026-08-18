---
name: huawei-database-usage-operations
version: 1.0.0
description: "Use already-deployed Huawei Cloud database instances — RDS, DDS, GeminiDB, TaurusDB, and GaussDB — via hcloud CLI (KooCLI): find an instance, read its connection details, and assign it an Elastic IP (EIP) for public access. Deploys the EIP itself via the EIP service and binds it using each database service's own confirmed mechanism (a dedicated bind operation where one exists, or the generic EIP-to-port association where it does not, as for RDS). Never invents a bind operation and documents the one service, GaussDB, where no public-cloud EIP-bind capability could be confirmed."
category: database-operations
risk_level: high
status: READY_WITH_WARNINGS
requires_explicit_approval: true
license: Apache-2.0
compatibility:
  - OpenCode
  - Hermes
metadata:
  domain: Database-Operations
  family: Cloud-Database-Usage-And-Network-Exposure
  service: EIP-RDS-DDS-GeminiDB-TaurusDB-GaussDB
  risk_level: high
  status: READY_WITH_WARNINGS
  create_operation_verification: PARTIAL_PUBLIC_DOCS_VERIFIED_NOT_LIVE_TESTED
---

# Purpose

Use already-deployed Huawei Cloud database instances — RDS, DDS, GeminiDB, TaurusDB, and GaussDB — via hcloud CLI (KooCLI). This skill does not create database instances (see the companion `huawei-database-deploy-operations` skill for that); it assumes an instance already exists and covers finding it, reading its connection details, and — its main focus — assigning it public reachability by deploying an Elastic IP (EIP) and binding it to the instance. Each database service binds an EIP through its own mechanism: a dedicated per-node or per-instance bind operation for DDS, GeminiDB, and TaurusDB; the generic EIP-to-network-port association for RDS, which has no dedicated bind operation of its own; and, for GaussDB, an explicitly unresolved capability gap rather than a guessed command.

This skill is usage-and-exposure-focused. It does not manage databases/schemas/users inside an instance, does not perform backup/restore or specification changes, and does not create the VPC/subnet/security group an instance uses — it only consumes their already-existing IDs.

# Supported scenario

- Source: an operation intent naming exactly one target service (rds, dds, geminidb, taurusdb, or gaussdb), an action (find, connect, or bind-eip), and — for bind-eip — an EIP to deploy or reuse
- Target: an already-existing DB instance in that service, identified by its own instance ID (and, for DDS/GeminiDB, a specific node ID)
- Mechanism: each database service's own REST API called through hcloud CLI, under that service's own `hcloud` service name, plus the standalone EIP service (`hcloud EIP`) for deploying and associating the public IP; no dedicated MCP exists for any of these six services
- Storage: none beyond the artifacts this skill itself generates
- Topology: single-region, single-service, single-instance (and, where relevant, single-node) operation per invocation

| Service | Marketing name | `hcloud` service name | EIP-bind mechanism |
|---|---|---|---|
| EIP | Elastic IP | `EIP` | N/A — this is the resource being bound |
| RDS | Relational Database Service | `RDS` | Generic: `EIP AssociatePublicips` against the instance's private network port (no dedicated RDS operation) |
| DDS | Document Database Service | `DDS` | Dedicated, per-node bind operation |
| GeminiDB | GeminiDB (multi-model NoSQL) | `NoSQL` | Dedicated, per-node bind operation (fully confirmed) |
| TaurusDB | TaurusDB (MySQL-compatible) | `GaussDBforMySQL` | Dedicated, per-instance bind operation (fully confirmed, including operation name) |
| GaussDB | GaussDB (distributed, openGauss-based) | `GaussDB` (unconfirmed at public-cloud level) | Not confirmed — critical capability gap |

# When to use this skill

- Finding an existing RDS/DDS/GeminiDB/TaurusDB/GaussDB instance by name and reading its status, datastore, and network details
- Deploying a new EIP (public IP address + bandwidth) via code
- Binding an EIP to an existing database instance (or, for DDS/GeminiDB, a specific node of one) so it can be reached from outside its VPC
- Verifying that an instance is reachable on its bound public IP before handing connection details to an application team
- Auditing which instances in a project currently have a public IP bound

# When not to use this skill

- Creating a new database instance — use the companion `huawei-database-deploy-operations` skill
- Creating, modifying, or deleting the VPC, subnet, or security group an instance uses, or the security-group rule that actually opens the database port to a given client IP — resolve/modify these via the networking service/console; this skill only consumes the resulting IDs and calls out the missing inbound rule as a likely failure cause, but does not create it
- Managing databases, schemas, users, or grants inside an already-deployed instance — use the engine's own client (mysql, psql, mongosh, cqlsh, gsql) or Data Admin Service (DAS), not hcloud
- Backup, restore, specification changes, or read-replica management on an existing instance
- Binding an EIP to a GaussDB instance when no confirmed hcloud operation exists (`GAP-DB-USE-105`) and the console is not acceptable to the requester
- When hcloud CLI is not available and cannot be installed

# Required inputs

- target_service (one of: rds, dds, geminidb, taurusdb, gaussdb)
- action (find, connect, or bind-eip)
- source_region
- instance_name or instance_id
- node_id (required for dds and geminidb when action is bind-eip; each binds per node, not per instance)
- approval_owner (required whenever action is bind-eip)

# Optional inputs

- eip_id (reuse an already-deployed EIP instead of creating a new one)
- eip_type (5_bgp or 5_sbgp; defaults to 5_bgp where unspecified)
- bandwidth_size, bandwidth_share_type, bandwidth_charge_mode (defaults: dedicated (PER), traffic-billed, size supplied by the approval owner)
- enterprise_project_id

# Required MCPs

None. All operations across all five database services and the EIP service are performed via hcloud CLI.

# Optional MCPs

- huaweicloud-ticket (only to open a support ticket if a capability-gap probe fails for a critical-path operation and manual escalation is desired)

# Tool selection policy

- Use hcloud CLI for ALL operations: finding instances, deploying the EIP, and binding it
- Never assume a database service has a dedicated EIP-bind operation without checking; RDS specifically does not, and binds through the generic `EIP AssociatePublicips` operation against the instance's private network port instead
- Because every bind-EIP operation in scope (except the generic RDS path) takes a small JSON request body, pass it through KooCLI's `--cli-jsonInput=<file>` option for consistency and to avoid quoting errors, even where a flattened `--param` form might also work
- Never assume an operation not in a service's confirmed-operations table (see `# Per-service operations`) is available without probing it live first (`hcloud <SERVICE_NAME> <OPERATION> --help`)
- Never use huaweicloud-ticket to substitute a missing capability with an invented command; it is for support escalation only
- Never use this skill to create, modify, or delete a VPC, subnet, or security group, or the security-group rule that opens the database port; resolve/modify these via the networking service/console
- For GaussDB specifically, since no EIP-bind operation could be confirmed under the current `GaussDB` service name at authoring time, probe `hcloud GaussDB --help` live before attempting anything beyond finding the instance; if unresolved, use the console

# Safety and approval gates

1. Any bind-eip action (across any of the five database services) requires explicit approval before execution — binding a public IP to a database instance is a security-relevant change that exposes it to the internet
2. Deploying a new EIP requires explicit approval — it is a billable resource
3. Reusing an existing EIP instead of deploying a new one still requires explicit confirmation from the approval owner, since it changes which resource is now publicly exposed
4. Before binding, this skill surfaces a reminder that binding an EIP does not by itself open the database port — the instance's security group must separately allow inbound access from the intended client IP(s) — but does not modify the security group itself
5. Unbinding an EIP from an instance is out of this skill's primary workflow but, if requested, requires explicit approval every time, since it is easy to mistake for a reversible/no-risk action when in fact it can interrupt existing public connections

# Rules

1. Each of the five database services in this skill's scope is exposed through hcloud CLI under its own distinct service name; there is no generic `Database` service name and no dedicated MCP for any of them, nor for EIP. [VERIFIED_FROM_PUBLIC_API_DOCS]

2. **EIP** is exposed under the hcloud service name `EIP`. Deploying an EIP (`POST /v1/{project_id}/publicips`) is confirmed with a full request/response parameter table from its own public API Reference page; the response's `publicip.id` and `publicip.public_ip_address` are the values every subsequent bind operation in this skill needs. Querying an EIP's status (`GET /v3/{project_id}/eip/publicips/{publicip_id}`) and the generic bind/unbind operations (`POST /v3/{project_id}/eip/publicips/{publicip_id}/associate-instance` and `.../disassociate-instance`) are each confirmed with a full request/response example from their own current (V3) API Reference pages. The literal `hcloud EIP <operation>` name strings used internally were not observed directly during authoring — only each API's documented function name and HTTP method/path were. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

3. **RDS** has no dedicated EIP-bind operation. It is confirmed (via RDS's own user guide and the official Terraform provider's documented RDS+EIP pattern) that public access is enabled by resolving the RDS instance's private network port — via its `private_ips` field, cross-referenced against the VPC service's own port-query operation — and then calling the generic `EIP AssociatePublicips` operation (Rule 2) against that port ID with `associate_instance_type: "PORT"`. The VPC port-query operation's exact name and query-parameter syntax were not independently confirmed during authoring; probe `hcloud VPC --help` before scripting it. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

4. **DDS** binds an EIP per node, not per instance, via a confirmed operation (`POST /v3/{project_id}/nodes/{node_id}/bind-eip`) whose HTTP method, path, and full request/response body were observed on its own API Reference page — reached via a regional mirror of the standard DDS API Reference during authoring, not the default-region page directly, though it is the same underlying product API. The literal operation-name string was not observed there; this skill uses the placeholder name `BindEip` and requires confirming the exact name via `hcloud DDS --help` before relying on it verbatim. Only primary and secondary nodes (replica-set instances) or mongos nodes (cluster instances) support EIP binding. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

5. **GeminiDB** (service name `NoSQL`) binds an EIP per node via `POST /v3/{project_id}/instances/{instance_id}/nodes/{node_id}/public-ip`, confirmed with a full request/response parameter table from its own current API Reference page, including the request body's `action` field (`BIND` or `UNBIND`), `public_ip`, and `public_ip_id`. This is the most fully confirmed EIP-bind operation in this skill's scope. The literal `hcloud NoSQL <operation>` name string was not observed directly; this skill uses the placeholder name `BindEip`. [VERIFIED_FROM_PUBLIC_API_DOCS] [PROBE_HELP_BEFORE_USE]

6. **TaurusDB** (service name `GaussDBforMySQL`) binds an EIP per instance via `PUT /v3/{project_id}/instances/{instance_id}/public-ips/bind`, confirmed with a full request/response example from its own current API Reference page. Unlike DDS and GeminiDB, this operation's literal name IS confirmed directly from its own API Reference page URL: `UpdateGaussMySqlInstanceEip`, following the same verbose `GaussMySql`-qualified naming already established for TaurusDB's other operations (e.g. `CreateGaussMySqlInstance`, `ListGaussMySqlInstanceDetailInfoUnifyStatus`). [VERIFIED_FROM_PUBLIC_API_DOCS]

7. **GaussDB** is this skill's most significant capability gap, directly analogous to GaussDB's create-instance gap in the companion `huawei-database-deploy-operations` skill. A "Binding or Unbinding an EIP" section was located in a GaussDB API Reference, but the copy found during authoring was explicitly for the Huawei Cloud Stack (private/on-premises deployment) edition, not the public cloud — the two are different product editions and their operation IDs are not guaranteed to match. No `hcloud GaussDB` EIP-bind operation name, parameter, or CLI behavior was confirmed against the public-cloud catalogue at authoring time. Before relying on any GaussDB EIP-bind operation, this skill MUST probe `hcloud GaussDB --help` live; if the operation is missing or its parameters cannot be confirmed on the API Explorer CLI Examples tab, use the console instead of guessing a command. [NOT_CONFIRMED] [PROBE_HELP_BEFORE_USE]

8. FIND BEFORE BIND: for every service, always resolve the target instance's (and, for DDS/GeminiDB, node's) current ID and status via a read operation before attempting to bind an EIP; never hardcode an instance or node ID. [VERIFIED_FROM_PUBLIC_API_DOCS]

9. Every EIP-deploy and bind-EIP request body is passed as a JSON file via `--cli-jsonInput=<file>`, for consistency across services and to avoid shell-quoting errors, even for the smaller bodies where a flattened form might work. [INFERRED] (explicit consistency preference carried over from the companion deployment skill)

10. VERIFY AFTER EVERY BIND: every bind-EIP action must be followed by that same service's find/list operation, confirming the EIP now appears against the target instance or node, and by a reminder (not an automatic action) that the security group must separately allow the intended client IP(s) on the database port before the instance is actually reachable. [VERIFIED_FROM_PUBLIC_API_DOCS] [INFERRED]

11. Every bind-eip action, and every EIP deployment, requires explicit approval before execution. [INFERRED]

12. This skill's scope excludes VPC/subnet/security-group creation and modification entirely, including the inbound security-group rule that actually opens the database port; it only resolves an RDS instance's network port ID read-only (Rule 3) and never creates, modifies, or deletes networking resources. [INFERRED] (explicit scope boundary carried over from the companion deployment skill)

13. Never include secrets (AK, SK, database passwords, tokens) in commands, JSON body files, examples, or logs; use the credentials already configured in the local hcloud profile. [INFERRED]

14. Each of the five database-service modules, and the EIP module, is independent: a request scoped to one service must not require having exercised any other service's workflow first (beyond the EIP itself needing to be deployed once before any bind step), and must not silently issue commands against a different service to compensate for a gap. [INFERRED] (explicit design requirement carried over from the companion deployment skill)

15. This skill was authored and verified from the official public API Reference pages for EIP (V1 create, V3 query/associate/disassociate), GeminiDB/NoSQL, and TaurusDB/GaussDBforMySQL, each with a full parameter table independently fetched and read; from a regional mirror of the standard DDS API Reference for DDS; and from RDS's own user guide plus the official Terraform provider's documented pattern for RDS (since RDS has no dedicated bind API of its own). GaussDB could not be confirmed at the public-cloud level at all. It was **not** executed against a live hcloud CLI installation or a live Huawei Cloud tenant. The first real use of this skill for any given service in any environment MUST start with that service's discovery probe (`hcloud <SERVICE_NAME> --help`) before relying on any operation not in its confirmed-operations table. [NOT_LIVE_TESTED]

# Prerequisites

| Tool or resource | Required | Purpose | Verification |
|---|---:|---|---|
| hcloud CLI (KooCLI) | Yes | All operations across EIP and all five database services | `hcloud version` |
| Huawei Cloud authentication (AK/SK) | Yes | API access | `hcloud configure show --cli-profile=default` |
| An already-existing, running database instance | Yes | This skill uses, but does not create, instances | Resolved via that service's find/list operation |
| An existing VPC, subnet, and security group associated with the instance | Yes | Needed to resolve the RDS network port (Rule 3) and to remind the operator to open the database port | Resolve read-only via the VPC service/console; this skill does not create or modify them |
| Target region (service-supported) | Yes | Service region/endpoint | Confirm via a successful `hcloud <SERVICE_NAME> --help`/discovery call |
| EIP-deploy and EIP-bind permission for the target service | Only if action=bind-eip | Ability to deploy/bind the EIP | Confirmed only by a successful call or console check |
| Approval owner | Yes (for bind-eip actions and EIP deployment) | Authorizes write operations | Specified in intent |
| huaweicloud-ticket MCP | No | Support escalation if a capability gap blocks a critical-path request | MCP availability check |

# Workflow

## STEP 1 — PARSE INTENT

**Classification: AUTOMATED**

**Objective**: Extract target_service, action, region, and instance/node/EIP parameters from the request.

**Preconditions**: None.

**Command**: None (parsing logic).

**Approval requirement**: None.

**Verification**: Confirm target_service is exactly one of `rds`, `dds`, `geminidb`, `taurusdb`, `gaussdb`, and action is one of `find`, `connect`, `bind-eip`.

**Expected result**: Complete intent object with a single target_service.

**Failure action**: If target_service is missing, ambiguous, or not one of the five, STOP and request clarification. Do not guess which service was meant.

**Evidence artifact**: `artifacts/db-use-intent.json`

## STEP 2 — DISCOVER AUTHENTICATION AND REGION

**Classification: ASSISTED**

**Objective**: Verify hcloud CLI is installed/configured for the target region.

**Inputs**: source_region.

**Preconditions**: hcloud CLI installed (see `# Prerequisites` above).

**Commands** (read-only):

```bash
hcloud version
hcloud configure show --cli-profile=default
```

**Approval requirement**: None.

**Verification**: Version and profile confirmed.

**Expected result**: Authentication valid.

**Failure action**: STOP. Report the authentication/configuration error.

**Evidence artifact**: `artifacts/db-use-auth-discovery.json`

## STEP 3 — FIND THE TARGET INSTANCE

**Classification: ASSISTED**

**Objective**: Confirm the target service responds, and resolve the target instance's (and, for DDS/GeminiDB, node's) current ID, status, and network details.

**Inputs**: target_service, instance_name or instance_id.

**Preconditions**: Step 2 completed.

Consult the dedicated section for the target service (see `# Per-service operations`) and run its Find command. For DDS and GeminiDB, additionally identify the specific node_id that will receive the EIP.

**Approval requirement**: None.

**Verification**: Exactly one instance resolves for the given name/ID; the instance's status indicates it is running/normal, not being created, deleted, or in an error state.

**Expected result**: instance_id (and, where relevant, node_id) resolved; current network state (private IP, existing public IP if any) recorded.

**Failure action**: STOP. If zero or multiple instances match, do not guess; report and request the operator to disambiguate. For GaussDB, a failure here that traces back to an unconfirmed operation directly confirms `GAP-DB-USE-105`.

**Evidence artifact**: `artifacts/db-use-instance-resolution.json`

## STEP 4 — RUN THE REQUESTED ACTION

**Classification: ASSISTED**

**Objective**: Execute `find` (stop after Step 3), `connect` (surface connection details only), or `bind-eip` (deploy/reuse an EIP and bind it, per the target service's confirmed mechanism).

**Inputs**: target_service, instance_id/node_id, eip_id (if reusing), EIP deployment parameters (if deploying new).

**Preconditions**: Steps 1-3 completed.

If action is `find`: stop here; Step 3's result is the answer.

If action is `connect`: from the instance details already resolved, surface the connection endpoint (private IP, and public IP if already bound), port, and a reminder of which client (mysql/psql/mongosh/cqlsh/gsql) applies to this engine; do not proceed to bind-eip unless separately requested.

If action is `bind-eip`:
1. If no `eip_id` was supplied, request explicit approval to deploy a new EIP (see `# Per-service operations` → EIP), run the deploy command, and record the returned `eip_id`/`public_ip_address`. If reusing an existing `eip_id`, still request explicit confirmation.
2. Request explicit approval for the bind itself, naming the target instance/node and the EIP.
3. Run the target service's confirmed bind mechanism (see `# Per-service operations`) — the generic `EIP AssociatePublicips` call for RDS, or the service-specific bind operation for DDS/GeminiDB/TaurusDB. For GaussDB, do not proceed past a live `hcloud GaussDB --help` probe unless it confirms a usable operation; otherwise route to the console.
4. Re-run the service's find operation to verify the EIP now appears against the instance/node.
5. Surface the standing reminder that the security group must separately allow the intended client IP(s) on the database port; do not modify the security group.

**Approval requirement**: EXPLICIT for any bind-eip action, and for any new EIP deployment; none for find/connect.

**Verification**: Per the target service's section; the instance's (or node's) public IP field matches the bound EIP.

**Expected result**: The requested instance/node state confirmed.

**Failure action**: STOP on any error; do not retry with a different, invented command; do not fall back to a different service without a new approval and a documented reason.

**Evidence artifact**: `artifacts/db-use-execution-result.json`, `artifacts/db-use-verification.json`

## STEP 5 — CLOSURE

**Classification: AUTOMATED**

**Objective**: Generate final summary, evidence, and follow-up actions.

**Inputs**: All artifacts from Steps 1-4.

**Preconditions**: All previous steps completed.

Generate:
- Final summary (target_service, action, region, instance_id/node_id, eip_id/public_ip_address if applicable, result)
- Capability probe result for the target service (so future runs against the same tenant/CLI version can skip re-probing confirmed operations, but MUST re-probe any operation still marked unconfirmed, and MUST always re-probe GaussDB)
- Warnings (for example, if a known gap was encountered and routed to the console, or if the security-group reminder was surfaced but not acted on)
- Explicit statement that no other of the five services, and no networking resource beyond reading the RDS port ID, was touched during this run
- Follow-up actions (for example: "open an inbound security-group rule for the client's IP on port <db_port>" if the instance is still not reachable)
- Unresolved risks

Do NOT perform any unbind/rollback action automatically in this closure step.

**Expected result**: Complete closure report.

**Evidence artifact**: `artifacts/db-use-final-report.md`

# Per-service operations

Only the section for the request's `target_service` (plus EIP, which every bind-eip action depends on) is used; the sections below are otherwise independent of each other.

### EIP (service name: `EIP`)

Standalone public IP address and bandwidth resource.

Confirmed operations (full parameter table verified against the operation's own API Reference page):

| Operation | HTTP method / path | Key parameters |
|---|---|---|
| Deploy EIP (`CreateEip`, name unconfirmed) | `POST /v1/{project_id}/publicips` | publicip.type (5_bgp/5_sbgp), publicip.ip_version, bandwidth.name/size/share_type/charge_mode (required), enterprise_project_id |
| Query EIP (`ShowPublicipV3`) | `GET /v3/{project_id}/eip/publicips/{publicip_id}` | publicip_id (path) |
| Bind EIP (`AssociatePublicips`) | `POST /v3/{project_id}/eip/publicips/{publicip_id}/associate-instance` | publicip.associate_instance_id (required), publicip.associate_instance_type (required — `PORT` for a database's network port) |
| Unbind EIP (`DisassociatePublicips`) | `POST /v3/{project_id}/eip/publicips/{publicip_id}/disassociate-instance` | publicip_id (path) |

**Deploy:**
```bash
hcloud EIP CreateEip --cli-region=<REGION> --cli-jsonInput=./eip-create.json
```
Contents of `eip-create.json`:
```json
{
  "publicip": { "type": "5_bgp", "ip_version": 4 },
  "bandwidth": { "name": "<bandwidth-name>", "size": 5, "share_type": "PER", "charge_mode": "traffic" }
}
```
The response returns `publicip.id` and `publicip.public_ip_address`.

**Query:**
```bash
hcloud EIP ShowPublicipV3 --cli-region=<REGION> --publicip_id="<EIP_ID>"
```

**Bind** (used by RDS, and as the underlying mechanism the other services' own bind operations abstract over):
```bash
hcloud EIP AssociatePublicips --cli-region=<REGION> --publicip_id="<EIP_ID>" --cli-jsonInput=./eip-bind.json
```
```json
{ "publicip": { "associate_instance_id": "<PORT_ID>", "associate_instance_type": "PORT" } }
```

Known gap (`GAP-DB-USE-101`): the literal `hcloud EIP <operation>` name strings were not observed directly during authoring — only each API's documented function name and HTTP method/path were, each independently confirmed with a full parameter table. Probe `hcloud EIP --help` before relying on the names used above verbatim.

### RDS (service name: `RDS`)

No dedicated EIP-bind operation exists; RDS is bound through the generic EIP service acting on its network port.

**Find:**
```bash
hcloud RDS ListInstances --cli-region=<REGION> --name="<instance-name>"
```
Record `id` and the `private_ips` array from the response.

**Resolve the network port (VPC, operation name unconfirmed):**
```bash
hcloud VPC ListPorts --cli-region=<REGION> --fixed_ips="ip_address=<PRIVATE_IP>"
```
Probe `hcloud VPC --help` before relying on this exact operation name/syntax; it was not independently confirmed during authoring. Record the returned port's `id`.

**Bind:**
```bash
hcloud EIP AssociatePublicips --cli-region=<REGION> --publicip_id="<EIP_ID>" --cli-jsonInput=./rds-bind-eip.json
```
```json
{ "publicip": { "associate_instance_id": "<PORT_ID>", "associate_instance_type": "PORT" } }
```

**Verify:**
```bash
hcloud RDS ListInstances --cli-region=<REGION> --id="<INSTANCE_ID>"
```

Known gap (`GAP-DB-USE-102`): the VPC port-query operation's exact name and query-parameter syntax were not independently confirmed during authoring. Probe `hcloud VPC --help` before scripting it.

### DDS (service name: `DDS`)

Binds an EIP per node (mongos node for cluster instances; primary/secondary node for replica-set instances).

**Find:**
```bash
hcloud DDS ListInstances --cli-region=<REGION> --name="<instance-name>"
```
Record `id` and, from the instance's node list, the target `node_id`.

**Bind** (operation name unconfirmed; placeholder `BindEip` used):
```bash
hcloud DDS BindEip --cli-region=<REGION> --node_id="<NODE_ID>" --cli-jsonInput=./dds-bind-eip.json
```
```json
{ "public_ip": "<EIP_ADDRESS>", "public_ip_id": "<EIP_ID>" }
```
The response returns `job_id`, `node_id`, `node_name`, `public_ip`, `public_ip_id`.

**Verify:**
```bash
hcloud DDS ListInstances --cli-region=<REGION> --id="<INSTANCE_ID>"
```

Known gap (`GAP-DB-USE-103`): this operation's HTTP method, path, and request/response body were confirmed via a regional mirror of the standard DDS API Reference rather than the default-region page directly (the same underlying product API). The literal operation-name string was not observed. Probe `hcloud DDS --help` before relying on `BindEip` as the exact name.

### GeminiDB (service name: `NoSQL`)

Binds an EIP per node. This is the most fully confirmed bind operation in this skill's scope.

**Find:**
```bash
hcloud NoSQL ListInstances --cli-region=<REGION> --name="<instance-name>"
```
Record `id` and, from the instance's node list, the target `node_id`.

**Bind** (operation name unconfirmed; placeholder `BindEip` used):
```bash
hcloud NoSQL BindEip --cli-region=<REGION> --instance_id="<INSTANCE_ID>" --node_id="<NODE_ID>" --cli-jsonInput=./geminidb-bind-eip.json
```
```json
{ "action": "BIND", "public_ip": "<EIP_ADDRESS>", "public_ip_id": "<EIP_ID>" }
```
The response returns `job_id`. To unbind, resend with `"action": "UNBIND"` and only `public_ip`.

**Verify:**
```bash
hcloud NoSQL ListInstances --cli-region=<REGION> --id="<INSTANCE_ID>"
```

Known gap (`GAP-DB-USE-104`): the literal `hcloud NoSQL <operation>` name string was not observed directly, despite the full request/response parameter table being confirmed. Probe `hcloud NoSQL --help` before relying on `BindEip` as the exact name.

### TaurusDB (service name: `GaussDBforMySQL`)

Binds an EIP per instance. This operation's name IS confirmed directly (unlike DDS/GeminiDB's bind operations).

**Find:**
```bash
hcloud GaussDBforMySQL ListGaussMySqlInstanceDetailInfoUnifyStatus --cli-region=<REGION> --name="<instance-name>"
```
Record `id`; the response also includes `public_ips`, useful for confirming whether an EIP is already bound.

**Bind** (`UpdateGaussMySqlInstanceEip`, confirmed):
```bash
hcloud GaussDBforMySQL UpdateGaussMySqlInstanceEip --cli-region=<REGION> --instance_id="<INSTANCE_ID>" --cli-jsonInput=./taurusdb-bind-eip.json
```
```json
{ "public_ip": "<EIP_ADDRESS>", "public_ip_id": "<EIP_ID>" }
```
The response returns `job_id`.

**Verify:**
```bash
hcloud GaussDBforMySQL ListGaussMySqlInstanceDetailInfoUnifyStatus --cli-region=<REGION> --id="<INSTANCE_ID>"
```
Confirm `public_ips` is now populated.

No open gap beyond the general caution (Rule 15) that this was not live-tested.

### GaussDB (service name: `GaussDB` — NOT independently confirmed at the public-cloud KooCLI level)

**Find:**
```bash
hcloud GaussDB --help
```
No instance-listing operation for GaussDB was confirmed during authoring; probe `--help` live to discover the current catalogue for your account before proceeding.

**Bind**: no confirmed operation (`GAP-DB-USE-105`). Do not invent one.

Known gap (`GAP-DB-USE-105`): this is this skill's most significant capability gap, directly analogous to GaussDB's create-instance gap in the companion `huawei-database-deploy-operations` skill. A "Binding or Unbinding an EIP" section exists in a GaussDB API Reference, but the copy located during authoring was for the Huawei Cloud Stack (private/on-premises deployment) edition, not the public cloud — a different product edition whose operation IDs are not guaranteed to match the public-cloud catalogue. Before relying on any GaussDB operation, this skill MUST probe `hcloud GaussDB --help` live and cross-check the operation's own API Explorer "CLI Examples" tab; if the operation is missing, unclear, or its parameters cannot be confirmed, use the console instead of guessing a command.

# Capability gap handling

When a capability required for an EIP/RDS/DDS/GeminiDB/TaurusDB/GaussDB operation is not available or not confirmed:

1. Document the gap with Gap ID, phase (service), and impact (see `# Per-service operations` and the known gaps below)
2. Classify the gap: critical path (blocks the requested action) or optional
3. Evaluate alternatives:
   - Can the step be performed via hcloud CLI after a live `--help` probe? → PROBE_HELP_BEFORE_USE (preferred)
   - Can it only be done manually in the console? → USE_MANUAL_CONSOLE_FALLBACK
   - Can an existing MCP tool accomplish the task? → USE_EXISTING_TOOL (not applicable to any gap in this skill)
   - Is a new MCP needed? → CREATE_NEW_MCP (last resort; not applicable to any gap in this skill)
4. Never auto-activate a generated MCP or invent an undocumented command as a workaround
5. Update the affected service's status in this document's `# Known limitations` section if critical gaps remain

Known capability gaps:

- GAP-DB-USE-101 (EIP): the literal `hcloud EIP <operation>` name strings were not observed directly during authoring, despite each operation's HTTP method/path/parameters being independently confirmed with a full table.
- GAP-DB-USE-102 (RDS): the VPC port-query operation used to resolve an RDS instance's network port was not independently confirmed — name and query syntax unverified.
- GAP-DB-USE-103 (DDS): the bind-EIP operation's body was confirmed via a regional mirror of the standard DDS documentation, and its literal operation name was not observed.
- GAP-DB-USE-104 (GeminiDB/NoSQL): the bind-EIP operation's full parameter table is confirmed, but its literal operation name was not observed.
- GAP-DB-USE-105 (GaussDB): no EIP-bind (or instance-find) operation name, parameter, or CLI behavior was confirmed against the public-cloud API Explorer/KooCLI catalogue; the only "Binding or Unbinding an EIP" reference found was for the Huawei Cloud Stack private-cloud edition, a different product from the public cloud. This is a critical-path gap for any GaussDB bind-eip action.
- GAP-DB-USE-000: No dedicated MCP exists for EIP or any of the five database services in this skill's scope; all operations via hcloud CLI. [VERIFIED_FROM_PUBLIC_API_DOCS]
- GAP-DB-USE-999: This skill has not been executed against a live hcloud CLI installation or live tenant for any of the six services in scope; all CLI syntax is derived from public (and, for DDS, regionally-mirrored) API Reference documentation, not from `--help` output captured live. [NOT_LIVE_TESTED]

# Output artifacts

- artifacts/db-use-intent.json — Parsed intent (target_service, action, instance/node/EIP parameters)
- artifacts/db-use-auth-discovery.json — Authentication and hcloud version/profile check
- artifacts/db-use-instance-resolution.json — Resolved instance_id/node_id, status, and network details
- artifacts/db-use-execution-result.json — Result of the find/connect/bind-eip action executed
- artifacts/db-use-verification.json — Post-action verification (read-back) result
- artifacts/db-use-final-report.md — Closure report

# Troubleshooting

| Symptom | Likely cause | Diagnosis | Resolution |
|---|---|---|---|
| `hcloud: command not found` | KooCLI not installed or not in PATH | `hcloud version` | Install KooCLI; add `/usr/local/bin` to PATH |
| Authentication failure | hcloud profile misconfigured | `hcloud configure show --cli-profile=default` | Re-run `hcloud configure init` |
| No instance resolves by name | Instance doesn't exist in this region/project, or was named differently | Re-run the service's find operation with a broader filter | Confirm the instance name/region/project with the requester |
| `AssociatePublicips` (or a service-specific bind operation) rejects with "already bound" | The EIP is already associated with another resource | `EIP ShowPublicipV3` on the target EIP | Unbind it first (`EIP DisassociatePublicips`, or the target service's own unbind call) before binding elsewhere |
| Bind succeeds but the instance is still unreachable | The security group has no inbound rule for the client's IP on the database port | Check the instance's security group rules (out of this skill's scope to modify) | Ask the network owner to add the missing inbound rule; this skill only surfaces the reminder, never modifies the security group |
| RDS port resolution (`VPC ListPorts`) returns zero or multiple ports | The instance's `private_ips` value is stale, or multiple ports share that fixed IP unexpectedly | Re-run `RDS ListInstances` to refresh `private_ips` | Re-resolve and retry; if still ambiguous, escalate rather than guessing which port to use |
| `hcloud <SERVICE_NAME> --help` missing an expected operation | Older KooCLI/API Explorer metadata, or the operation genuinely does not exist under this service | Compare against that service's confirmed-operations table in `# Per-service operations` above | Use the console instead of inventing a substitute |
| `hcloud GaussDB --help` behaves unexpectedly or lacks a bind/find operation | Known gap `GAP-DB-USE-105`: unconfirmed at the public-cloud level | `hcloud GaussDB --help` | Use the console for GaussDB usage/EIP binding |
| A bind or deploy operation is rejected (403/permission) | Tenant lacks the specific EIP or database-service permission for that action | Error message from the call | Request the specific permission from an administrator |
| Region mismatch between plan and call | `--cli-region` omitted or wrong on a later command | Compare command flags across steps | Ensure every command for the same operation uses the same `--cli-region` |

# Failure handling

- Authentication failure: verify hcloud config, region, IAM permissions. Do not retry with different credentials without operator confirmation.
- Instance not found / ambiguous: stop; report and request disambiguation from the requester.
- Service unreachable / operation missing: cross-check against the target service's confirmed-operations table before assuming a transient error; if genuinely missing, use the console fallback, never an invented command.
- Write operation (EIP deploy or bind) rejected for a permission reason: report; do not retry with different credentials without operator confirmation.
- Write operation rejected for any other reason: STOP, preserve evidence, report to approval owner; do not retry with a different, invented command.
- Bind succeeds but connectivity verification fails: report the likely security-group cause (per Troubleshooting); do not modify the security group and do not unbind automatically.

# Recovery procedure

1. If failure during discovery (Steps 2-3): no resource created or bound. Fix authentication/region/instance-lookup issue and retry from Step 2.
2. If failure resolving the RDS network port (Step 4, RDS only): re-run `RDS ListInstances` to refresh `private_ips`, then retry the VPC port lookup once corrected.
3. If failure during EIP deployment: check the error. If authorization-related, request the specific permission with a new approval request. If a bandwidth/quota error, adjust the requested bandwidth size and retry with a fresh approval.
4. If failure during the bind sub-action: check the error (already-bound EIP, invalid instance/node state). Correct and retry with a fresh approval if the EIP or target instance/node changed.
5. If bind succeeds but verification (actual connectivity) fails: do not unbind or redeploy automatically; report the likely security-group cause and await a decision.
6. Never expand recovery into a different service's module, or into networking resource changes (VPC/subnet/security-group), to compensate for a failure.

# Rollback

Unbinding an EIP from an instance is the natural "undo" for a bind-eip action, and — unlike the companion deployment skill's delete-instance rollback — every service in this skill's confirmed scope (except GaussDB) has a confirmed or strongly-implied unbind path:

**EIP (generic, used for RDS):**
```bash
hcloud EIP DisassociatePublicips --cli-region=<REGION> --publicip_id="<EIP_ID>"
```
Confirmed with a full example from its own API Reference page.

**DDS:** resend the bind operation's request with the DDS-documented unbind semantics observed alongside the bind body (a `public_ip`-only payload against the same `bind-eip`-family endpoint); confirm the exact shape via `hcloud DDS --help` and its own CLI Examples tab before relying on it, since (per `GAP-DB-USE-103`) the operation name itself is unconfirmed.

**GeminiDB (NoSQL):** confirmed — resend the same bind endpoint with `{"action": "UNBIND", "public_ip": "<EIP_ADDRESS>"}` (Rule 5 / `# Per-service operations` → GeminiDB).

**TaurusDB (GaussDBforMySQL):** an unbind counterpart to `UpdateGaussMySqlInstanceEip` is expected to exist by analogy but was not independently confirmed during authoring; probe `hcloud GaussDBforMySQL --help` first.

**GaussDB:** no operation of any kind is confirmed (`GAP-DB-USE-105`); an unbind/rollback request must go through the console.

Do NOT unbind or redeploy an EIP automatically after a failure in any phase. Do NOT invent an unbind command not confirmed (or, for TaurusDB, strongly implied) to exist for that specific service. Do NOT touch networking resources (VPC/subnet/security-group) as part of any rollback in this skill.

# Evidence and traceability

- All hcloud CLI commands logged with timestamps
- instance_id, node_id (where applicable), eip_id, and public_ip_address recorded in artifacts
- Approval decisions recorded with approver identity and timestamp
- Per-service capability probe results recorded and reusable across runs against the same tenant/CLI version (re-probe if either changes, and always re-probe GaussDB and any operation still marked unconfirmed for that service)
- No secrets (AK/SK, database passwords) in any artifact

# Known limitations

- No dedicated MCP exists for EIP or any of the five database services in this skill's scope [VERIFIED_FROM_PUBLIC_API_DOCS]
- GaussDB's EIP-bind (and instance-find) capability is entirely unresolved at the public-cloud KooCLI level; only a private-cloud (Huawei Cloud Stack) API reference confirms a "Binding or Unbinding an EIP" section exists at all, for a different product edition [NOT_CONFIRMED] [GAP-DB-USE-105]
- The literal `hcloud EIP`, `hcloud DDS`, and `hcloud NoSQL` bind-operation name strings were not captured from a live `--help` call, though every operation's HTTP method/path/parameters were independently confirmed with a full table (except RDS's underlying VPC port-query step, which is unconfirmed at the parameter level too)
- This skill's scope explicitly excludes database-instance creation (see the companion deploy skill), VPC/subnet/security-group creation or modification (including the inbound rule that actually opens the database port), in-instance database/schema/user management, backup/restore, and specification changes
- No live hcloud CLI or tenant test was performed during authoring

# Status justification

Status: READY_WITH_WARNINGS

Evidence:
- EIP (`EIP`): deploy (`POST /v1/{project_id}/publicips`), query (`GET /v3/.../{publicip_id}`), bind, and unbind (`POST /v3/.../associate-instance` and `.../disassociate-instance`) each confirmed with a full request/response parameter table or example from their own current API Reference pages. [VERIFIED_FROM_PUBLIC_API_DOCS]
- RDS (`RDS`): binds via the generic EIP mechanism against its network port; this pattern is confirmed via RDS's own user guide and the official Terraform provider's documented example, though the VPC port-query step itself is unconfirmed at the parameter level. [VERIFIED_FROM_PUBLIC_API_DOCS] [PARTIAL]
- DDS (`DDS`): bind-EIP operation's HTTP method/path/body confirmed via a regional mirror of the standard API Reference; operation name unconfirmed. [PARTIAL] [PROBE_HELP_BEFORE_USE]
- GeminiDB (`NoSQL`): bind-EIP operation confirmed with a full parameter table from its own current API Reference page — the most fully confirmed bind operation in this skill; operation name unconfirmed. [VERIFIED_FROM_PUBLIC_API_DOCS] [PARTIAL]
- TaurusDB (`GaussDBforMySQL`): bind-EIP operation (`UpdateGaussMySqlInstanceEip`) confirmed with a full example AND its literal operation name, directly from its own API Reference page URL. [VERIFIED_FROM_PUBLIC_API_DOCS]
- GaussDB (`GaussDB`): no operation confirmed at the public-cloud KooCLI/API Explorer level; only a private-cloud (Huawei Cloud Stack) reference confirms the capability exists by name for a different product edition. [NOT_CONFIRMED]
- No dedicated MCP exists for EIP or any of the five database services [VERIFIED_FROM_PUBLIC_API_DOCS]
- All bind-eip actions and EIP deployments require explicit approval [INFERRED]
- No cloud-side or CLI-side live test was executed for any of the six services in scope; this authoring environment had web-search/fetch access to public (and, for DDS, regionally-mirrored) documentation only, not a live hcloud CLI install or Huawei Cloud credentials [NOT_LIVE_TESTED]
- Because of the above, this skill mandates a live per-operation probe (`hcloud <SERVICE_NAME> <OPERATION> --help`) before any workflow instance relies on an operation outside the confirmed-operations table for its target service, and documents an explicit console fallback for the one service (GaussDB) where no operation could be confirmed at the public-cloud level at all
