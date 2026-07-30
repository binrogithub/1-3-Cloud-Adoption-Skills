# Demo Script - PostgreSQL ECS to RDS Migration via DRS

## Presentation Flow (15-20 minutes)

### 1. Introduction (2 min)

**Say:** "Today I'll demonstrate an inter-region PostgreSQL migration from a self-managed database on Huawei Cloud ECS to Huawei Cloud RDS for PostgreSQL, using the Data Replication Service with Full + Incremental mode."

**Show:** `docs/architecture.md` — the architecture diagram

**Key points:**
- Source: Self-managed PostgreSQL 16 on ECS (not RDS)
- Target: RDS for PostgreSQL 16 in Santiago (la-south-2)
- Technology: DRS Full + Incremental
- Current phase: Internet-based connectivity (experimental)
- Presentation version: VPN/private network

### 2. Show Source Data (3 min)

**Action:** SSH to source ECS

```bash
ssh ubuntu@<ECS_EIP>
psql -d demomigration -f sql/03_source_validation.sql
```

**Say:** "Here's our source PostgreSQL database. We have 5 customers, 5 products, 5 orders, and 9 order items. The total revenue is 3,106.41. The migration audit shows INITIAL_LOAD status is READY."

**Point out:**
- Row counts
- Revenue total
- Migration audit row

### 3. Show DRS Task (3 min)

**Action:** Open DRS console in browser

**Say:** "DRS is configured for Full + Incremental migration. The source is our self-managed PostgreSQL on ECS, and the target is RDS in Santiago. We're using public network connectivity for this experimental lab — the presentation version will use VPN."

**Point out:**
- Task name and status
- Migration mode: Full + Incremental
- Source and target details
- Network type: Public network
- Current status (incremental sync running)

### 4. Show Target Data - Full Sync Validation (3 min)

**Action:** Open DAS for target RDS

```sql
-- From sql/04_target_validation_das.sql
```

**Say:** "After DRS full sync completed, all data was replicated to the target RDS. Let me verify the row counts and totals match the source exactly."

**Point out:**
- Row counts match source: 5 customers, 5 products, 5 orders, 9 items
- Revenue total matches: 3,106.41
- Audit row matches: INITIAL_LOAD / READY

### 5. Insert Incremental Data on Source (2 min)

**Action:** On source ECS

```bash
psql -d demomigration -f sql/05_incremental_test_source.sql
```

**Say:** "Now I'll insert a new customer and order on the source database. DRS incremental sync should replicate these changes to the target in near real-time."

**Point out:**
- New customer C006 (Frank Okafor)
- New order ORD006
- New audit row INCREMENTAL_TEST

### 6. Show Replicated Data on Target (3 min)

**Action:** Wait 10-30 seconds, then in DAS

```sql
-- From sql/06_incremental_validation_target_das.sql
```

**Say:** "The incremental data has been replicated! Customer C006, order ORD006, and the INCREMENTAL_TEST audit row are all present on the target RDS. The total revenue is now 3,406.40."

**Point out:**
- C006 exists on target
- ORD006 exists on target
- INCREMENTAL_TEST audit exists
- Revenue updated to 3,406.40

### 7. Explain Connectivity and Security (2 min)

**Say:** "I want to be transparent about the networking. This experimental lab uses public Internet connectivity between the source ECS and DRS. The PostgreSQL port is only open to the DRS source CIDR — not to 0.0.0.0/0. For the actual presentation, we will replace this with inter-region VPN connectivity, eliminating all public PostgreSQL exposure."

**Show:** `docs/security-and-cleanup.md` — public exposure inventory

**Key points:**
- PostgreSQL access restricted to DRS CIDR only
- No 0.0.0.0/0 access
- VPN migration plan is documented
- All public exposure will be removed

### 8. Summary and Q&A (2 min)

**Say:** "To summarize: we demonstrated a successful inter-region PostgreSQL migration using DRS Full + Incremental mode. The source is a self-managed PostgreSQL on ECS, the target is RDS in Santiago, and all data — including real-time incremental changes — replicated correctly. The next step is to harden the connectivity with VPN for the production presentation."

## Backup Slides / Talking Points

- **Why DRS and not pg_dump/pg_restore?** DRS provides CDC-based incremental sync with minimal downtime
- **Why Full + Incremental?** Full sync captures the baseline; incremental keeps them in sync during cutover window
- **Why self-managed source?** Many enterprises run PostgreSQL on VMs; this demonstrates the migration path to managed RDS
- **wal_level = logical:** Required for DRS to decode WAL streams for CDC
- **DRS replication user:** Minimal privileges — CONNECT, USAGE, SELECT on all tables
- **Inter-region:** Source and target are in different Huawei Cloud regions, demonstrating cross-region capability
