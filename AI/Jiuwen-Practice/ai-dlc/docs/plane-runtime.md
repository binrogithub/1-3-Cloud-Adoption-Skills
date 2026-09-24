# Plane runtime — the authorisation and sandbox record

The measured settings that let the planning plane (`bin/plan.py dispatch`)
run unattended against the shipped gateway client
(`<gateway-client> chat … --jsonl --cwd <repo>`). This is a
living operational record, not evidence: it is edited when the runtime
changes, and the failure modes below were measured on this host when a
layer was absent. The spec contract is
`openspec/specs/runtime-authorization/spec.md` (the `devteam` change
that authored it is archived at
`openspec/changes/archive/2026-08-30-devteam/`).

## 1. The three permission layers

No responder exists in a headless run, so a permission `ask` is an
interrupt that fails the dispatch (exit 7). All three layers were
measured and all three are satisfied. Layers 1 and 2 live in our runtime
configuration `<gateway-home>/config/config.yaml`, never in
dependency source.

1. **Tool permission defaults** — `permissions.defaults` in config.yaml:
   `'*': allow`. The floor under everything.
2. **Per-tool baselines** — `permissions.tools` (schema
   `tiered_policy`): every tool the plane uses is `allow` — `bash`,
   `edit_file`, `write`, `write_file`, `search_replace`, `acp_chat`,
   `mcp_exec_command`, `read`/`grep`/`glob`/`list_dir`, the memory and
   todo tools. A per-tool baseline overrides the default, so this layer
   is what actually grants execution; it must stay `allow` even though
   the default already is.
3. **Parameter-level rules** — `permissions.rules` plus the built-in
   shell guardrail. The rules carry a command-shape pattern and a
   severity: LOW rules (`shell_allow_ls`, `shell_allow_git_status`, …)
   pass a single simple command, HIGH/CRITICAL rules (`shell_ask_rm`,
   `path_ask_env` on `**/.env*`, …) ask in `permission_mode: normal`.
   On top of them the shell AST structure guard
   (`tiered_policy:shell_ast:structure_guard`) decomposes a compound
   command — `cd X && … | …` — and interrupts on the compound shape
   **even when the tool baseline grants execution and every part
   separately matches an allow rule**; this was measured live on this
   host (2026-08-30, `evidence/v0.9.0-devteam/d4/live-interrupt.md`: a
   `ls -R … | head -50` asked although both `shell_allow_ls` and
   `shell_allow_head` matched). Consequences when the engine is on,
   both formerly baked into the role prompt (`bin/plan.py
   assemble_prompt`):
   - role prompts instructed single simple commands only;
   - the working directory came from the dispatch (`--cwd`), never
     from a `cd` inside a command.

   **Retired with the open runtime (open-plane, 2026-08-30):** both
   clauses are gone from the prompt — they described a constraint the
   runtime no longer imposes, and the prompt-surface audit
   (`bin/plan.py prompt_surface_audit`) rejects their return.

   No rule inside the enabled system — LOW, `action: allow`, pattern
   `*`, or a persisted approval override — opens these floors: they
   evaluate in the tiered policy, below the rules layer. The one lever
   sits a layer above it: the engine's real entry (`check_permission`,
   core.py:145) short-circuits at core.py:161 when
   `permissions.enabled` is false, returning allow before the tiered
   policy is reached. The direct-evaluation helpers the offline study
   used are documented as exempt from that short-circuit (core.py:99
   and 115: 「不受 enabled 开关…短路影响」) — measuring through them is
   how the wrong "no switch exists" conclusion was reached; the
   corrected study carries the proof
   (`evidence/v0.9.0-landing/permission-matcher-repro.py`). The
   built-in high-risk command rules load from
   `<gateway-home>/config/builtin_rules.yaml` (preferred) or the
   in-package copy. §3 records the standing state.

Backups: the configuration prior to the current settings is
`<gateway-home>/config/config.yaml.bak.1788022906` (an older
snapshot is `config.yaml.bak`). Restore: copy the `.bak` back over
`config.yaml`, then `systemctl restart jiuwenswarm-gateway`.

## 2. The service sandbox

Two regimes stand on this host, and the runtime is correct under both
(the open-sandbox PRD's invariant I6):

- **Open (standing since 2026-09-01, operator decision)** — the unit
  reads:

  ```
  NoNewPrivileges=true
  PrivateTmp=false
  ReadOnlyPaths=<local-dir> /opt/open-design
  ```

  The second entry (uidesigner-opendesign, 2026-09-01) is the pinned
  design reference tree: read-only **inside the gateway's namespace
  too**, because root sessions bypass DAC permissions (measured —
  chmod 0555 does not stop a root session writing it) and a systemd ro
  bind mount does. The design dispatch reads the tree; nothing ever
  writes it, and a tree that moved off its pin stops every design
  dispatch (exit 26). `ProtectSystem=strict` and `ReadWritePaths` are
  retired: the whole filesystem is the sandbox (decision, accepted
  residuals and rollback
  drill in `docs/prd-gateway-open-sandbox.md`; the pre-open unit is at
  `….service.bak.1788207660`, older states at `….bak.1788196532` and
  `….bak.1788023482` — copy one back, `daemon-reload` + `restart`, to
  return to the hardened form). In this regime a standing path is
  almost always **writable** — one class in practice.
- **Hardened (any `.bak` restore)** — the unit below, and the
  **three classes** return exactly as recorded.

`/etc/systemd/system/jiuwenswarm-gateway.service`, hardened form
verbatim (as widened 2026-09-01 — see the change record below):

```
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/root /var/lib/aidlc
ReadOnlyPaths=<local-dir>
```

Consequence (hardened form): the service mounts a **private** `/tmp`
and `/var/tmp`, and everything outside the writable grants reads
read-only — the whole file hierarchy, `/usr`, `/etc`, `/boot` included
(`ProtectSystem=strict`). A target therefore falls into one of
**three classes**, and `bin/plan.py classify --repo <path>` says which
by probing read and write separately through the service's own mount
namespace (`/proc/<MainPID>/root/...`) — never by matching the path
against known prefixes.

How the class is **decided** (changed 2026-09-01, the open-sandbox
PRD's I1/I2 — the probe once read a pollutable namespace as truth,
which is what misclassified `/tmp/country-e`):

1. The probe creates nothing (`os.access`, not mkdir), and
   `probe_created_paths` is asserted empty — a probe that would leave a
   path standing is a refused classification, never a class.
2. The deepest mount covering the path is compared between the
   gateway's `/proc/<MainPID>/mountinfo` and the caller's own: a mount
   only the gateway's namespace sees is a **veto** — `invisible`,
   whatever the probe reports behind it (`masked_by` names the mount,
   `decision_basis: "mountinfo"`). In the open regime the comparison is
   trivially equal but always runs — under a `.bak` restore it is the
   only honest judge.
3. Otherwise the probe decides, except against an **allowlist the unit
   actually declares**: a probe-writable path beyond a declared
   `ReadWritePaths` drops to `readable` (the conservative answer,
   `decision_basis: "grants"`). An open unit declares nothing, so the
   probe's writable there is agreement, not disagreement.

| class | the probe says | what a round does |
|---|---|---|
| writable | visible, writable | dispatches against the project itself — no scratch, no copy |
| readable | visible, not writable | **read in place**: the working directory is a scratch under `<plane root>/.ai-dlc/scratch/`, the project is granted as an additional trusted location for reading by absolute path, and nothing is written into it |
| invisible | not visible at all | a self-contained copy is staged under `<plane root>/.ai-dlc/stage/` and the round runs against the copy |

Under the **open** regime the same table holds but nearly everything
standing is `writable`; the readable/invisible rows are what a `.bak`
restore brings back (and what the mount veto still says under it for
paths the private namespace carries).

The plane root is the unit's writable area minus the gateway's own data
directory (`<gateway-home>`) — today everything under `/root`
outside `<local-dir>`, plus `/var/lib/aidlc` (the containment plane's
signed records and, from P3, the migrated spec trees). Scratch and
staged workspaces live under `<workspace-root>/.ai-dlc/`, never inside a
project the round must not write. A readable target must not be copied
(`plan.py stage` refuses and names the bytes the copy would have cost),
a copy that is not self-contained stops the run before dispatch, and a
target that used to be invisible but now probes readable is read in
place with the earlier copy recorded as not reused.

When a read-in-place round finishes, `plan.py return` copies exactly one
thing back into the real project — the change directory — refuses any
return carrying more (or gateway bookkeeping inside it), and removes the
scratch unless its retention is recorded with a reason.

Widening the unit for a target is **not** a remedy the runtime may
apply to itself: `plan.py sandbox --audit-unit <draft>` refuses a draft
that adds any writable path (exit 21) and names the split workspace
instead, and `plan.py sandbox` reports any existing writable grant that
is a project tree rather than the runtime's own area. Unit changes are
host steps a human applies; the sandbox guard keeps the runtime from
ever making them.

**Changed 2026-09-01 (operator decision, the open sandbox):** the unit
was opened as recorded at the top of this section — Robin, in-session:
「授权 openjiuwen 全文件夹访问权限，把整体安装环境当作沙箱。先完整功能
可用。」`ProtectSystem=strict` and `ReadWritePaths` retired,
`PrivateTmp=false`; kept `NoNewPrivileges=true` and
`ReadOnlyPaths=<local-dir>` (zero functional cost). The decision and
its accepted residuals — sessions run as root and, with the wall down,
the verdict key is readable and the openspec binary writable, so
signed records degrade from mechanically unforgeable to trusting the
session itself — are recorded in
`docs/prd-gateway-open-sandbox.md` (§1, §10). What the runtime owes
back in exchange (landed the same day, the PRD's P1/P2): a classify
that creates nothing and lets a namespace-only mount veto its probe
(I1/I2 above), and a close that checks the repo's reachability BEFORE
the plane's tree is touched (I3 — exit 11, plane untouched, no second
way out) and resumes a half-closed tree at the write-back alone (I4 —
tree shape `changes/<id>` gone + `archive/<date>-<id>` standing, the
standing archive named, the resume signed into the record and
`resumed_from` carried in the close JSON). End-to-end acceptance:
`R-G1`..`R-G4` in the PRD; the fresh-`/tmp` lifecycle (`R-G2`) closed
through the plane with a plane-authored write-back commit on the host
(change `rg2-check`, 2026-09-01).

**Changed 2026-09-01 (operator-directed, containment P2/P3):** the two
hardcoded grants (`<gateway-home>`, `<workspace-root>`) became a
policy — `ReadWritePaths=/root /var/lib/aidlc` with
`ReadOnlyPaths=<local-dir>` carving the gateway's own source (the uv
tool install) back out, and `ProtectHome=read-only` dropped because it
protects `/root` as a whole and only specific subdirectories can be
carved back out of it. (Superseded the same day by the open-sandbox
decision above; the text stays as the record of the hardened form's
own history.) Probed through the service's own mount view
(session `aidlc-perm-probe1`): writable `/var/lib/aidlc/records`,
`<workspace-root>/**`; refused `<local-dir>`, `/usr/local/bin` (the
openspec binary — containment §5.2 depends on this), `/etc/aidlc` (the
verdict key); `/usr/local/bin/openspec --version` executes (1.10.0).
The pre-widening unit is kept at
`/etc/systemd/system/jiuwenswarm-gateway.service.bak.1788196532`
(the two-grant state itself at `….bak.1788023482`).
Restore either: copy the `.bak` back over the unit, then
`systemctl daemon-reload && systemctl restart jiuwenswarm-gateway`.

## 3. The external-directory allow list

`permissions.external_directory` in config.yaml — the read/write reach
for directories outside the gateway's own roots:

```yaml
  external_directory:
    '*': ask
    "<repo-path>": "allow"
    "/tmp/jw-canary": "allow"
    "/tmp/ojtest": "allow"
    "<gateway-home>/ojtest": "allow"
    "<workspace-root>/ojtest2": "allow"
```

The two `/tmp` entries were dead weight under the hardened unit's
`PrivateTmp` — the gateway could not see those paths. Since the
2026-09-01 open sandbox (§2) the gateway sees and writes `/tmp` like
anywhere else, and the `'*': allow` wildcard below makes the explicit
entries redundant in either regime; they stay as the historical record
they already were. Anything not listed was `ask` under the closed
engine, which headless is an interrupt (exit 7, the JSON names the tool
and its argument).

**Changed 2026-09-01 (operator-directed, same widening as §2):** the
wildcard is `"allow"` now — `external_directory.'*': allow` — so a
round in a directory nobody named runs without the headless interrupt.
The boundary that remains is the service sandbox (§2): the mount
namespace, not the prompt, is what keeps the gateway source, the
validator binary and the verdict key read-only. The explicit allow
entries above stay as the historical record of what was granted one
tree at a time; they are redundant under the wildcard. Config backup:
`config.yaml.bak.1788197348`; restore it and restart the service.
Verified live (session `aidlc-perm-open-probe1`): a write into a
fresh directory on no allow list completed — no interrupt frame,
round_complete, rc 0.

**Adding a repository (the D5 procedure):** keep a timestamped backup
first (`cp config.yaml config.yaml.bak.<epoch>`), add the path under
`external_directory` as `"allow"`, then `systemctl restart
jiuwenswarm-gateway`. If the tree sits outside the sandbox's writable
grants (§2), the unit's `ReadWritePaths` must name it too, followed by
`systemctl daemon-reload` before the restart. Under the open sandbox
and the `'*': allow` wildcard (2026-09-01) neither step is needed — the
procedure remains for the hardened form a `.bak` restore brings back.

Added 2026-08-30: entry `"<workspace-root>/e2e-devteam": "allow"` (D5);
prior configuration kept at `config.yaml.bak.1788033962`. Added
2026-08-30 (landing L5, user-approved): entry
`"<skills-repo>": "allow"` (backup
`config.yaml.bak.1788039295`) plus the unit drop-in
`/etc/systemd/system/jiuwenswarm-gateway.service.d/landing-l5-target.conf`
naming that tree in `ReadWritePaths` (it sits outside `<workspace-root>`,
and `ProtectSystem=strict` applies); `daemon-reload` + restart followed.
Removing the drop-in file and the config line undoes the whole grant.

**Revoked 2026-08-30 (same day, landing L7.7):** the L5 grant above is
gone — the config entry was removed, the drop-in directory was deleted
entirely, `daemon-reload` + restart followed, and the effective state
was verified: `ReadWritePaths=<gateway-home> <workspace-root>`, no
`<internal-project>` line under `external_directory`, service
active. The run that needed the grant was reclassified as a rehearsal
(the tree held dependency source this project may not modify); the
deliverable was handed over as a patch and the target returned to as
found. A grant follows its target — the target is gone, so the grant
is gone.

Added 2026-08-30 (landing L5 qualified acceptance): entry
`"<workspace-root>/benchmark-accept": "allow"` (backup
`config.yaml.bak.1788042319`) for the disposable local copy of
a CSV-parsing benchmark project (inline form) that the amended
acceptance spec requires. Still in place
while the run waits on a human decision (the specs role is blocked on
a permission ask — see
evidence/v0.9.0-landing/acceptance-qualified.md); removing the line
and restarting the gateway undoes it, and the copy is deleted with the
run's end either way. No drop-in: the tree sits under <workspace-root>,
which the base unit already grants.

**Opened wide 2026-08-30 (user decision, same run):**
`permissions.enabled` set to `false` (backup `config.yaml.bak.1788061129`),
then `systemctl restart jiuwenswarm-gateway`; verified active and the
formerly blocked command now evaluates `allow` ("Permission system is
disabled"). Why this lever and no other: the specs role's opening
command is a compound `ls … 2>/dev/null; echo …`, and the offline
reproduction (`evidence/v0.9.0-landing/permission-matcher-repro.py`)
proved every subcommand of it already matches a LOW allow rule while
two code-level floors — the shell-AST structure guard on any redirect
and the shell-operator escalation on any `` ;&|`<> `` metacharacter —
force an ask that **no** config rule can override (LOW rule,
`action: allow`, pattern `*`, even a persisted approval override all
still ask). The only switch that admits the command is disabling the
permission system, and the human chose it explicitly. While in effect
there are no parameter rules, no structure guard, no operator
escalation, and no external_directory asks — every tool call is allow.
What still constrains a run in that window: the service sandbox (§2 —
writes confined to `<gateway-home>` and `<workspace-root>`), this
pipeline's own gates (dispatch admission exit 12, the boundary check
exit 8, MERGE_GATE held by a human), and the role prompt.

**Closed 2026-08-30 (same day, run ended):** `permissions.enabled`
restored to `true` and the copy's `external_directory` entry removed in
one editing session (backup `config.yaml.bak.1788062369` taken first,
then restart). Verified three ways: `enabled: true`, no `benchmark-accept`
entry under `external_directory`, and the specs opener evaluates to
`ask` again via `tiered_policy:shell_ast:structure_guard` — the guard
that stopped the run's first five attempts is back on duty. The
disposable target was deleted with the run's end and the source
repository verified untouched (same 11 untracked paths, zero tracked
modifications). The benchmark-accept grant paragraph above is kept as
history of the run; nothing of it remains in the live configuration.

**Open as the standing state since 2026-08-30, late (open-plane):**
the engine is disabled again, and this time it is the scripted,
standing state of the runtime rather than a window a run opened.
Backup taken before this standing state:
`config.yaml.bak.pre-disable.1788088854`. `./install.sh
--provision-plane` performs and proves the whole step idempotently —
back up, disable the engine (the only setting that clears the shell
structure floor), keep the service unit writable at exactly the
runtime dir and `<workspace-root>`, `daemon-reload` + restart, wait for
the gateway to accept connections, then a live probe: one command
combining a redirection, a substitution and a pipe, carrying a token
generated at probe time through the shipped client; the mode exits
non-zero when the token does not come back or the frames carry an
interrupt, and names the backup when the gateway does not return. A
second run reports no change and skips the restart.
`./install.sh --doctor` reports the engine state, the writable grant
and the cost below, and names any writable path beyond the project
root as a finding.

The cost, stated plainly (the same price the earlier window paid):
with the engine off there are no parameter rules, no structure guard,
no operator escalation and no external_directory asks — every tool
call inside the writable grant is allow, and the built-in
high-severity shell rules (`rm -rf`, `mkfs`, reverse shells) no longer
ask either. Inside those paths a role can do anything a shell can do.
The systemd sandbox (§2) is the only remaining boundary, and it is
what keeps the rest of the machine read-only. What else still
constrains a run: this pipeline's own gates — dispatch admission
(exit 12), the boundary check (exit 8), the frame checks that keep
the author from being the judge now that the CLI is reachable
(validator invocation exit 13, destruction of a pre-dispatch baseline
path exit 14), MERGE_GATE held by a human — and the role prompt.
Restore the closed state: copy the backup over `config.yaml`, then
`systemctl restart jiuwenswarm-gateway`, and expect the compound
shapes to ask again — that is the closed state doing its work. The
"Closed 2026-08-30" account above is the history of the earlier
window, superseded by this standing state.

## 4. Gateway bookkeeping directories

The gateway writes three directories into a working tree it runs in —
`.agent_history/` (file-operation history), `coding_memory/` (the coding
memory store) and `prompt_attachment/` (prompt attachments). They are
gateway bookkeeping, not product surface, so `bin/plan.py boundary`
excludes exactly these three (`GATEWAY_BOOKKEEPING` in `bin/plan.py`);
every other path outside `openspec/changes/<change>/` aborts the task
(exit 8, the paths are named, nothing is cleaned up).

## 5. Where usage lives

No budget capability exists (landing L1): nothing in this repo computes,
caps, stops, warns or annotates on a token total. A dispatch's usage is
read where upstream already records it — the session history
`<gateway-home>/agent/sessions/plan-<change>-<artifact>/history.jsonl`:
keep the rows with `event_type == "chat.usage_metadata"`; the rows are
per-request, not cumulative, and `metadata.json` is never also read
(it duplicates the totals and double-counts). An executor's usage lives
in its own agent transcript. The two sources follow different
conventions — the gateway's `input_tokens` already includes its cache
figure, a transcript's does not — so each is reported on its own terms
and never combined into one total (that mismatch once doubled the
reported planning spend: 2,263,762 reported where the truth was
1,179,346, of which 94,930 was genuinely cold).

## 6. The design dispatch and its records (uidesigner-opendesign)

The design role is the one dispatch whose working directory is the
**repo**, not the plane tree: it writes the product surface. Everything
else keeps the authorisation shape of §1–§5 — one fresh session
(`design-<change>-<seq>`), frames on disk under
`.ai-dlc/tasks/<task>/evidence/plan-design-<seq>.jsonl`, usage read
where §5 says.

- **The reference tree** stands at `/opt/open-design` (sparse clone of
  tag `open-design-v0.21.1`, sha `fbd4d48`, 138M: `skills/`,
  `design-templates/`, `design-systems/`), root-owned 0555/0444, pinned
  by `.aidlc-pin.json` (`tree_sha256` = sha256 over every file's
  sha256+path, sorted). Deployed and rolled back by
  `scripts/install-opendesign.sh` (an operator host step — it also
  writes the one `external_directory` allow entry of §3 and installs
  the one pointer skill; backups and read-backs at every step). The
  tree is read through the `ui-designer` skill: the body says where
  the tree is and how to pick by frontmatter — not one word of the
  upstream prose is copied into this repo.
- **The five facts** (`bin/plan.py design`): the record is computed by
  the CALLER from the session's frames and the filesystem, never taken
  from the role's closing sentence — (1) a read of an upstream
  `SKILL.md` (path + sha256), (2) files written, verified standing in
  the repo's product surface, (3) every referenced asset resolves
  (local exists; remote HEAD answers, 404 fails), (4) pages render
  (local static server, HTTP 200, non-empty DOM), (5) no placeholder
  content (lorem/TODO/placeholder-image). All five hold →
  `/var/lib/aidlc/records/<change>/design-001.json`, signed like every
  verdict record. Any one fails → **no record**, exit 1, and deliver
  reports `design_unverified` (D8: claims the frames contradict write
  nothing). Heredoc bodies are stripped before write targets are read,
  so a page's own markup (`…">` then text) never reads as a write.
- **The four deliver states** (`bin/report.py deliver`, `design` key —
  a report, never a delivery gate): `design_applied` / `design_declined`
  (`plan.py decide --design skip --reason … --decided-by <named
  person>`) / `design_unverified` (applicable with no verifying
  record, or a record whose signature failed — tampering evidence, the
  rejected files named) / `design_not_applicable` (the measured
  surface carries no web or deck file). Applicability is measured:
  web extensions, `.pptx`, html under `slides//deck/`, markdown with
  deck frontmatter. A change with none of them asks for nothing, and
  `plan.py design` on one refuses exit 24 before the client exists.
- **PDF/PPTX/MP4 export does not exist here** — it belongs to the od
  daemon (Node 24 + pnpm, or Docker), deliberately out of scope until
  P4 of the PRD; nothing in this repo claims it.
