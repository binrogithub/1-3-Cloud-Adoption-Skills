# Console navigation

Exact paths for anything you ask someone to do in the Huawei Cloud console. Never say
"check it in DAS" — give the clicks.

Console UIs change. If a path does not match what they see, ask them what they *do* see
rather than insisting.

---

## Before anything: the region selector

**Top left of the console, next to "Console".** It shows the current region, for example
`AP-Singapore` or `LA-Mexico City2`.

Almost every "I don't see it" is the wrong region. Resources only appear in the region
they live in. Mention the region every single time you send someone to the console.

---

## Open the SQL editor on the target RDS (DAS)

Used in Step 9 and Step 10.

**The short way, from the instance:**

1. Region selector → **`<target_region>`**
2. **Service List → Databases → Relational Database Service**
3. Left menu: **Instances**
4. Click the **instance name** (`target-rds-postgresql`)
5. Top right of the instance page: **Log In**
6. A login dialog appears:
   - **Login Username:** `root`
   - **Password:** the RDS admin password
   - Tick **Remember Password**
   - **Test Connection**, then **OK**
7. The Data Admin Service opens with the database list
8. Find `<db_name>` → **SQL Statements Window**
9. Paste the query, press **Execute SQL (F8)**

**The long way**, if the Log In button is not visible: **Service List → Databases → Data
Admin Service → Development Tool → Add Login**, fill in DB Engine `PostgreSQL`, source
`RDS`, pick the instance, set **Database Name** to `<db_name>` (not `postgres`), username
`root`, the password, then **Log In** on the row that appears.

### Two things that trip people up

**Database Name defaults to `postgres`.** They must change it to the migrated database, or
the tables will not be there.

**The SQL editor mangles some quoting.** Queries using `xpath` / `query_to_xml` fail with
`syntax error at or near "("`. Always give a plain `UNION ALL` query for DAS — see Step
9.2.

---

## Check the DRS task

1. Region selector → **`<target_region>`**
2. **Service List → Databases → Data Replication Service**
3. Left menu: **Online Migration** (or **Data Synchronization**, depending on task type)
4. The task appears with its status

After cleanup the task should not be listed at all.

---

## Check the RDS instance

1. Region selector → **`<target_region>`**
2. **Service List → Databases → Relational Database Service → Instances**

Status must read **Available**. The instance page shows the private IP, port, VPC, subnet
and engine version.

After a `terraform destroy`, the list shows **0 Total instances**.

---

## Find or edit a security group rule

Used in Step 6 and Step 12.

1. Region selector → the region of the **server whose firewall you are changing** — the
   **source** region for the DRS access rule
2. **Service List → Networking → Virtual Private Cloud**
3. Left menu: **Access Control → Security Groups**
4. Click the security group name
5. **Inbound Rules** tab

To confirm the DRS rule: look for TCP 5432 with the DRS EIP and `/32`.
After cleanup, that rule should be gone.

---

## Find the ECS public IP and its security group

1. Region selector → **`<source_region>`**
2. **Service List → Compute → Elastic Cloud Server**
3. The list shows each server; the IP column shows the EIP and the private IP
4. Click the server name → **Security Groups** tab for the attached group and its ID

---

## Create or rotate access keys

Needed in Step 0.3 for Terraform.

1. **Top right avatar → My Credentials**
2. Left menu: **Access Keys**
3. **Create Access Key** — the Secret Key is shown **once**, in a downloaded CSV. It
   cannot be retrieved later.
4. To rotate: create the new one first, update the environment, then delete the old one

Worth saying out loud: if a key has been pasted into a chat, a screenshot or a shared
document, treat it as compromised and rotate it.

---

## Check billing for the migration

If they ask what this costs:

1. **Top right: Billing Center**
2. **Bills** for what has been charged, **Resource Packages** for what is running

Two things bill during a migration: the DRS replication instance (per hour while the task
runs, which is why Step 12 stops it) and the target RDS instance.
