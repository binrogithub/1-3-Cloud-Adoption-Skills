# Rollback

## The principle that makes rollback easy

**The source is never modified.** No schema changes, no data changes, no configuration
changes applied by the AI. The only things that touch the source during the whole
workflow are:

- a security group ingress rule for the DRS EIP, `/32`,
- two or three `pg_hba.conf` lines plus a reload,
- optionally, one probe table in Step 10 — only with explicit approval.

All three are additive and reversible. The source stays fully operational throughout, so
rollback is almost always just "stop and remove what was added".

---

## By phase

### Before the task is created (Steps 0–4)

Nothing has touched the source. The target may exist.

```bash
terraform destroy
```

Nothing else to undo.

---

### After the task is created, before it starts (Steps 5–7)

No data has moved. The task exists, and the source has the temporary access rule.

1. Delete the task:
   ```
   DRS BatchDeleteJobs --delete_type=delete    (confirm=true)
   ```
2. Remove the source security group rule.
3. Ask the human to remove the `pg_hba.conf` entries and reload.
4. `terraform destroy` if the target is not being kept.

---

### During full sync (Step 8)

The target holds partial data. The source is untouched and serving traffic normally.

1. Stop the task:
   ```
   DRS BatchStopJobs --pause_mode=all    (confirm=true)
   ```
2. Decide: retry or abandon.
   - **Retry** — the target must be clean first. Drop and recreate the target database,
     or destroy and re-provision the instance. Restarting a full sync onto a partially
     populated target produces conflicts.
   - **Abandon** — delete the task, remove source access, `terraform destroy`.

No impact on the source either way.

---

### During incremental sync (Step 9–10)

Full sync finished, the target is live-following the source. Still no cutover, so the
application is still on the source.

1. Stop the task. The target freezes at whatever point it reached.
2. The source continues normally — it never depended on the task.
3. If the migration is being abandoned, clean up as above.

The target and source will diverge from the moment the task stops. If you intend to
resume later, plan on a fresh full sync rather than restarting the incremental.

---

### During or after cutover (Step 11)

This is the only phase where the application is affected.

**The rollback is the connection string.** The source was never modified, so it is still
correct and still running:

1. Point the application back at the source.
2. Verify the application works.
3. Stop the DRS task.

**The caveat.** Any write that landed on the target after cutover is not on the source.
Before reverting, determine whether the target received writes:

- If no writes reached the target — revert freely, nothing is lost.
- If writes reached the target — those rows exist only there. Export them and apply them
  to the source manually before reverting, or accept the loss deliberately. There is no
  automatic reverse sync in this scenario.

This is why cutover is an explicit gate and why writes should be stopped and the delay
allowed to reach zero before switching.

---

## Cleanup checklist

Whatever the outcome, confirm all of these:

- [ ] DRS task stopped and deleted (`ShowJobDetail` reports it no longer exists)
- [ ] Source security group rule for the DRS EIP removed
- [ ] Source `pg_hba.conf` entries removed and configuration reloaded
- [ ] Probe table dropped from the source, if Step 10 Option B was used
- [ ] Target destroyed, if the migration was a test
- [ ] Passwords used during the run rotated, if they were shared over chat or logs
- [ ] `terraform.tfstate` not committed anywhere — it contains sensitive values

The first three matter most. A DRS task left running keeps billing, and a stale firewall
rule leaves PostgreSQL exposed on the public Internet to whoever inherits that EIP.
