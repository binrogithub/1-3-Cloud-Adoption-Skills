---
name: postgresql-ecs-to-rds-drs
description: Migrate a self-managed PostgreSQL database running on a Huawei Cloud ECS to a Huawei Cloud RDS for PostgreSQL instance in a different region, using DRS Full + Incremental synchronization over public EIP. Provisions the target with Terraform and drives DRS through the Huawei Cloud CLI. Use when a customer has PostgreSQL on an ECS and wants it on managed RDS, cross-region, with minimal downtime.
---

# PostgreSQL ECS to RDS — DRS cross-region migration

## What this skill does

Takes an **existing** self-managed PostgreSQL on an ECS and migrates it to a **new** RDS
for PostgreSQL instance in a different region, using DRS Full + Incremental replication
over the public network.

## What this skill does NOT do

- **It does not create the source.** The source is the customer's existing database.
- **It does not write to the source.** Every change is emitted as a command for a person
  to run.
- **It does not create the target database.** DRS creates it during the full sync — see
  Step 4.
- **It does not use VPN or VPC peering.** Public EIP with /32 restriction only.
- **It does not shut anything down.** Cutover redirects the application; the source keeps
  running.

## Required MCP servers

| MCP | Purpose |
|---|---|
| `hcloud` | All Huawei Cloud operations: discovery, DRS lifecycle, security group rules |
| `terraform` | Target VPC, subnet, security group and RDS instance |

Nothing else. No browser automation.

### Using `hcloud`

Structured read-only tools for discovery: `hcloud_list_rds_datastores`,
`hcloud_list_rds_flavors`, `hcloud_list_rds_storage_types`, `hcloud_list_rds_instances`,
`hcloud_list_vpcs`, `hcloud_list_subnets`, `hcloud_list_security_groups`,
`hcloud_list_security_group_rules`, `hcloud_list_public_ips`, `hcloud_list_servers`,
`hcloud_list_server_interfaces`, `hcloud_list_availability_zones`.

Everything else, including all of DRS, goes through `hcloud_cli`.

**Never hardcode CLI parameters from memory.** Discover them with `--help` and build the
call from what it returned. Parameters change between KooCLI versions.

Destructive operations (`Delete`, `Remove`, `Revoke`, `Detach`, `Disassociate`, `Cancel`,
`Force`) run as dry-run unless you pass `confirm=true`.

---

# How to talk to the person you are helping

**Assume they know they want to migrate, and nothing else.**

Read `references/client-communication.md` before Step 0. In short:

- **Explain why before asking what.** One or two sentences of context, always.
- **Give complete, runnable commands.** Never "add these lines to `pg_hba.conf`".
- **Say where each command runs** — their machine, inside the ECS over SSH, or the console.
- **For the console, give the clicks.** See `references/console-navigation.md`.
- **Never emit a command you know will fail.** Check it against what Step 1 told you.
- **Confirm success before proposing anything destructive.**

---

# Non-negotiable rules

1. **Source is read-only.** Never SSH into it, never modify it. Emit the command, stop,
   wait.
2. **Never widen the source firewall beyond /32.**
3. **Never invent a value.** Ask.
4. **Steps run in order.** The order matters more than it looks — several steps fail with
   misleading errors if the previous one has not actually completed. Do not skip, merge or
   reorder.
5. **Explicit approval before every write**, at the gate numbers below. Fixed numbers.
6. **Verify after every step.**

### Approval gates

| Gate | Operation | Step |
|---|---|---|
| G1 | `terraform apply` for the target | 3 |
| G2 | Creating the DRS task | 5 |
| G3 | Starting the DRS task | 8 |
| G4 | Writing the incremental probe row on the source | 10 |
| G5 | Cutover | 11 |
| G6 | Stopping the task, removing access, destroying the target | 12 |

---

# Workflow

---

## Step 0 — Preflight

**Explain first:** "Before touching anything I want to confirm the environment can finish
the job. Five checks, all read-only."

### 0.1 — Can I execute commands?

Some assistants run in a planning mode where commands are displayed but not executed. In
OpenCode that is **Plan** mode; the executing mode is **Build**.

If you cannot execute, say so and stop:

> I'm in a mode where I can only show commands, not run them. Switch to Build mode and
> tell me when you have — otherwise we'll reach Step 3 and nothing will really be created.

Re-state this before G1, G2, G3 and G6.

### 0.2 — Are both MCPs alive?

```
hcloud_cli(command="--help")
```

Terraform MCP: confirm it responds.

### 0.3 — Credentials — two separate sets

| Credential | Used by | Check |
|---|---|---|
| `hcloud` CLI profile | the `hcloud` MCP | `hcloud_cli(command="IAM KeytoneListProjects --cli-region=<target_region>")` |
| `HW_ACCESS_KEY` / `HW_SECRET_KEY` | Terraform | check the environment |

The CLI stores its credentials **encrypted**; Terraform cannot read them. If the
environment variables are not set, ask for the AK/SK **now**, not at Step 3.

> Terraform authenticates separately from the CLI and can't reuse its stored credentials.
> I need your Access Key and Secret Key. I'll export them in my own shell — they won't be
> written to any file. Console path: avatar (top right) → My Credentials → Access Keys.

Warn against pasting keys into a shared channel or screenshot, and suggest rotating them
afterwards.

**Capture the project ID of BOTH regions.** DRS commands need the target one; some
discovery calls need the source one.

### 0.4 — Does KooCLI support PostgreSQL for DRS?

```
hcloud_cli(command="DRS CreateJob --help")
```

Check `db_type` for `postgresql` and `engine_type` for `postgresql-to-postgresql`. If
either is missing, follow `references/koocli-drs-metadata.md` before continuing.

### 0.5 — Regions differ

If they are the same, this skill does not apply.

**Verify:** execution mode, both MCPs, both credential sets, both project IDs, DRS
metadata, regions differ.

---

## Step 1 — Source discovery and readiness

**Explain first:**

> Now I need to look at your existing setup — the server and the database. I won't change
> anything. DRS has requirements, and if they're not met the migration fails halfway
> through with an unhelpful error.
>
> Part of this I can look up myself. The database part I'll give you a script for, because
> I don't connect to your database.

### 1.1 — Discover the source ECS network (you do this)

**Do not skip this.** `DRS CreateJob` requires the source ECS's **VPC ID, subnet ID and
security group ID**, even though the connection runs over the public Internet. Without them
it fails with `The parameter source_endpoint.vpc is empty` (DRS.10020001).

The customer normally only knows the EIP. Find the rest yourself:

```
hcloud_list_public_ips(region=<source_region>)
```

Locate their EIP and read the attached server ID, then:

```
hcloud_list_servers(region=<source_region>)
hcloud_list_server_interfaces(region=<source_region>, server_id=<server_id>)
```

Record: server ID, private IP, VPC ID, subnet ID. Combine with the security group ID the
customer supplied.

If any of it cannot be resolved, ask — do not guess.

### 1.2 — Database readiness (they do this)

Give both commands, with real paths filled in.

**On their own machine**, to copy the script to the ECS:

```bash
scp <skill_path>/assets/sql/01_source_readiness_check.sql root@<source_eip>:/tmp/
```

Explain: this copies the file into `/tmp` on the server. Nothing is installed; it can be
deleted afterwards.

**Then, connecting to the ECS:**

```bash
ssh root@<source_eip>
```

**And once inside:**

```bash
sudo -u postgres psql -P pager=off -d <source_db> -f /tmp/01_source_readiness_check.sql
```

Explain why it runs on the ECS rather than remotely: the `postgres` superuser normally has
no remote-access entry in `pg_hba.conf`, so a remote `psql -U postgres` would be refused.

### 1.3 — Read the results

| Value | Requirement | If not met |
|---|---|---|
| `wal_level` | `logical` | Config change **plus a restart** — emit the lines, flag the maintenance window, stop |
| `max_replication_slots` | >= 1 | Same |
| `max_wal_senders` | >= 1 | Same |
| `password_encryption` | record it | Decides the `pg_hba.conf` method in Step 6 |
| `lc_monetary`, `datcollate`, `datctype` | record them | The target must match — Step 4 |
| `server_version` | record it | The target needs the same major version |
| Replication user with `REPLICATION` | required | |
| `SELECT` on all tables **and sequences** | required | Emit `02_source_grants.sql` |
| Database size | record it | The target disk must be larger |

On PostgreSQL 16+, `lc_collate` and `lc_ctype` are no longer server settings — they come
from `pg_database` in section 5 of the script, not section 4. Expected, not missing.

**Verify:** network details captured, every database requirement satisfied.

---

## Step 2 — Source baseline

**Explain first:**

> Before moving anything I want a count of what's in your database right now. Afterwards we
> compare the target against it.
>
> This matters more than it sounds: DRS can report a migration as consistent when the
> structure matches perfectly and no data actually arrived. The row counts are what prove
> the data moved.

```bash
scp <skill_path>/assets/sql/03_source_baseline.sql root@<source_eip>:/tmp/
```

```bash
sudo -u postgres psql -P pager=off -d <source_db> -f /tmp/03_source_baseline.sql
```

**Record the table names, not just the counts.** You need them in Step 7.2 to verify the
object collection, in Step 9 to build a DAS-compatible query, and in Step 10 to pick a
table for the probe.

**Verify:** table-by-table row count, total, timestamp.

---

## Step 3 — Provision the target

**Explain first:**

> Now I'll create the destination: a managed RDS for PostgreSQL in <target_region>, with
> its own network. Nothing on your side is touched. I'll show you the plan first.

### 3.1 — Ask how they want it configured

> Two questions before I build it:
>
> **Network** — new VPC and subnet, or an existing network in <target_region>? If existing,
> I need the VPC and subnet IDs.
>
> **Sizing** — I can pick sensible defaults based on your source (same PostgreSQL major
> version, comparable CPU and memory, disk larger than your current database), or you can
> choose. Which do you prefer?

If they want to choose, discover the real options and present a short list:

```
hcloud_list_rds_datastores(region=<target_region>, database_name="PostgreSQL")
hcloud_list_rds_flavors(region=<target_region>, database_name="PostgreSQL", version_name=<major>)
hcloud_list_rds_storage_types(region=<target_region>, database_name="PostgreSQL", version_name=<major>)
hcloud_list_availability_zones(region=<target_region>)
```

**On storage type:** prefer `CLOUDSSD`. `GPSSD2` and `ESSD2` require an explicit `iops`
value and fail with `parameter error: iops/null` (DBS.01280023) without it. The Terraform
supports it via `volume_iops`, but unless the customer specifically asked for that storage
class, `CLOUDSSD` is the safe default.

For an existing network:

```
hcloud_list_vpcs(region=<target_region>)
hcloud_list_subnets(region=<target_region>)
```

### 3.2 — Ask for the RDS password, with the rules up front

> I need an administrator password for the new database. Huawei RDS requires:
>
> - 8 to 32 characters
> - at least one uppercase letter
> - at least one lowercase letter
> - at least one digit
> - at least one special character from `~!@#$%^&*()-_=+|[{}];:,.<>?`
>
> For example `Migration@2026` fits. It's RDS's rule, not mine.
>
> Just tell me the password. I'll set it as an environment variable in my own shell; it
> won't be written into any configuration file.

**Validate it against those five rules yourself before using it.** Name the failing rule if
it does not pass.

Export it in **your own shell, the same one that runs Terraform**:

```bash
export TF_VAR_rds_password='<password>'
```

Same for `HW_ACCESS_KEY` and `HW_SECRET_KEY`. Environment variables do not cross shells.

### 3.3 — Plan

Copy `assets/terraform/target-rds/` to a working directory, write `terraform.tfvars`, then:

```
terraform init
terraform plan
```

Show the plan and summarise it in plain language.

### 3.4 — G1

Request explicit approval. Re-confirm executing mode.

```
terraform apply
```

The RDS instance takes about five minutes.

### 3.5 — Verify

```
hcloud_list_rds_instances(region=<target_region>)
```

Must be `ACTIVE`. Capture instance ID, private IP, subnet CIDR, security group ID, and the
provisioned engine version.

---

## Step 4 — Align the locale, and make sure the target database does NOT exist

**Explain first:**

> One small thing that prevents a failure later. A fresh RDS instance often comes up with
> different locale settings than your source, and DRS refuses to migrate when they differ.
> I'll change the target to match yours — never the other way round, since that would mean
> restarting your production database.

### 4.1 — Locale

```
hcloud_cli(command="RDS ShowInstanceConfiguration --instance_id=<id> --cli-region=<target_region>")
```

Compare against the Step 1 values. A fresh instance commonly reports `lc_monetary = "C"`.
If it differs:

```
hcloud_cli(command="RDS UpdateInstanceConfiguration --instance_id=<id> --cli-region=<target_region> --values.lc_monetary=<source_value>", confirm=true)
```

Run `--help` first. Check `restart_required` in the response; restart and wait for `ACTIVE`
if it is true.

### 4.2 — Do NOT create the target database

DRS creates it during the full sync, and needs to control its creation so that it matches
the source exactly.

If the database already exists on the target, the pre-check fails with
`SPECIFIED_DATABASE_ALREADY_EXISTED_IN_TARGET_ERROR`.

Check, and delete it if present:

```
hcloud_cli(command="RDS ListDatabases --instance_id=<id> --cli-region=<target_region>")
hcloud_cli(command="RDS DeleteDatabase --instance_id=<id> --cli-region=<target_region> --db_name=<db_name>", confirm=true)
```

**Verify:** locale matches the source, and the target database does **not** exist.

---

## Step 5 — Create the DRS task

**Explain first:**

> Now I create the replication task. Creating it doesn't move any data — that needs your
> approval separately, in a later step.

### 5.1 — Build the request

```
hcloud_cli(command="DRS CreateJob --help")
```

| Field | Value |
|---|---|
| Region | target region |
| `db_type` | `postgresql` |
| `engine_type` | `postgresql-to-postgresql` |
| `job_type` | `sync` |
| `task_type` | Full + Incremental |
| `job_direction` | `up` |
| `net_type` | `eip` |
| Source endpoint | `ecs_postgresql`, `<source_eip>:5432`, user `<repl_user>`, **plus the source VPC ID, subnet ID and security group ID from Step 1.1** |
| Target endpoint | `cloud_postgresql`, RDS instance `<instance_id>` |

The source VPC, subnet and security group are **required even for an EIP connection**.

### 5.2 — G2

Show the exact command with the password masked. Wait for approval.

Execute with `confirm=true`. Record the **job ID**.

### 5.3 — Wait for the replication instance

The task goes `CREATING` then `CONFIGURATION` while the replication instance is built. Poll
until it has an IP:

```
hcloud_cli(command="DRS ShowJobDetail --job_id=<job_id> --cli-region=<target_region> --project_id=<target_project_id> --type=detail")
```

**Verify:** task exists, replication instance has both a public and a private IP.

**Object selection does not happen here.** It is Step 7.2, and it cannot run until DRS can
reach the source — which is Step 6. Attempting it now fails with a permissions error that
has nothing to do with permissions.

---

## Step 6 — Give the DRS instance network access

**Explain first:**

> DRS runs on its own machine with its own IP address. Right now neither database will
> accept a connection from it. Three things have to allow it in: the firewall on your
> server, PostgreSQL's own access list on your server, and the firewall on the new
> database. I can do the two firewalls; the access list lives inside your server, so that
> one is yours.
>
> All of it is temporary. We remove it in the last step.

### 6.1 — Get the DRS instance IPs

From the Step 5.3 output: the **public IP** (used to reach the source) and the **private
IP** (used to reach the target).

### 6.2 — Source security group (you do this)

```
hcloud_cli(command="VPC CreateSecurityGroupRule --cli-region=<source_region> --security_group_rule.security_group_id=<source_sg_id> --security_group_rule.direction=ingress --security_group_rule.protocol=tcp --security_group_rule.port_range_min=5432 --security_group_rule.port_range_max=5432 --security_group_rule.remote_ip_prefix=<drs_public_ip>/32", confirm=true)
```

Confirm parameter names with `--help`. **Always `/32`.** Record the rule ID for Step 12.

### 6.3 — Target security group (you do this)

The DRS replication instance sits inside the target VPC and reaches the RDS privately — but
it still needs an ingress rule. The Terraform builds the security group with the default
rules removed, so without one the target connection test fails with *"Connection failed.
Check security group..."*.

The Terraform creates this rule from the subnet CIDR. Verify:

```
hcloud_list_security_group_rules(region=<target_region>, security_group_id=<target_sg_id>)
```

If missing, add it from the DRS private IP:

```
hcloud_cli(command="VPC CreateSecurityGroupRule --cli-region=<target_region> --security_group_rule.security_group_id=<target_sg_id> --security_group_rule.direction=ingress --security_group_rule.protocol=tcp --security_group_rule.port_range_min=5432 --security_group_rule.port_range_max=5432 --security_group_rule.remote_ip_prefix=<drs_private_ip>/32", confirm=true)
```

### 6.4 — `pg_hba.conf` on the source (they do this)

Use the `password_encryption` value from Step 1 — `scram-sha-256` on a default
PostgreSQL 14+. The wrong method gives *"The database user must allow remote connections"*.

Three entries, not two. The `all` entry matters because DRS reads metadata from databases
other than the one being migrated.

One runnable block, **inside the ECS over SSH**:

```bash
cat >> /etc/postgresql/<version>/main/pg_hba.conf <<'EOF'

# DRS replication access — temporary, remove after migration
host  all          <repl_user>  <drs_public_ip>/32  <method>
host  <db_name>    <repl_user>  <drs_public_ip>/32  <method>
host  replication  <repl_user>  <drs_public_ip>/32  <method>
EOF

sudo -u postgres psql -c "SELECT pg_reload_conf();"
tail -6 /etc/postgresql/<version>/main/pg_hba.conf
```

Explain each line: append, reload (no restart, nothing disconnects), show the result.

**Do not suggest a remote `psql -U postgres`** — that user has no remote entry.

### 6.5 — Wait

Ask them to confirm and paste the `tail` output. Do not continue on assumption.

**Verify:** both security group rules present, `pg_hba.conf` confirmed by the customer.

---

## Step 7 — Connection test, object selection, pre-check

**Explain first:**

> DRS now checks it can reach both databases, works out what there is to migrate, and runs
> a full readiness check. This is where problems surface, and much better here than
> mid-migration.

**The order inside this step is fixed.** Object collection needs a working source
connection; the pre-check needs the object selection. Out of order, each one fails with an
error that points somewhere else entirely.

### 7.1 — Connection test, both endpoints

```
hcloud_cli(command="DRS BatchValidateConnections --help")
```

Run it for source and target. Both must return SUCCESS before continuing.

The target may briefly report *"ip is empty"* or time out while the replication instance is
still initialising — retry. If it reports *"Connection failed"*, that is the target
security group; go back to Step 6.3.

### 7.2 — Collect the source objects

Only after the source connection test passes:

```
hcloud_cli(command="DRS CollectDbObjectsInfo --help")
```

A failure of *"Query failed. Check whether the migration account has sufficient
permissions"* almost always means DRS still cannot reach the source, **not** that
privileges are wrong. Re-check Step 6 before touching any grants.

Record the `query_id`. **Confirm the returned tables match the Step 2 baseline.** If they
do not, stop and investigate rather than proceeding with a mismatch.

### 7.3 — Set the migration objects

```
hcloud_cli(command="DRS BatchSetObjects --help")
```

Select the database being migrated, with `selected=true`.

A failure of *"Query error. Select another database object"* means the collection in 7.2
did not actually succeed. Re-run 7.2 first.

**Skipping this produces `SRC_HAS_DATABASE_WITH_NO_TABLE` at pre-check**, which reads as
"your database is empty" and is misleading.

### 7.4 — Pre-check

```
hcloud_cli(command="DRS BatchCheckJobs --help")
```

Then poll:

```
hcloud_cli(command="DRS ShowJobDetail --job_id=<job_id> --cli-region=<target_region> --project_id=<target_project_id> --type=precheck")
```

| Error | Cause | Fix |
|---|---|---|
| *Invoke test connection interface first* | pre-check ran before 7.1 | Run 7.1 |
| `SRC_HAS_DATABASE_WITH_NO_TABLE` | object selection empty | Step 7.3 |
| `SPECIFIED_DATABASE_ALREADY_EXISTED_IN_TARGET_ERROR` | the target database exists | Step 4.2 — delete it |
| The database user must allow remote connections | wrong `pg_hba.conf` method | Step 6.4 |
| `FULL_PG_SRC_DB_PRIVI_IS_NOT_ENOUGH_V2` | missing sequence grants | Step 1, script 02 |
| `DB_LC_MONETARY_INCONSISTENCY` | locale mismatch | Step 4.1 |

**Never create tables on the source to satisfy a pre-check.**

Translate failures into plain language — `references/troubleshooting.md`.

**Verify:** connection test PASS both sides, pre-check 100% with zero blocking items. List
the non-blocking alarms and explain them; they do not stop anything.

---

## Step 8 — Start the task and monitor the full sync

### 8.1 — G3

> This is the point where data starts moving. Your source isn't modified and stays
> available — DRS only reads from it.

Re-confirm executing mode. Wait for approval.

```
hcloud_cli(command="DRS BatchStartJobs --cli-region=<target_region> --project_id=<target_project_id> --jobs.1.job_id=<job_id>", confirm=true)
```

### 8.2 — Monitor

```
hcloud_cli(command="DRS ShowJobDetail --job_id=<job_id> --cli-region=<target_region> --project_id=<target_project_id> --type=progress")
```

Wait between polls. The task moves `STARTJOBING` → `FULL_TRANSFER_STARTED` →
`INCRE_TRANSFER_STARTED`.

**Record the actual timestamps of the full transfer start and end, and report the duration
as a number.** "A few seconds" is not a measurement; the report needs the real figure.

**Verify:** structure, data and index all at 100%, task at `INCRE_TRANSFER_STARTED`,
incremental delay recorded.

---

## Step 9 — Validate the migration

**Explain first:**

> Two checks. The first compares structure. The second counts rows. Both are needed: the
> structure check passes on a target that's perfectly shaped and completely empty, so only
> the row counts prove your data arrived.

### 9.1 — Object level

```
hcloud_cli(command="DRS CreateObjectLevelCompareJob --cli-region=<target_region> --project_id=<target_project_id> --job_id=<job_id>", confirm=true)
```

Poll for the result. Report tables, indexes, constraints and extensions on both sides.

### 9.2 — Row counts

**Mandatory. There is no skip option.**

Build an explicit query from the Step 2 table list. Do **not** give them the
`xpath`/`query_to_xml` version — the DAS editor mangles its quoting and it fails with
`syntax error at or near "("`. Generate a plain `UNION ALL`:

```sql
SELECT '<table_1>' AS tabla, count(*) AS filas FROM <table_1>
UNION ALL SELECT '<table_2>', count(*) FROM <table_2>;
```

Give the console path click by click — `references/console-navigation.md`.

Compare table by table against the baseline. If the source is live, the target may be equal
or slightly ahead; say so rather than reporting a mismatch.

**Verify:** object comparison consistent **and** every row count matches.

---

## Step 10 — Verify incremental replication

**Explain first:**

> The task reports a delay under a second, but that only means the channel is open. It
> doesn't prove a change travels. Let's make one and watch it arrive.

### Option A — the source is live

Count rows on both sides, wait a minute, count again. Confirm the target follows. Nothing
is written. Prefer this whenever the source has traffic.

### Option B — the source is idle

**G4 — this writes one row to the source.**

**Pick a table from the Step 2 baseline** — one that already existed when the objects were
selected in Step 7.3. Do **not** create a new table: anything created after the selection
is outside the task's scope, will not replicate, and looks like a failure when nothing is
wrong.

Read the structure first so the insert is valid:

```bash
sudo -u postgres psql -d <source_db> -c "\d <table>"
```

Then an insert with a clearly identifiable value:

```bash
sudo -u postgres psql -d <source_db> -c "INSERT INTO <table> (<columns>) VALUES (<values>);"
```

Wait about 30 seconds, then have them count that table on the target via DAS. One higher
than the baseline.

Offer to remove the test row afterwards — the delete replicates too.

**Verify:** the change reached the target with no manual copying.

---

## Step 11 — Cutover

### 11.1 — Is there anything to cut over?

> Is there an application currently connected to the source that should now point at the
> new database? If this was a test migration, there's nothing to do here.

If not, say clearly that Step 11 does not apply, and record G5 as skipped rather than
omitting it silently.

### 11.2 — What cutover is

> Cutover means changing your application's connection settings to the new database.
> **Nothing is shut down or deleted.** Your ECS keeps running and your original database
> stays exactly as it is — that's deliberate, it's your way back.

### 11.3 — G5

1. Confirm the incremental delay is low and stable.
2. They stop writes to the source.
3. Wait for the delay to reach zero.
4. Give them the connection details, ready to copy:

   ```
   Host:     <rds_private_ip>
   Port:     5432
   Database: <db_name>
   User:     root
   ```

   The private IP is reachable from inside the target VPC. If the application runs
   elsewhere, flag that they need a public IP on the RDS or private connectivity.
5. They verify the application works.

**Warn clearly:** once the application writes to the new database, those writes are not
copied back. Rolling back after that means losing them or moving them by hand.

---

## Step 12 — Confirm success, then clean up

### 12.1 — Report success first

**Before proposing anything destructive.**

> The migration is complete and verified. Your database is now on managed RDS in
> <target_region>: <n> tables and <n> rows, matching your source exactly. The full copy
> took <duration> and replication was running with a delay of <delay>.

Then the full report — `references/reporting.md`.

### 12.2 — Ask what to keep

> Two separate things.
>
> **The DRS task** should be stopped either way — it bills while it runs and isn't needed
> after cutover.
>
> **The target RDS instance** is your call. Keep it if the migration is real, destroy it if
> this was a test.

### 12.3 — G6

```
hcloud_cli(command="DRS BatchStopJobs --cli-region=<target_region> --project_id=<target_project_id> --jobs.1.job_id=<job_id> --pause_mode=all", confirm=true)
hcloud_cli(command="DRS BatchDeleteJobs --cli-region=<target_region> --project_id=<target_project_id> --jobs.1.job_id=<job_id> --delete_type=force_terminate", confirm=true)
```

Then confirm it is gone:

```
hcloud_cli(command="DRS ShowJobDetail --job_id=<job_id> --cli-region=<target_region> --project_id=<target_project_id> --type=detail")
```

If the task still exists, run `--delete_type=delete` as well. If `force_terminate` already
removed it, that call returns *"Task already terminated"* — harmless, not a failure. Do not
report it as an error.

Remove the source security group rule:

```
hcloud_cli(command="VPC DeleteSecurityGroupRule --cli-region=<source_region> --security_group_rule_id=<rule_id>", confirm=true)
```

### 12.4 — The `pg_hba.conf` lines (they do this)

> One last thing on your server. Those three lines tell PostgreSQL to accept connections
> from the DRS machine — and that machine no longer exists. Its IP goes back into Huawei
> Cloud's pool and will eventually belong to someone else. Leaving the entry means whoever
> gets it has one less obstacle in front of your database.

```bash
sed -i '/<drs_ip_escaped>/d' /etc/postgresql/<version>/main/pg_hba.conf
sudo -u postgres psql -c "SELECT pg_reload_conf();"
tail -5 /etc/postgresql/<version>/main/pg_hba.conf
```

Explain each line. If a probe row was inserted in Step 10, offer the `DELETE` too.

### 12.5 — Destroy the target, only if they asked

```
terraform destroy
```

Subnets and security groups can each take several minutes.

**Verify:** task gone, source rule removed, `hcloud_list_rds_instances` returns zero, and
their confirmation on the `pg_hba.conf` lines.

---

## References

| File | Read it |
|---|---|
| `references/client-communication.md` | Before Step 0 |
| `references/prerequisites.md` | Before Step 0 |
| `references/console-navigation.md` | Whenever you send someone to the console |
| `references/koocli-drs-metadata.md` | Step 0.4, if `--help` lacks PostgreSQL |
| `references/troubleshooting.md` | Step 7, on any failure |
| `references/rollback.md` | Anything fails after Step 8 |
| `references/reporting.md` | Step 12.1 |

## Assets

| File | Step |
|---|---|
| `assets/sql/01_source_readiness_check.sql` | 1 |
| `assets/sql/02_source_grants.sql` | 1, if privileges are missing |
| `assets/sql/03_source_baseline.sql` | 2 |
| `assets/sql/04_target_validation_psql.sql` | 9, via psql |
| `assets/sql/04_target_validation_das.sql` | 9, template for the DAS editor |
| `assets/terraform/target-rds/` | 3 |
