# PostgreSQL ECS to RDS — DRS cross-region migration

Migrate an existing self-managed PostgreSQL database running on a Huawei Cloud ECS to a
new RDS for PostgreSQL instance in a different region, using DRS Full + Incremental
synchronization.

## At a glance

| | |
|---|---|
| **Source** | Self-managed PostgreSQL on ECS — **already exists**, the customer's |
| **Target** | RDS for PostgreSQL — created by this skill, in another region |
| **Mechanism** | DRS Full + Incremental over public EIP |
| **MCPs required** | `hcloud`, `terraform` — nothing else |
| **Connectivity** | Public Internet, port 5432 restricted to a `/32` |
| **Downtime** | Cutover only; the source stays live throughout |

## Architecture

```
   SOURCE REGION                              TARGET REGION
┌──────────────────────┐                 ┌─────────────────────────┐
│  ECS                 │                 │  VPC                    │
│  ┌────────────────┐  │                 │  ┌───────────────────┐  │
│  │ PostgreSQL     │  │   public EIP    │  │ DRS replication   │  │
│  │ (self-managed) │◄─┼─────────────────┼──┤ instance          │  │
│  └────────────────┘  │   TCP 5432      │  └─────────┬─────────┘  │
│                      │   /32 only      │            │ private    │
│  EIP ────────────────┼─                │            ▼            │
│                      │                 │  ┌───────────────────┐  │
│  SG: ingress 5432    │                 │  │ RDS PostgreSQL    │  │
│      from DRS EIP/32 │                 │  └───────────────────┘  │
└──────────────────────┘                 └─────────────────────────┘
     customer's, untouched                    created by this skill
```

Only the **source** security group needs a new rule. The DRS instance reaches the target
privately inside the VPC.

## Requirements

Two general-purpose MCP servers:

| MCP | Used for |
|---|---|
| `hcloud` | Discovery, DRS lifecycle, RDS database creation, security group rules |
| `terraform` | Target VPC, subnet, security group and RDS instance |

No scenario-specific MCP. No browser automation.

**Your assistant must be in an executing mode** — Build in OpenCode, not Plan. In planning
mode the commands are only displayed, and you reach the end of the workflow with nothing
actually created. Step 0 checks this.

Full checklist: [`references/prerequisites.md`](references/prerequisites.md).

## Installation

```bash
# OpenCode
cp -r postgresql-ecs-to-rds-drs ~/.opencode/skills/

# Claude Code
cp -r postgresql-ecs-to-rds-drs ~/.claude/skills/

# Hermes
cp -r postgresql-ecs-to-rds-drs ~/.hermes/skills/
```

## Starting the migration

Copy this, replace the values in `<angle brackets>`, and send it.

```
/postgresql-ecs-to-rds-drs

Using this skill and the "hcloud" and "terraform" MCPs, migrate my PostgreSQL
database. Go step by step and stop at every approval gate.

SOURCE (already exists — do not modify it, do not connect to it via SSH):
- Region: <source region, e.g. ap-southeast-3>
- Public IP (EIP): <source EIP>
- Port: <port, usually 5432>
- Database name: <database to migrate>
- Replication user: <user with REPLICATION, e.g. drs_replicator>
- Security group ID: <source security group ID>

TARGET (does not exist yet — create it):
- Region: <target region, must differ from the source>

Start at Step 0 and wait for my confirmation at each gate. When you need me to
run something on the source, give me the complete command and wait.
```

### Only two things are truly required

**The source details** — region, EIP, database name, replication user, security group ID.
The skill cannot discover these, and guessing them is not acceptable.

**The target region** — and it must differ from the source region.

Everything else is asked along the way, with defaults offered.

### Optional additions

Add any of these if you already know the answer; otherwise the skill asks.

```
- Existing network: use VPC <vpc-id> and subnet <subnet-id> in the target region
  (otherwise a new VPC and subnet are created)

- Sizing: use flavor <flavor-id> with <n> GB of <storage type>
  (otherwise sizing is proposed based on the source)

- DRS task name: <name>

- This is a test migration, no application will be cut over
```

### What you will be asked for during the run

- **The RDS administrator password.** The format rules are explained before the request.
- **Access Key and Secret Key**, if not already in the environment. Terraform authenticates
  separately from the CLI and cannot reuse the CLI's stored credentials.
- **The replication user's password**, when the DRS task is created.
- **To run three or four commands yourself** on the source — the assistant never connects
  to your database. Each one comes complete, with an explanation of what it does.

### Where to find your source details

If you do not know the security group ID or the EIP:
[`references/console-navigation.md`](references/console-navigation.md) has the click path.
Or just ask the assistant — it can look them up with `hcloud` if you give it the ECS name
and region.

## Workflow

Twelve steps, in order. Detail in [`SKILL.md`](SKILL.md).

| Step | What happens | Approval |
|---:|---|---|
| 0 | Preflight — execution mode, MCPs, credentials, CLI metadata, regions | — |
| 1 | Source discovery and readiness — network, settings, privileges, locale | — |
| 2 | Source baseline — row counts, kept for validation | — |
| 3 | Provision the target with Terraform | **G1** |
| 4 | Align locale; ensure the target database does NOT exist | — |
| 5 | Create the DRS task | **G2** |
| 6 | Give the DRS instance network access | you apply `pg_hba.conf` |
| 7 | Connection test, object selection, pre-check | — |
| 8 | Start the task, monitor the full sync | **G3** |
| 9 | Validate — object level and row counts | — |
| 10 | Verify incremental replication | **G4** if a probe is needed |
| 11 | Cutover | **G5** |
| 12 | Confirm success, then clean up | **G6** |

## Design rules

**The source is read-only.** The assistant never connects to your database and never
modifies it. When the source needs a change, it prints the exact command and waits. This
keeps rollback trivial — the source is always exactly as you left it.

**Explain before asking.** Every request for action comes with what it is for and what
happens if it is skipped. You should never have to ask "wait, why am I doing this?".

**Discover, never assume.** Flavors, versions and CLI parameters vary by region and by CLI
version. The skill queries rather than hardcoding.

**Prove it with data.** An object-level comparison passes on a target with perfect
structure and zero rows. The skill takes a row-count baseline before migrating and compares
against it after. Both checks are required; neither can be skipped.

**Never wider than /32.** The source port is exposed during the migration. The rule is
always a single host, and it is removed in Step 12.

**Nothing is shut down.** Cutover redirects your application. Your ECS keeps running and
your original database stays intact — that is your way back.

## Files

```
postgresql-ecs-to-rds-drs/
├── SKILL.md                          The 12 steps, in order
├── README.md                         This file
├── references/
│   ├── client-communication.md       How to explain things — read before Step 0
│   ├── prerequisites.md              Full checklist
│   ├── console-navigation.md         Click-by-click console paths
│   ├── koocli-drs-metadata.md        If the CLI rejects PostgreSQL for DRS
│   ├── troubleshooting.md            Real errors, translations, and fixes
│   ├── rollback.md                   How to back out at each phase
│   └── reporting.md                  Final report template
└── assets/
    ├── sql/
    │   ├── 01_source_readiness_check.sql    Step 1 — read only
    │   ├── 02_source_grants.sql             Step 1 — grants only, if needed
    │   ├── 03_source_baseline.sql           Step 2 — read only
    │   ├── 04_target_validation_psql.sql    Step 9 — via psql
    │   └── 04_target_validation_das.sql     Step 9 — via the DAS editor
    └── terraform/target-rds/                Step 3
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        └── terraform.tfvars.example
```

## Known limitations

- **Public network only.** VPN and VPC peering are out of scope.
- **Three human touchpoints.** `postgresql.conf` changes if needed (plus a restart), the
  `pg_hba.conf` entries, and their removal at the end. Deliberate, not a gap.
- **KooCLI metadata.** Some CLI versions do not list PostgreSQL for `DRS CreateJob`. Step 0
  detects it; [`references/koocli-drs-metadata.md`](references/koocli-drs-metadata.md)
  resolves it.
- **Same major version only.** DRS does not migrate across PostgreSQL major versions.
- **CLOUDSSD storage only.** GPSSD2 and ESSD2 need a provisioned IOPS value and are rejected
  at plan time; provision from the console if one of those is required.
- **The target database is created by DRS**, not by this skill. If one already exists on the
  target, it is deleted first.
- **No automatic reverse sync.** After cutover, writes on the target are not replicated back
  to the source.
- **The DAS SQL editor mangles some quoting.** Validation queries for DAS are generated in a
  plain form; the `xpath` variant is for `psql` only.
