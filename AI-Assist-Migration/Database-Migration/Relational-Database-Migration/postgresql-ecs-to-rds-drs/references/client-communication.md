# Talking to the person you are helping

Read this before Step 0.

## The assumption to start from

**They know they want to migrate. Assume nothing else.**

They may not know what SSH is, where `pg_hba.conf` lives, what a security group does, why
a locale setting matters, or what "cutover" means. They may never have opened the Huawei
Cloud console beyond the page they landed on.

That is not a problem to work around. It is the normal case, and this skill exists to
serve it. Treating them as a database administrator is the fastest way to make it useless
— they get stuck, ask someone else, and the automation saved nobody any time.

A person who has to interrupt and ask "wait, what is this and why?" has been failed by the
instruction, not the other way round.

---

## Six rules

### 1. Explain why before asking what

Every request gets one or two sentences of context first: what this is for, and what
happens if it is skipped.

> **No:** "Run 01_source_readiness_check.sql and paste the output."
>
> **Yes:** "DRS needs a few specific settings on your database, and if they're missing the
> migration fails halfway through with an unhelpful error. This script checks for them.
> It only reads — it changes nothing. Run it and paste me what comes out."

### 2. Complete commands, never fragments

A command they can paste and run. Not a description of what to do.

> **No:** "Add the entries to `pg_hba.conf` and reload."
>
> **Yes:**
> ```bash
> cat >> /etc/postgresql/16/main/pg_hba.conf <<'EOF'
>
> # DRS replication access — temporary
> host  all  drs_replicator  101.44.24.109/32  scram-sha-256
> EOF
>
> sudo -u postgres psql -c "SELECT pg_reload_conf();"
> ```
> "The first command appends the line, the second makes PostgreSQL reread the file. No
> restart, nothing disconnects."

Fill in the real values. Never leave `<placeholders>` in something you are asking someone
to run — they will paste it verbatim.

### 3. Say where it runs

Three different places, and the same command fails confusingly in the wrong one:

- **Their own machine** — `scp`, `terraform`, connecting over SSH
- **Inside the source ECS**, over SSH — anything touching PostgreSQL config or data
- **The Huawei Cloud console** — DAS queries, visual verification

Label every command with one of them.

### 4. For the console, give the clicks

> **No:** "Check it in DAS."
>
> **Yes:** "In the console, set the region selector at the top left to LA-Mexico City2,
> then go to **Service List → Databases → Relational Database Service → Instances**. Click
> your instance name, then **Log In** at the top right."

Paths are in `references/console-navigation.md`.

### 5. Never emit a command you know will fail

You learned things in Step 1. Use them.

If `pg_hba.conf` only has a remote entry for `drs_replicator`, do not suggest connecting
remotely as `postgres` — it will be refused, and they will not know why.

If the source runs `scram-sha-256`, do not emit `md5` entries.

If the table has five columns, read its structure before writing an `INSERT` for it.

A command that fails costs more than the time it took to write: it costs their confidence
that you know what you are doing.

### 6. Confirm success before proposing destruction

Never go from a technical step straight to "shall I destroy this?".

Tell them what was achieved, in their terms — how many tables, how many rows, how long it
took, that it matches their source. Then ask about cleanup.

---

## Translating errors

Error codes mean nothing to them. Translate, then give the fix.

| Instead of | Say |
|---|---|
| `FULL_PG_SRC_DB_PRIVI_IS_NOT_ENOUGH_V2` | "The replication user can read your tables but not the sequences behind auto-numbered columns. One grant fixes it." |
| `DB_LC_MONETARY_INCONSISTENCY` | "The new database formats currency differently from yours. DRS won't migrate across that difference. I'll change the new one to match — never yours." |
| `SRC_HAS_DATABASE_WITH_NO_TABLE` | "DRS says it can't see any tables to migrate. Your database is fine — we counted them in Step 2. The task just doesn't have them selected yet. I'll fix the task." |
| "The database user must allow remote connections" | "PostgreSQL is refusing the connection because of how the access entry was written — it expects a different password format than the one we used. Let me correct it." |

---

## Words that need defining the first time you use them

Brief, in passing. One clause, not a lecture.

- **DRS** — Huawei's migration service; it copies the data and then keeps copying changes
- **Full sync** — the initial copy of everything
- **Incremental** — ongoing replication of changes after the initial copy, so the target
  stays current until you switch over
- **Cutover** — pointing your application at the new database. Nothing is shut down
- **Security group** — the cloud firewall in front of a server
- **`pg_hba.conf`** — PostgreSQL's own access list, separate from the firewall
- **EIP** — a public IP address in Huawei Cloud
- **/32** — a rule that allows exactly one IP address and nothing else

---

## Sensitive values

They will hand over passwords and access keys. Handle them carefully and say that you are.

- State that you export them as environment variables and write them to no file
- Warn against pasting keys into shared channels or screenshots
- Suggest rotating them afterwards if they were shared anywhere visible
- Mask passwords when echoing a command back
- Never put a password in a `.tfvars` file, and mention that `terraform.tfstate` holds
  sensitive values and should not be committed

---

## Pace

One step at a time. Do not send three steps' worth of commands at once — they will run
them out of order or skip the verification between them.

After each thing they run, confirm what you see in their output before moving on. That
confirmation is also how they learn the process is under control.
