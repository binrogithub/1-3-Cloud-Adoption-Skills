# Troubleshooting

Every entry comes from a real failure observed running this scenario end to end.

Each one includes how to explain it to the person you are helping. Error codes mean
nothing to them — translate first, then fix.

---

## Connection test

### "The database user must allow remote connections"

**Say:** "PostgreSQL is refusing the connection. The access entry we added expects the
password in a different format than your server actually stores. One-line fix."

**Cause.** The `pg_hba.conf` entry uses the wrong authentication method. Usually `md5` was
written but the source runs PostgreSQL 14+, where `password_encryption` defaults to
`scram-sha-256`. The stored hash is SCRAM, so MD5 authentication cannot succeed.

**Fix.** Use the value recorded in Step 1. Rewrite the three entries with the correct
method and reload:

```
host  all          <repl_user>  <drs_eip>/32  scram-sha-256
host  <db_name>    <repl_user>  <drs_eip>/32  scram-sha-256
host  replication  <repl_user>  <drs_eip>/32  scram-sha-256
```

```sql
SELECT pg_reload_conf();
```

**Never switch the source to `md5` to make DRS happy.** That weakens the customer's
authentication permanently to work around a one-line fix.

**One extra case:** if the entries are right but the user's password hash predates a change
to `password_encryption`, the hash is still MD5. Resetting the password rehashes it:

```sql
ALTER USER <repl_user> WITH PASSWORD '<same or new password>';
```

---

### Connection test times out

**Say:** "DRS can't reach your server at all — this is a network problem rather than a
password one. Let me check the firewall."

Work outward from the database:

1. Security group rule on the **source**: TCP 5432 from `<drs_eip>/32`?
   ```
   hcloud_list_security_group_rules(region=<source_region>, security_group_id=<source_sg_id>)
   ```
2. Is the source EIP still attached to the ECS?
3. `SHOW listen_addresses;` — does it allow remote connections?
4. Host firewall on the ECS (`ufw`, `iptables`) blocking 5432?

A timeout is network. An authentication error means the network is already fine.

---

### The DRS EIP changed

The replication instance EIP is assigned at task creation and changes if the task is
recreated. If the test passed before and fails now, re-read the EIP from `ShowJobDetail`
and compare against the security group and `pg_hba.conf`. Stale entries are the usual
cause of "it worked yesterday".

---

## Pre-check

### `SRC_HAS_DATABASE_WITH_NO_TABLE`

**Say:** "DRS is reporting it can't see any tables to migrate. Your database is fine — we
counted them in Step 2. The task just doesn't have them selected yet. I'll fix the task."

**Cause.** The task has no migration object selection. It reads as "the database is empty",
which is misleading.

**Fix.** Step 5.3 — `DRS CollectDbObjectsInfo`, then `DRS BatchSetObjects` for the database
being migrated. Re-run the pre-check.

**Never create tables on the source to satisfy this check.** If Step 2 showed tables and
DRS says there are none, the discrepancy is in the task configuration. Writing objects into
a customer's database to clear a pre-check changes the thing being migrated, contaminates
the row-count baseline, and on a production system is simply unacceptable.

This is the reason Step 2 exists: without a baseline you have nothing to contradict DRS
with.

---

### `FULL_PG_SRC_DB_PRIVI_IS_NOT_ENOUGH_V2`

**Say:** "The replication user can read your tables but not the sequences behind
auto-numbered columns. Two grants fix it."

**Fix.** `assets/sql/02_source_grants.sql`. The lines that matter:

```sql
GRANT SELECT, USAGE ON ALL SEQUENCES IN SCHEMA public TO <repl_user>;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, USAGE ON SEQUENCES TO <repl_user>;
```

Repeat for every schema if the database uses more than `public`.

---

### `DB_LC_MONETARY_INCONSISTENCY`

**Say:** "The new database formats currency differently from yours. DRS won't migrate
across that difference. I'll change the new one to match — never yours, since that would
mean restarting your production database."

**Cause.** A fresh RDS instance often comes up with `lc_monetary = C` while a self-managed
Ubuntu install uses `en_US.UTF-8`.

**Fix — on the target:**

```
hcloud_cli(command="RDS ShowInstanceConfiguration --instance_id=<id> --cli-region=<target_region>")
hcloud_cli(command="RDS UpdateInstanceConfiguration --instance_id=<id> --cli-region=<target_region> --values.lc_monetary=<source_value>", confirm=true)
```

Confirm the syntax with `--help` first. Restart and wait for `ACTIVE` if required.

Step 4 does this proactively, so it should not appear at all.

---

### Non-blocking alarms

The pre-check separates blocking failures from warnings. Warnings do not stop anything.

**Say:** "It flagged a few things but none of them block the migration — for example your
PostgreSQL doesn't support failover replication slots, which only matters if the source
server fails mid-migration."

List them, explain them, move on. Do not "fix" them by changing the source.

---

## Task execution

### Stuck in `STARTJOBING`

Normal for a minute or two. Poll with a wait between calls. If it does not advance after
several minutes, read `--type=detail` for the error.

---

### Target row counts lower than the baseline

1. **The source is live and still receiving writes.** Expected — the incremental phase
   catches up. Compare again once the delay stabilises.
2. **The object selection excluded tables.** Compare the task's selection against the
   Step 2 table list.

If the target has *more* rows than the source and the source is idle, something wrote to
the target directly. Investigate before cutover.

---

### Object comparison shows more tables than the baseline

Compare against the Step 2 baseline, not against assumption. Extra tables on both sides
mean something created them on the source after the baseline was taken. Find out what
before trusting the comparison.

An object comparison only proves both sides match each other. It does not prove either
side matches what you started with.

---

### The incremental probe table never appears on the target

**This is expected, not a failure.**

A table created *after* the object selection in Step 5.3 is outside the task's scope, so
neither its DDL nor its rows replicate.

**Say:** "The test table didn't replicate, but that's not a problem with replication — the
table was created after we told DRS what to migrate, so it's outside the task's scope.
Let me test with a table that is in scope."

**Fix.** Use Step 10 Option B correctly: `INSERT` into a table that already existed at
Step 2, and watch its count go up on the target. Never `CREATE TABLE` for the probe.

---

### Incremental delay is low but changes do not appear

A low delay means the channel is open, not that changes are flowing. Verify with an actual
change on a table inside the object selection.

---

## Task creation and object selection

### `The parameter source_endpoint.vpc is empty` (DRS.10020001)

**Say:** "DRS needs to know which virtual network your server lives in, not just its public
address. Let me look that up."

**Cause.** `CreateJob` requires the source ECS's VPC ID, subnet ID and security group ID
even when the connection runs over the public Internet. The customer normally only supplies
the EIP.

**Fix.** Step 1.1 — discover them yourself:

```
hcloud_list_public_ips(region=<source_region>)      # EIP -> server id
hcloud_list_servers(region=<source_region>)
hcloud_list_server_interfaces(region=<source_region>, server_id=<server_id>)
```

---

### `CollectDbObjectsInfo` fails with a permissions message

The message reads *"Query failed. Check whether the migration account has sufficient
permissions"*, and it is misleading. Almost always the DRS instance simply cannot reach the
source yet.

**Fix.** Complete Step 6 first — both the source security group rule and the
`pg_hba.conf` entries — then retry. Do not start changing grants on the basis of this
message.

This is why object selection is Step 7.2 and not part of task creation.

---

### `BatchSetObjects` fails with "Query error. Select another database object"

The collection in 7.2 did not actually succeed, even if it appeared to. Re-run 7.2, confirm
it returned a `query_id` and a table list matching the Step 2 baseline, then retry.

---

### `SPECIFIED_DATABASE_ALREADY_EXISTED_IN_TARGET_ERROR`

**Say:** "DRS wants to create the database itself so it matches yours exactly, and it's
finding one already there. I'll remove it — no data is lost, it's empty."

**Cause.** The target database was created ahead of the migration. DRS creates it during
the full sync and will not migrate into a pre-existing one.

**Fix.** Step 4.2:

```
hcloud_cli(command="RDS DeleteDatabase --instance_id=<id> --cli-region=<target_region> --db_name=<db_name>", confirm=true)
```

Then re-run the pre-check. **Do not create the target database at any point.**

---

### Target connection test: "Connection failed. Check security group"

**Cause.** The target security group has no ingress rule on 5432. The Terraform builds the
group with `delete_default_rules = true`, which removes the implicit intra-group allow, so
the rule has to be explicit.

**Fix.** The Terraform now creates it from the subnet CIDR. Verify with
`hcloud_list_security_group_rules`; if missing, add it from the DRS instance private IP —
Step 6.3.

---

### Target connection test: "ip is empty" or a timeout

The replication instance is still initialising and has no IP yet. Wait and retry. This is
not an error condition on the first attempt or two.

---

## Terraform

### `terraform apply` fails on the password

RDS requires 8-32 characters with an uppercase letter, a lowercase letter, a digit, and a
special character from `~!@#$%^&*()-_=+|[{}];:,.<>?`.

The `rds_password` variable validates this before the API is called, so the failure should
surface as a Terraform validation error rather than an API error. Ask for a new password
naming the rule that failed.

---

### Terraform cannot authenticate

The `hcloud` CLI stores credentials encrypted and **Terraform cannot read them**. It needs
`HW_ACCESS_KEY` and `HW_SECRET_KEY` in the environment.

Export them in the same shell that runs Terraform — environment variables do not cross
shells, so exporting in another terminal has no effect.

Step 0.3 checks this so it does not surface mid-apply.

---

### `parameter error: iops/null` (DBS.01280023)

**Cause.** `volume_type` was set to `GPSSD2` or `ESSD2`. Those storage classes require a
provisioned `iops` value.

**Fix.** Use `CLOUDSSD`. The `volume_type` variable now rejects GPSSD2 and ESSD2 at plan
time with a clear message, so this should not reach the API. If the customer specifically
needs one of those classes, provision the instance from the console instead.

---

### Flavor not found

Flavors vary by region. Discover with
`hcloud_list_rds_flavors(region=..., database_name="PostgreSQL", version_name=...)` and
use one that the call actually returned.

---

### `terraform destroy` fails on the security group

The DRS replication instance may still hold an interface in the VPC. Delete the DRS task
completely first, confirm it is gone from `ShowJobDetail`, then destroy.

---

## Cleanup

### The task will not delete

Order matters, and all three need `confirm=true`:

```
DRS BatchStopJobs   --pause_mode=all
DRS BatchDeleteJobs --delete_type=force_terminate
DRS BatchDeleteJobs --delete_type=delete
```

---

## Assistant execution

### Commands appear to run but nothing is created

The assistant is in a planning mode that displays commands without executing them — Plan
mode in OpenCode, or the equivalent elsewhere.

The symptom is a `terraform apply` that "succeeds" while
`hcloud_list_rds_instances` returns nothing.

Step 0.1 checks for this. Re-confirm before G1, G2, G3 and G6.
