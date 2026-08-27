# Prerequisites

Checked in Step 0. Items marked **blocker** stop the migration outright.

## Assistant environment

| Requirement | Check | Blocker |
|---|---|---|
| Executing mode, not planning mode | Build in OpenCode, or equivalent | Yes |
| `hcloud` MCP responding | `hcloud_cli(command="--help")` | Yes |
| Terraform MCP responding | — | Yes |
| Terraform >= 1.3 | `terraform version` | Yes |
| KooCLI DRS metadata supports PostgreSQL | `hcloud_cli(command="DRS CreateJob --help")` | Yes — see `koocli-drs-metadata.md` |

## Credentials — two separate sets

These are **not** interchangeable, and the second one is the usual surprise.

| Credential | Used by | Notes |
|---|---|---|
| `hcloud` CLI profile | the `hcloud` MCP | `hcloud configure init` if missing |
| `HW_ACCESS_KEY` / `HW_SECRET_KEY` | Terraform | The CLI stores its credentials **encrypted**; Terraform cannot read them |

Ask for the AK/SK at Step 0, not at Step 3 in the middle of an apply. Export them in the
same shell that will run Terraform — environment variables do not cross shells.

Console path to create or rotate keys: **avatar (top right) → My Credentials → Access
Keys**. The Secret Key is shown once, in a downloaded CSV.

## IAM permissions

- DRS: full access in the target region
- RDS: create and manage instances in the target region
- VPC: create VPC, subnet, security group, and **modify the source security group**
- IAM: list projects

## Source — the customer's existing database

Not created by this skill. It already exists.

| Requirement | Value | Blocker |
|---|---|---|
| PostgreSQL reachable from the Internet | EIP + port 5432 | Yes |
| `wal_level` | `logical` | Yes — **needs a restart** to change |
| `max_replication_slots` | >= 1 | Yes — needs a restart |
| `max_wal_senders` | >= 1 | Yes — needs a restart |
| `listen_addresses` | allows remote connections | Yes |
| Replication user with `REPLICATION` | e.g. `drs_replicator` | Yes |
| `SELECT` on all tables | | Yes |
| **`SELECT, USAGE` on all sequences** | | Yes — most commonly missed |
| `password_encryption` value known | `scram-sha-256` or `md5` | Yes — decides the `pg_hba.conf` method |
| Locale known | `lc_monetary`, `datcollate`, `datctype` | Yes — the target must match |
| Source security group ID known | | Yes |
| Source VPC ID and subnet ID | discovered by the skill in Step 1.1 | Yes — `CreateJob` needs them even over EIP |
| Database size known | | Yes — the target disk must be larger |
| Tables have primary keys | | No — but tables without one replicate unreliably during the incremental phase |

`assets/sql/01_source_readiness_check.sql` checks all of it in one run.

### Two things a human must do

The AI never touches the source. These need a person:

1. Any `postgresql.conf` change (`wal_level`, slots, senders) — **plus a restart**.
   Flag the restart early: it needs a maintenance window.
2. The `pg_hba.conf` entries for the DRS instance — plus a reload (no restart).

The skill emits the exact commands. It does not run them.

## Target

Does not need to exist — Step 3 creates it.

| Requirement | Notes |
|---|---|
| Target region differs from the source | Cross-region by definition |
| Quota for one RDS instance in the target region | |
| A flavor that exists in that region | Discover it, never assume |
| A storage class that needs no provisioned IOPS | CLOUDSSD. GPSSD2 and ESSD2 are rejected at plan time |
| Same PostgreSQL major version as the source | DRS does not migrate across major versions |
| Source extensions available on RDS | Check the Step 1 list against RDS support |
| An existing VPC and subnet, if reusing one | Ask; do not assume a new network is wanted |

## Network model

Public Internet only.

- The DRS replication instance is created in the **target** region, inside the target VPC
- It reaches the **target** privately over the VPC
- It reaches the **source** over the public Internet via the source EIP
- So only the **source** security group needs a new rule, always `/32`

VPN and VPC peering are out of scope.

### Security note worth saying out loud

During the migration the source PostgreSQL port is reachable from the Internet. That is
inherent to this architecture, and worth stating plainly rather than glossing over.

Mitigated by: a `/32` prefix, `pg_hba.conf` entries scoped to the same `/32` and a single
user, and removal of both in Step 12.

Do not skip Step 12. A stale rule leaves the database exposed to whoever inherits that EIP
next.

## Information to collect

Ask for anything missing rather than assuming:

- Source: region, EIP, port, database name, PostgreSQL version, security group ID
  (the VPC and subnet IDs are discovered automatically in Step 1.1)
- Source replication user and password
- Target: region, new network or existing (with IDs), sizing preference
- Target RDS admin password — with the format rules explained before asking
- DRS task name
- Whether an application will be cut over, or this is a test
- Who approves the write gates
