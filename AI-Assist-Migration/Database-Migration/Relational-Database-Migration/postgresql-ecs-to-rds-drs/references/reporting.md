# Reporting

Produced in Step 12.1, **before** proposing any cleanup.

## Order matters

Confirm success first, in the customer's terms. Then the detail. Then cleanup.

Never go from a technical step straight to "shall I destroy this?" — it reads as though
something went wrong, and it gives them no basis to decide.

## Open with plain language

> The migration is complete and verified. Your database is now running on managed RDS in
> LA-Mexico City2. All 5 tables and 29 rows are there, matching your original exactly. The
> initial copy took about 18 seconds, and ongoing replication was keeping the two in sync
> with less than a second of delay.

No identifiers, no status codes, no jargon. Detail comes after.

## Then the record

### Endpoints

| | Source | Target |
|---|---|---|
| Region | | |
| Type | ECS self-managed | RDS for PostgreSQL |
| Endpoint | | |
| Database | | |
| PostgreSQL version | | |

### DRS task

| Field | Value |
|---|---|
| Job ID | |
| Engine | `postgresql-to-postgresql` |
| Mode | Full + Incremental |
| Full sync duration | Real figure, from the Step 8 timestamps. "A few seconds" is not a measurement |
| Incremental delay | |
| Status | |

### Baseline vs target

Table by table, with the match column. This is the evidence the migration worked — not the
object comparison.

| Table | Source rows | Target rows | Match |
|---|---|---|---|

Plus the totals row.

Then object counts: tables, indexes, constraints, sequences, extensions.

### Incremental verification

Which option was used (A or B), what was changed, and what arrived. If the probe table did
not replicate, explain why — created after the object selection, therefore out of scope —
so nobody later reads it as a failure.

### Pre-check issues

Every failure encountered and how it was resolved. Even the ones fixed in seconds: they
are what the next person needs.

| Issue | Resolution |
|---|---|

### Approval gates

| Gate | Operation | Approved by |
|---|---|---|

Only the gates that actually occurred. If Step 11 was skipped, say so and say why, rather
than omitting G5 silently.

### Cleanup state

| Item | Status |
|---|---|
| DRS task | |
| Source security group rule | |
| Source `pg_hba.conf` entries | |
| Target RDS instance | |
| Target VPC / subnet / security group | |

Anything left for the customer to do goes here, spelled out. The `pg_hba.conf` lines are
the usual one — the AI cannot remove them, and a stale entry leaves the database reachable
by whoever inherits that EIP.

## Things worth flagging

- **A KooCLI metadata patch was needed** — the run is not reproducible without it
- **The DRS task was created from the console** because `CreateJob` rejected PostgreSQL
- **The source needed a restart** to change `wal_level`
- **Extensions on the source that RDS does not support**
- **Tables without primary keys**
- **Credentials shared during the session** — recommend rotating them

## What not to put in

- Passwords, access keys, or secret keys, in any form
- Contents of `terraform.tfstate`
- Customer data, or row values beyond counts
