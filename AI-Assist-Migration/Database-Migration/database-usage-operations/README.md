# Database Usage Operations

Complete toolkit for operating already-deployed Huawei Cloud database instances -- RDS, DDS, GeminiDB, TaurusDB, and GaussDB -- via hcloud CLI (KooCLI): find an instance, read its connection details, and assign it an Elastic IP (EIP) for public access.

Includes 1 skill for AI agents (OpenCode, Hermes), covering instance discovery, EIP deployment, EIP binding, and post-bind verification across five database services with per-service bind mechanisms.

---

## What This Skill Does and Why It Is Useful

### The Problem

When you need to make an already-deployed database instance publicly reachable:

- Each database service (RDS, DDS, GeminiDB, TaurusDB, GaussDB) binds EIPs through its own mechanism
- RDS has no dedicated EIP-bind operation -- it uses the generic `EIP AssociatePublicips` against the instance's private network port
- DDS and GeminiDB bind per node, not per instance -- you need the specific node ID
- GaussDB has an unresolved capability gap at the public-cloud level
- Binding an EIP does not by itself open the database port -- the security group must separately allow inbound access
- You need explicit approval before exposing a database to the internet

### The Solution: Per-Service EIP Binding via hcloud CLI

```
  PARSE INTENT      DISCOVER AUTH     FIND INSTANCE     DEPLOY EIP
  (target service)  (hcloud config)   (by name/ID)      (EIP service)
      |                  |                  |                |
      v                  v                  v                v
  Step 1              Step 2            Step 3            Step 4

  BIND EIP           VERIFY
  (per-service)      (reachable?)
      |                  |
      v                  v
  Step 5            Step 6
```

#### Skill: huawei-database-usage-operations

**What it does:** Finds existing database instances, reads their connection details, and assigns public reachability by deploying an EIP and binding it to the instance (or a specific node for DDS/GeminiDB).

**Per-service bind mechanisms:**

| Service | hcloud name | EIP-bind mechanism | Status |
|---------|-----------|-------------------|--------|
| RDS | `RDS` | Generic: `EIP AssociatePublicips` against private network port | Confirmed |
| DDS | `DDS` | Dedicated per-node bind operation | Confirmed |
| GeminiDB | `NoSQL` | Dedicated per-node bind operation | Fully confirmed |
| TaurusDB | `GaussDBforMySQL` | Dedicated per-instance bind (`UpdateGaussMySqlInstanceEip`) | Fully confirmed |
| GaussDB | `GaussDB` | Not confirmed at public-cloud level | Capability gap |

**What it produces:** A database instance with a bound EIP, reachable from outside its VPC, plus a reminder to open the security group port.

---

## What This Package Includes

```
database-usage-operations/
|
|-- huawei-database-usage-operations/   The operations skill
|   |-- SKILL.md                        Metadata + step-by-step instructions
|   |-- scripts/                        Executable scripts
|   |-- references/                     Per-service documentation
|   +-- artifacts/                      Evidence artifacts (intent, auth, results)
|
+-- README.md                           (this file)
```

---

## Installation

### Option A: OpenCode

```bash
mkdir -p ~/.opencode/skills
cp -r huawei-database-usage-operations ~/.opencode/skills/
```

### Option B: Hermes Agent

```bash
cp -r huawei-database-usage-operations ~/.hermes/skills/database/
```

---

## How to Use the Skill with an AI Agent

### Natural Triggers

```
"Find my RDS instance and show its connection details"
"Bind an EIP to my DDS instance for public access"
"Make my GeminiDB cluster reachable from outside the VPC"
"List all database instances that have a public IP"
```

### Workflow Summary

```
Step 1: PARSE INTENT      Extract target_service, action, region      -> intent.json
        |                  (rds, dds, geminidb, taurusdb, gaussdb)
        v
Step 2: DISCOVER AUTH     Verify hcloud CLI + credentials             -> auth.json
        |                  hcloud version, hcloud configure show
        v
Step 3: FIND INSTANCE     Locate instance by name or ID              -> instance details
        |                  Read status, datastore, network info
        v
Step 4: DEPLOY EIP        Create new EIP or reuse existing           -> eip_id, public_ip
        |                  (requires explicit approval)
        v
Step 5: BIND EIP          Per-service bind mechanism                 -> eip bound
        |                  RDS: generic port associate
        |                  DDS/GeminiDB: per-node bind
        |                  TaurusDB: per-instance bind
        v
Step 6: VERIFY            Confirm EIP appears on instance            -> reachable
        |                  Remind: open security group port
```

---

## Quick Reference

### Find an RDS Instance

```bash
hcloud RDS ListInstances --cli-region=<region> --cli-output=json
```

### Deploy an EIP

```bash
hcloud EIP CreatePublicip --cli-region=<region> \
  --cli-jsonInput=eip_config.json --cli-output=json
```

### Bind EIP to DDS Node

```bash
hcloud DDS BindEip --cli-region=<region> \
  --node_id=<node-id> --public_ip=<eip-address> \
  --cli-output=json
```

### Bind EIP to TaurusDB Instance

```bash
hcloud GaussDBforMySQL UpdateGaussMySqlInstanceEip --cli-region=<region> \
  --instance_id=<instance-id> --public_ip=<eip-address> \
  --cli-output=json
```

---

## Requirements

| Component | Requirement |
|------------|-----------|
| hcloud CLI | Installed and configured with AK/SK |
| Database instance | Already deployed and running (RDS, DDS, GeminiDB, TaurusDB, or GaussDB) |
| EIP permissions | Ability to deploy and bind EIPs |
| Approval owner | Required for all bind-eip and EIP-deploy actions |
| Security group | Must separately allow inbound on the database port (not automated) |

---

## Safety and Approval Gates

1. **Bind-eip requires explicit approval** -- exposes a database to the internet
2. **EIP deployment requires explicit approval** -- creates a billable resource
3. **Reusing an existing EIP still requires confirmation** -- changes which resource is publicly exposed
4. **Security group reminder** -- binding an EIP does not open the database port; the SG must allow it
5. **GaussDB gap** -- probe `hcloud GaussDB --help` before attempting; use console if unavailable

---

*Skills: huawei-database-usage-operations*
*Services: RDS, DDS, GeminiDB, TaurusDB, GaussDB*
*Mechanism: hcloud CLI + EIP service*
