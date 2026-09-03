# CHANGELOG

## v0.19.0 — phase-chain automation, Phase A: queue the next phase's task skeleton on an approved close (PRD `phase-chain-automation`, Robin's approval 2026-09-03)

A multi-phase initiative (a proposal that splits work into "Phase 1 / Phase
2 / Phase 3", the way `openjiuwen-efficiency-v1` did) existed only as prose:
nothing recorded which change was which phase of what, and nothing created
Phase 2's task skeleton once Phase 1 merged. A separate task record showed
the same class of gap at the single-task level — a delivery report can print
the exact remedy command and still nothing carries it to a person.

- **`plan.py initiative register/advance/status`** (`bin/initiative.py`,
  new): `register` writes `.ai-dlc/initiatives/<id>.json` — an ordered list
  of phases (`change_id`, `status`). `advance --change <closed-id>` marks
  that phase `delivered` and, if the next phase is `pending`, creates its
  task skeleton through the exact same code path manual `report.py init`
  uses — clean-slate, nothing copied from the phase that just delivered —
  then marks it `queued` and appends `INITIATIVE_PHASE_QUEUED` /
  `INITIATIVE_COMPLETE` to the repo's `events.jsonl`. `status` is read-only.
- **Standalone in this pass.** `advance` is invoked by hand; it is **not**
  wired into `plan.py close`'s tail (that hook is Phase B, a separate
  change — it touches the existing merge-gate tail rather than being purely
  additive, so it gets its own review). A change id absent from every
  initiative manifest is untouched by any of this — every existing
  single-phase task's behavior is unchanged (INV-6, the acceptance bar
  this feature had to clear to land at all).
- Every scenario in `openspec/specs/phase-chain-automation/spec.md` — clean
  next-phase state, one change id per initiative, failure isolation (a
  failed `advance` never rolls back the phase that already closed), no-op
  for unregistered changes — has a direct test in
  `tests/test_initiative.py` (11 cases); full suite still green (47 passed,
  no regressions).

## v0.18.0 — the design surface: a pinned read-only OpenDesign reference, one pointer skill, conclusions as signed records (PRD `uidesigner-opendesign`, Robin's 「实施prd」 2026-09-01)

P0 measured before anything moved: the sparse reference tree
(`--filter=blob:none --sparse`, the three content dirs) is **138M** on
this host against a 1.8 GB full clone; the CC runtime shell saw the
tree before N5 closed it (documented pre-existing leak, then closed);
the one pointer skill costs **+265 frontmatter chars** of registry
surface for every session (live journal shows it read at every session
assembly — R4's cost, measured not assumed). P0 findings beyond the
plan: the shipped tree lists 162 skills against the PRD's 139 (drift,
not plan-changing), and git 2.27 writes cone sparse-checkout files
without the `/*` `!/*/` header patterns, leaving `apps/ docs/ plugins/
packages/` on disk — the install script hand-writes the five-line
pattern file.

- **the upstream stands pinned and read-only (N3/N6)**: deployed at
  `/opt/open-design` (tag `open-design-v0.21.1`, sha `fbd4d48`, pin
  `.aidlc-pin.json` with a `tree_sha256` over every file's digest) by
  `scripts/install-opendesign.sh` — an operator host step, idempotent,
  with the config/skill edits backed up and read back. The pin is the
  dispatch's own digest contract: a tree that moved off it stops every
  design dispatch before a session opens (exit 26, measured vs pinned
  digest in the refusal — I3's detection half). Root DAC does not stop
  root sessions (chmod 0555 measured insufficient — D4's finding), so
  the enforcement is the gateway unit's `ReadOnlyPaths=/opt/open-design`
  (systemd ro bind mount, bites root too; unit `.bak.<ts>` kept).
- **applicability is measured, not asked**: `design-scope` reports the
  change's product surface by class — web extensions, `.pptx`, html
  under `slides//deck/`, markdown with deck frontmatter — and `design`
  refuses exit 24 when nothing applicable stands ("a backend change
  buys no beautifying"). Exits 24/25 (skill)/26 (pin) all fire before
  the client exists; the stub-client tests prove the marker never
  appears.
- **one pointer skill, no upstream prose (N2)**: `ui-designer` in the
  gateway workspace — where the tree is, how to pick by frontmatter,
  read the chosen SKILL.md in full. Linking 139 skills is dead
  (`react.skill_mode: all`, no per-session filter exists); E4's
  decision, the `openspec-author` shape.
- **the record is the frames' (N1)**: `plan.py design` opens one fresh
  session whose cwd is the repo, then reads five facts from the frames
  and the filesystem — which upstream SKILL.md was read (path+sha),
  which files were written (verified standing, heredoc bodies stripped
  so a page's own markup never reads as a write), assets resolve, pages
  render (local server, HTTP 200, non-empty DOM), no placeholder
  content. All five hold → signed `design-<seq>.json` record; any fail
  → no record (exit 1) and deliver reports `design_unverified` (D8: a
  session that claims the work without reading the upstream writes
  nothing, however loudly it claims). Three fact-reading defects were
  found by the first live round refusing (the honest failure working as
  designed) and are pinned in the tests: a write tool's truncated
  arguments blob read as shell text made every `>word` in the page a
  phantom write; `preconnect`/`dns-prefetch` hint hrefs are connection
  hints a browser never fetches (fonts.googleapis.com's root 404s to
  everything), so they are skipped and a HEAD 404 falls back to GET;
  and the template fact now requires a read that **landed** — the
  shipped tree keeps no SKILL.md under `design-systems/`, and a
  session's probe for one left names in the frames that hashed null.
- **deliver's four design states, never a gate**: `design_applied` (a
  signed record), `design_declined` (a person's recorded skip —
  `decide --design skip`, class-word deciders refused),
  `design_unverified` (applicable, no verifying record — never folded
  to failure, never auto-rerun), `design_not_applicable` (measured).
  A tampered record is tampering evidence: `design_unverified` with
  the rejected files named (D7). The design state never joins the
  delivered conjunction (D6/D12 — country-e-m1 re-delivered today reports
  `design_unverified` while staying delivered).
- **the CC shell never sees the reference (N5)**: `aidlc-shell` masks
  `/opt/open-design` and every `od` on PATH (coreutils' od included,
  by name); a mask miss refuses to start. Live-verified both sides:
  inside the shell the tree and od are unreachable, outside both
  answer (D2/D3). `bin/` spawns no od/open-design process — an AST
  regression gate over every process call in `bin/` (I1/D1, green
  today and pinned green).
- **tests**: `tests/collapse/ud_design_gates.sh` — class matrix, the
  three pre-dispatch refusals with the client never invoked, D8
  offline frames, the positive five-facts record (HMAC-verified), D7
  tamper, the four deliver states, the heredoc strip, the AST gate,
  and the live D2/D3 shell block (skipped with a note where no tree
  stands). `glue_surface.sh` excludes `install-opendesign.sh` (the
  install.sh class: naming the host paths IS the deploy record).
- **PDF/PPTX/MP4 export is NOT claimed anywhere** — it belongs to the
  od daemon (Node 24 + pnpm or Docker), out of reach until P4, and the
  PRD forbids writing support for it before then. R1 stands honestly:
  invisibility of the tree to a determined caller is best-effort
  (mount masking + shell refusal), not a claimed enforcement.

## v0.17.0 — the open sandbox: whole machine as the sandbox, classify and close honest under both regimes (PRD `gateway-open-sandbox`, Robin's decision 2026-09-01)

P0 was a host step: the gateway unit's mount wall retired
(`PrivateTmp=false`, `ProtectSystem=strict` and `ReadWritePaths`
deleted; `NoNewPrivileges` and `ReadOnlyPaths=<local-dir>` kept) —
operator decision, recorded with its accepted residuals in the PRD
(§10): sessions run as root, the verdict key is readable and the
openspec binary writable, so signed records degrade from mechanically
unforgeable to trusting the session. Rollback anchor: tag
`v0.16.1-pre-open`; unit `.bak` chain (`….bak.1788207660` = pre-open).

- **classify tells the truth in both regimes** (P1, I1/I2): the probe
  creates nothing (`os.access`; `probe_created_paths` asserted empty —
  a probe that would leave a path standing is a refused
  classification), and the deepest mount covering the path is compared
  between the gateway's `/proc/<MainPID>/mountinfo` and the caller's
  own — a namespace-only mount **vetoes** the probe (`masked_by`,
  `decision_basis: "mountinfo"`). This is the fix for the `/tmp/country-e`
  misclassification: the old probe read the archive session's own mkdir
  residue in the private namespace as truth. Remaining disagreements
  with an allowlist the unit actually declares resolve to the most
  conservative answer (`decision_basis: "grants"`); an open unit
  declares nothing, so its writable is agreement. R-G1: classifying a
  nonexistent `/tmp` path leaves it nonexistent.
- **close checks before it moves, and resumes what already moved**
  (P2, I3/I4): the repo's class is established BEFORE the archive
  dispatch — not writable stops the close with the plane's tree
  untouched (exit 11, no second way out, the text pointing at the
  unit's regime or the path); a plane tree whose SHAPE says the
  archive already ran (`changes/<id>` gone, `archive/<date>-<id>`
  standing — the split state a failed close leaves) resumes at the
  write-back alone, against the standing archive directory (not
  today's predicted name), with the resume signed into the record
  (`resumed: true`, the archive literal's columns empty rather than
  lying) and `resumed_from: "write-back"` in the close JSON. R-G2
  passed live: a fresh `/tmp` repo closed end-to-end through the real
  plane with a plane-authored write-back commit on the host
  (`rg2-check`, 2026-09-01) — the exact path that split country-e-m1.
- **The suite is regime-proof**: d4/open_plane/l2 had silently coupled
  to the LIVE unit's hardened form (their `/tmp` fixtures classified
  through the real service); all close/classify-dependent tests now
  pin the class with fixtures, so the suite is green whichever regime
  the host stands in (I6). ad_any_directory grew the policy matrix
  (grants agreeing, mount refusing, open regime, missing view,
  conservative drop, namespace-only veto, non-creating probe); l2 grew
  the I3 stop and the I4 resume.
- **Rollback drill R-G4 (P3)**: `.bak` restored → classify honestly
  reports `/tmp` invisible by the mount veto (not by probe pollution)
  and close stops at I3 with the plane's tree untouched; re-opened
  after. `docs/plane-runtime.md` §1–§3 record both regimes, the new
  decision policy, and the standing open state.

## v0.16.0 — openspec containment, phase P4: the CC runtime shell (PRD `openspec-containment` N5; gates G2/G3/G5/G10 GREEN in the real unit)

P3 made the plane's world real; P4 closes it to the agent.
`bin/aidlc-shell` (installed at `/usr/local/bin/aidlc-shell`) starts
Claude Code — or any command after `--` — inside a systemd transient
unit (`systemd-run --collect --wait`, unit `aidlc-shell-*`) with
`NoNewPrivileges=yes`, an empty `CapabilityBoundingSet`, and
`InaccessiblePaths` over every openspec entry on PATH, the node module
tree behind it, and the plane's specs home.

- **The mask is built, not guessed** — `--print-mask` names the three
  surfaces. Every masked path must exist (systemd 239 fails the unit
  `226/NAMESPACE` on a nonexistent entry — measured), and the builder
  REFUSES to run if an openspec entry on PATH escaped the mask: a
  shell that silently stopped containing would be worse than none.
  `systemd-run`'s colon-list form is a trap (one nonexistent path →
  226); the directive is repeated per path. `--same-dir` is ≥243-only;
  `-p WorkingDirectory=` is the same mechanism on 239.
- **G2/G3/G4/G5 in the REAL unit** (`tests/collapse/n5_shell_gates.sh`,
  no fixture stands in for it): `openspec --version` → 127;
  `node <module>/bin/openspec.js` → MODULE_NOT_FOUND; read of the
  plane's tree → denied; write → `Permission denied`, nothing left
  behind. The **positive controls matter as much as the gates** (G9's
  lesson — a shut system is not a contained one): HOME travels in, git
  and the repo work, and the caller's own surface — the verdict key
  and the records store — stays usable, so the agent implements,
  delivers and reads signed verdicts inside the shell without ever
  needing the plane's sight.
- **The flagged conflict, resolved by ownership split**: with every
  capability dropped, uid 0 loses `DAC_OVERRIDE`, so the swarm-owned
  `0400` key and the `swarm:swarm` records store became unreadable to
  the caller — caller-side signing (N2/N4) would have died inside the
  shell. The caller's surface is now root-owned, group-swarm:
  `/etc/aidlc/verdict.key` `root:swarm 0440`, `/var/lib/aidlc/records`
  `root:swarm 0775` (owner access needs no capability); the plane's
  surface stays `swarm:swarm 0750`. Ownership now encodes who works
  where — and P5's uid split drops root instead of re-cutting it.
  `/etc/aidlc` is deliberately NOT masked: closing it would move
  signing into the very process being contained.
- **Plane-sight CLIs stop honestly inside the shell** —
  `masked_surface_refusal` (exit 12) for `validate` dispatches, role
  dispatches, `boundary` and the archive tail: the mask is named
  ("run it from the operator's shell, outside aidlc-shell"), never
  mistaken for a missing tree (a `migrate` remedy that cannot run),
  never judged blind. The mask hides existence from the caller; the
  gateway still knows. The archive's filesystem proof is read from the
  tree, so `close` is the operator's by construction.
- **G10 — discrimination** (`tests/collapse/g10_discrimination.sh`):
  the demo incident's own delivery report — `spec_valid: true` on the
  strength of an `openspec validate demo-site --strict` the caller ran
  itself — is snapshotted verbatim
  (`tests/collapse/fixtures/g10-demo-m1-report.json`) and judged RED by
  today's `deliver`: `spec_unverified`, the dispatch remedy, no
  validator rc anywhere, nothing auto-run. The same code path reads a
  SIGNED plane verdict as `spec_valid`, and a forged verdict with the
  plane's field shape is named tampering evidence — the gate
  discriminates; it neither blanket-rejects nor passes the incident.
- Live regression: the real-gateway validate dispatch still runs from
  the operator's shell (15.1 s, signed `verdict-001.json`,
  `spec_valid`). Suite **34/34**.
- Residual, honestly: `handwritten_paths` still admits uid 0 —
  aidlc-shell stripped the caller's capabilities but not its uid, so a
  hand-written root-owned file under a change dir remains
  indistinguishable from the service's writes until P5's uid split.

## v0.15.0 — openspec containment, phase P3: the tree moves into the plane's home, the archive runs as one dispatch, the implementation gets behavior only (PRD `openspec-containment` N6/N2/N7)

P2 made the plane's reads real. P3 moves the spec surface itself: the
project's `openspec/` tree leaves the repo and lives in the plane's home
for the whole working period, every dispatch writes there, and the tail
of a change — the archive — runs as ONE plane session whose literals are
judged from the frames and then checked against the filesystem. What
Claude Code holds of a change is a behavior-only handoff.

- **N6 migrate** (`plan.py migrate --repo <repo>`, one time): a plain
  move of `repo/openspec` into `/var/lib/aidlc/specs/<repo-id>/`
  (`repo-id` = the absolute path with `/`→`--`), a `git init` of the
  plane root (the boundary gate keeps judging increments exactly as it
  always has), and the plane's ownership — `swarm:swarm`, `0750`, not
  world-readable, the basis G4/G5 lean on. Nothing inside the tree is
  built, mirrored or copied (D12 stays dead): the tree changes address,
  and the repo loses its `openspec/` by design (R5) until the archive
  dispatch writes it back. Two existing trees refuse with the remedy
  named. Every dispatch's cwd is the plane root; the review round's
  reviewer findings and author answers live in the plane's own
  `.ai-dlc/review/<change>/` surface (a readable round could never
  write inside the project), while the synthesis stays caller-side in
  the task record the caller owns. `snapshot`/`untouched` skip the
  plane's `.ai-dlc` symmetrically — caller state sits outside both
  trees' comparison.
- **N2 archive dispatch** — the close tail. The merge still runs
  caller-side and only behind an approved, rationale-carrying gate
  answer; then ONE gateway session runs the normalized archive literal
  (`openspec archive <id> --yes --json`, `--skip-specs` when specs
  return) plus the write-back literals (`mkdir`/`cp -a` the specs, the
  config, the archived change dir into the repo; `git add`;
  `git commit` as `ai-dlc-plane`). Every literal is judged from the
  frames — shlex-quoted in the prompt so a spaced commit message
  round-trips — a missing or result-less literal is **exit 23** with no
  record written, a non-zero rc is **exit 11** carrying the command's
  output verbatim, and the frames' word is never taken for the
  filesystem's: the plane's change dir must have moved, the archive dir
  must stand in both trees, the repo's specs must be back, and the
  repo's commit subject must carry the change — only then is the signed
  archive record written and the task closed.
- **G6 at the archive door** — a change dir that stands only repo-side
  (Claude Code hand-wrote it), a plane surface altered by hand
  (owner/mode no longer `swarm:swarm 0750`), or foreign-owned content
  under the change dir refuses with **exit 12** before any session
  exists: the plane archives its own work, never a forgery.
- **N7 behavior handoff** — the moment `accept` accepts a change, its
  executable entries land verbatim in `records/<change>/handoff.md`:
  behavior only, no spec tooling, no artifact formats, no validation
  surface. Without this cut the caller implements from memory of
  formats it has seen and hand-writes spec files; with it the repo's
  worktree is the only place implementation happens.
- **sweep under N6** — judged against the PLANE root (the run's writes
  live there): baseline paths skipped and recorded, bookkeeping gone,
  tracked modifications restored to HEAD, openspec retained for a
  person unless `--purge-openspec`; the repo-side task record goes
  unless `--keep-record` (an emptied record prunes its own ancestor
  skeleton, returning `.ai-dlc/` to what stood before the run); the
  task worktree/branch logic stays keyed on the repo's git.
- Tests converted to the plane world (the last nine): `l2_close_tail`
  (rewritten — the stub plane runs the prompt's literals exactly and
  reports oc4-style frames; the real openspec CLI archives inside the
  plane tree, all three G6 refusals, exits 23/11, `--keep-task-branch`
  retention), `l7_sweep`, `d3_plan_boundary`, `l7_target_safety`,
  `ha_red_first`, `ad_red_first`, `ad_any_directory`, `open_plane`,
  `dr_review_round`; `d3_plan_accept` gains the N7 handoff assertions.
  Suite **32/32**.
- Live positive control: `migrate` moved the probe repo's tree to
  `/var/lib/aidlc/specs/root--live-p3--repo`; `close` ran the real
  gateway archive dispatch in **99.3 s** — all seven normalized
  literals in the frames, specs + `2026-09-01-live-p3` written back
  into the repo under the plane-authored commit
  `openspec: archive live-p3`, `archive-001.json` HMAC-verifies, task
  record DONE, worktree/branch removed, the merge caller-side behind
  the approved gate.

## v0.14.0 — openspec containment, phase P2: the plane's tool dispatches exist for real (PRD `openspec-containment` N1/N3/N4)

P1 left every reader consuming signed records and tests minting them by
hand. P2 makes the producer real: three plane tool dispatches —
`plan.py validate`, `plan.py graph`, `plan.py status` — each opens ONE
fresh gateway session, names the commands it owes as normalized
literals (absolute path, `--strict`/`--json`, no metacharacters), and
judges ONLY the frames: the command must appear as its exact literal
and its rc/stdout are read from the matching `chat.tool_result`, never
from the model's conclusions. The record the dispatch writes is the
record the readers already read — the fixtures and the producer share
one signing path (`report.write_record`).

- **N1 validate** — the session's one business is
  `/usr/local/bin/openspec validate <id> --strict --json`; rc and
  stdout verbatim land in a signed verdict record (`{verb, argv, rc,
  stdout, sha256, change, ts, session, hmac}`). A session that
  paraphrases the command — relative path, a pipe, a redirect — fails
  with **exit 23** and writes nothing: a verdict exists only for a
  command the frames show the plane running exactly.
- **N3 graph** — one dispatch produces the change's graph record for
  its whole life: the session runs the normalized status literal plus
  the instructions literal for every artifact status reported, and the
  graph (ids, dependency edges, each conditional artifact's own
  inclusion conditions VERBATIM from its instruction prose) is derived
  mechanically from those outputs — nothing is asked of the model's
  judgment and nothing is inferred caller-side. An instructions result
  missing for any artifact is exit 23, because a partial graph must not
  exist.
- **status** — the same machinery for the artifact-state snapshot; its
  own record (PRD §8's three-record contract: graph · status ·
  verdict), read by `roles`/preflight/`artifacts_view`.
- **N4 signing** — HMAC-SHA256 over canonical sorted-key JSON; key at
  `/etc/aidlc/verdict.key` (0400), records under
  `/var/lib/aidlc/records/<change>/` (both env-overridable). Signing
  and writing share one path with verification
  (`report.write_record`), used by the dispatches and the test
  stand-in alike. The key is root-owned until the swarm account exists
  (P3 chowns it; the P4 shell will make caller-side signing impossible
  by design — the conflict is flagged in the task list).
- Frames are parsed by a quote/depth-aware reader of the gateway's
  result repr (`success=… data={'content': …} error=…`), measured by
  probe sessions `aidlc-rc-probe`/`aidlc-rc2-probe`: rc from the
  `Exit code N` first line, stderr/stdout split at the gateway's blank
  line, `error=None` on success. The author-dispatch prohibition
  (author must not judge its own output) is untouched — the verifier is
  a second, independent session.
- Gates green: `oc2_g7_tamper` (an edited record is dropped and NAMED,
  `spec_unverified`, a good record beside a tampered one stays
  unverified, an edited status record reads as no status at all),
  `oc3_g8_no_verdict` (deliver reports `spec_unverified` with the
  dispatch as remedy, no validator rc/output anywhere, nothing
  auto-runs), `oc4_validate_dispatch` (fresh session per dispatch,
  verdict verbatim and verifiable; relative/piped/redirected
  paraphrases exit 23 writing nothing), `oc5_graph_status` (graph
  record with conditions verbatim, status record, `roles` derives from
  both, the graph is never recomputed). Suite 31/31.
- Live positive control (G9, P2 scope): against the probe change
  `probe-ch` through the real gateway — validate 18.7 s (rc 0, the
  validator's own JSON verbatim, verdict-001.json verifies),
  graph 72.9 s (five normalized literals in one session; the four
  upstream design conditions recovered mechanically, matching the
  transcribed fixtures exactly), status 19.3 s (`ready`/`blocked`
  states pass through and read as not-done). `roles` then derives
  `dispatchable_now: [design]` from the three records alone.

## v0.13.0 — openspec containment, phase P1: the caller reads records, it no longer runs the tool (PRD `openspec-containment`)

openspec used to execute on the caller side — the caller being Claude
Code itself — so the judge and the judged shared a process. P1 of the
containment PRD removes every caller-side openspec process call and
moves the spec surface to records the plane produced and signed. The
judgment ownership reverses next phases (validate/archive dispatches
N1/N2 land in P2/P3); what P1 makes impossible is the caller silently
filling a gap by running the CLI.

- `bin/plan.py` holds no openspec invocation anymore: `openspec()` and
  `openspec_soft()` are gone, and every reader — `roles`, preflight,
  the resume-skip, `conditioned_artifact_states`, the review-round
  design gate, `skipped_artifacts`, `accept` — reads the change's
  signed **graph record** (artifact ids, dependency edges, conditional
  inclusion conditions) and the newest **validate verdict's** status
  block instead. A missing record stops with exit 22 naming the
  dispatch that produces it; nothing is recomputed caller-side.
- `accept` no longer runs `--strict` in-process: the verdict comes from
  the newest signed record, and one that predates the newest artifact
  write is refused as stale (exit 22) — a verdict must speak of what
  stands now. `revision_pending.validator_output` carries the record's
  stdout verbatim.
- `close` stops after the merge: archive is a plane dispatch (N2, phase
  P3), so until that lands close reports `archive:
  not_dispatched` with exit 1 rather than pretending — merged, honest,
  nothing archived.
- `report.py deliver` reads the same records and reports three states:
  `spec_valid`, `spec_invalid` (a signed rejection) and
  `spec_unverified` (no verdict or a signature that does not verify).
  `spec_unverified` is never folded into `spec_invalid` and never
  triggers a re-run.
- The records layer (paths, canonical form, HMAC-SHA256, verification)
  lives in `bin/report.py`, shared with the delivery surface; exit 22
  (record missing/bad signature) and 23 (a validate dispatch whose
  frames carry no normalized validator call) are reserved.
- The six `openspec-*` skills and the six `opsx` commands are deleted
  (D6/D7); the ai-dlc skill's CHECK step now requests the plane's
  verdict instead of instructing the caller to run validate (D8); the
  role prompt names the validate dispatch as the judge — author
  self-validation remains a frame violation (D9).
- Gate `oc1_g1_no_calls.sh` (reverse gate G1) judges by AST that no
  `run/Popen/check_*` call in `bin/` carries openspec, and that no
  skill/command file instructs executing it. Tests mint signed
  records through `tests/collapse/records_tool.py`, standing in for
  the dispatches that will produce them for real in P2.

## v0.12.0 — a project in any directory is read in place, never copied (change `any-directory`)

A target is now classified into three by probing — read and write
separately, through the gateway's own mount namespace, never by matching
a path against known prefixes. A **writable** target dispatches against
itself, as before. A **readable** one (the plane sees it but cannot
write it — anything under `/root` outside the two grants) is read where
it lives: the working directory becomes a scratch under the plane root,
the project is granted as an additional trusted location for reading by
absolute path, and the round's own artifacts are written in the scratch.
Nothing is written into the project — not even the gateway's bookkeeping
directories — and this is proven, not assumed: every round takes a
byte-for-byte manifest first (`plan.py snapshot`) and verifies it after
(`plan.py untouched`), a dispatch whose frames show a write inside the
project fails naming the path (exit 8), and a split dispatch that
grants only the scratch is refused before the client exists (exit 20,
"the client was never invoked"). When the round is done, `plan.py
return` copies exactly one thing back — the change directory — refuses
a return carrying anything else or gateway bookkeeping inside it, and
removes the scratch unless its retention is recorded with a reason. Only
an **invisible** target (under the private temporary namespace) is
copied, and the copy is the exception: staged under the plane root,
recorded with source, size, duration and revision, and stopped before
dispatch when it is not self-contained (a git worktree's `.git` pointing
outside the copy is the canonical case). Copying a readable target is
refused outright with the bytes the copy would have cost. Exit 6
(repo invisible) is retired. Widening the service unit remains no
remedy: `plan.py sandbox` reports every writable grant and flags one
that is a project tree rather than the runtime's own area, and a draft
unit that adds any writable path is refused (exit 21) with the split
workspace named as the remedy, nothing applied, nothing restarted.

## v0.11.0 — the findings are synthesised before the author answers them (change `review-synthesis`)

Between the reviewers and the revision, the caller (Claude Code)
synthesises the findings itself — zero sessions, zero dispatches: it
already holds the design and every finding, and a dispatch would
re-read in a cold session what it has in hand. `review/synthesis.md`
in the round's record groups the findings by where in the design each
lands, names every opposing pair with what one increases and the other
reduces (or states explicitly that none oppose — silence does not
stand in for that statement), and cites every concern to its finding.
Three contract checks keep it from becoming a fourth opinion: a
concern citing no finding, a filed finding in no group, or a passage
that recommends or ranks between findings fails the round (exit 18,
each breach named). `--stage synthesis` checks the file;
`--stage revision` re-judges it and then dispatches the author with
every finding in full, the synthesis alongside, and the answers owed
to the findings — a revision answering only the synthesis blocks as
unanswered (exit 19). The synthesis travels into `review_advice`
beside the findings, never a delivery criterion. Team mode is now
refused by reference to the measured record `docs/team-mode-record.md`
(leader-plus-teammates is structural — the runtime demotes anything
else and the loader completes the pair; a configured roster is unread
on the command-line path, proven by a 2,672-frame run with zero roster
hits; a completed team round ≈1,500 s against 174.3 s for the
equal-reviewer round; the leader blocks awaiting notification, it is
not idle) — refusing needs no new experiment unless a proposal names a
fact the record does not cover. The inert roster the experiment left
in the gateway configuration is removed, backup named in the record.
A roster role named for synthesis or leadership is refused — the
reviewers are equal by construction. Acceptance (S5): run on the V5
round's own three findings, the synthesis named unaided the opposing
pair the author had reconciled alone (containment that costs speed
against the objection to unbounded concurrency), plus the alignment
the hand reading never stated (lock and ceiling point the same way);
zero sessions opened. Evidence:
`.ai-dlc/tasks/review-synthesis-impl/evidence/s5-synthesis/`.

- **Executables** — `bin/plan.py` (synthesis stage + judge + gates,
  reserved roster roles, record-citing team refusal), `bin/report.py`
  (`review_advice.synthesis`).
- **Skill text** — `1b · REVIEW` section extended with the caller's
  synthesis step; version 0.11.
- **Docs** — `docs/team-mode-record.md` (new).
- **Test surface** — `tests/collapse/dr_review_round.sh`, 25 cases
  including every reverse case (uncited concern, unfiled citation,
  omitted finding, side-taking passage, silent no-pairs,
  one-directional pair, synthesis-only answers, synthesis/leader
  roster role, stage-all refusal to skip the caller's step).

## v0.10.0 — the design artifact gets adversarial review (change `design-review`)

After the design artifact stands, a bounded review round runs
(`plan.py review`): each reviewer holds one axis and one antagonistic
persona from `review:` in `config/collapsed.config.yaml` (seeded with
security / operability / performance — the three gaps the hand audit of
the route-and-speed design found), dispatched through the existing
per-role path, and files exactly one finding — a second finding, a write
outside its own path, or silence fails the dispatch (exit 18). The
author revises once, answering every finding on the record; an
unanswered finding blocks the phase from reporting complete (exit 19)
and never blocks delivery — the round travels into the delivery report
as `review_advice`, explicitly never a delivery criterion. Team mode is
refused with the three recorded reasons (no named reviewers on a
wildcard-matched team; an order of magnitude slower; progress invisible
until it ends). Acceptance (V5): the round run against the route-and-speed
design raised all three hand-found gaps — the security finding arrived
by a stronger route (grep-proven absence of any containment, not the
named permission-engine state), the operability finding went deeper than
the audit (`save_json` rewrites the whole file, so key-disjoint writers
destroy each other silently), the performance finding covered the
unnamed ceiling but not the gateway-degradation view. Evidence:
`.ai-dlc/tasks/design-review-impl/evidence/v5-round/`.

- **Skill text** — `1b · REVIEW` section added; version 0.10.
- **Test surface** — `tests/collapse/dr_review_round.sh`, 15 cases
  including every reverse case; `dt1_gates.sh` refreshed (it audited a
  hardcoded path with a v0.6-era subcommand surface — stale-red at base;
  it now audits the checkout it belongs to).

## v0.9.x — the plane opens, the boundary moves to inspection (change `open-plane`)

The permission engine's `enabled` switch is the one lever above the
tiered policy (`check_permission` core.py:161 short-circuits before
it); the earlier "no switch exists" conclusion measured the exempt
`_directly` helpers below it — corrected in place across the study,
the acceptance record and the runtime document. With the engine off
(the user's standing decision; scripted, idempotent, probed),
`./install.sh --provision-plane` owns the whole step and
`--doctor` reports the state and the cost. Roles stop being told the
shell is unavailable and fetch their own authoring guidance through
the CLI; the author-not-the-judge rule stops being a withheld
capability and becomes a checked one.

- **O1 provisioning (install.sh)** — new `--provision-plane`: back up
  config + unit (`.bak.pre-open-plane.<epoch>`), set the engine
  disabled in-place (other settings untouched), narrow the unit's
  `ReadWritePaths` to exactly the runtime dir + `<workspace-root>`
  (moving drop-ins aside), `daemon-reload` + restart, wait for the
  gateway, then a live probe through the shipped client — one command
  combining redirection + substitution + pipe carrying a probe-time
  random token; fail on a missing token or an interrupt frame. A
  second run reports no change and skips the restart; a gateway that
  does not return exits non-zero naming the backups. `--doctor`
  reports engine state, what being open removes (the built-in
  high-severity shell rules no longer ask; the systemd sandbox is the
  only remaining boundary), each writable path with its source, and
  any path beyond the project root as a named finding. Test hooks:
  `AI_DLC_GW_CONFIG/GW_UNIT/GW_SERVICE/AI_DLC_SKIP_RESTART`.
- **O2 roles reach openspec (bin/plan.py)** — the dispatch prompt no
  longer copies the authoring instruction/template/outputPath in and
  no longer carries the shell-unavailable / native-tools-only /
  compound-shape clauses; it instructs the role to run
  `openspec instructions <role> --change <id> --json` through the
  openspec-author skill, keeps the handoff package, artifact identity
  and write boundary, and carries the `OPENSPEC_CLI_UNAVAILABLE:`
  contract (a role that cannot run the CLI ends with the marker +
  its account; dispatch fails 15 carrying that account verbatim).
  Skill gate before any client call: openspec-author installed +
  registered, else exit 16 with the remedy. Prompt 4259 → 1446 bytes
  (−66%). `prompt_surface_audit` rejects the retired clauses (exit 17).
- **O3 the author is not the judge, checked** — the judge scans every
  dispatch's frames: a role invoking `openspec validate` fails the
  dispatch naming the invocation verbatim (13) and `accept` refuses
  that dispatch's artifact before validating (13); a command removing
  or rewriting a pre-dispatch baseline path fails naming command +
  path (14, generous capture — redirect targets and destructive-bin
  operands — decided against the baseline). Boundary check (8)
  unchanged and still aborting.
- **O4 corrections in place** — permission-matcher-repro.py gains the
  correction section (measured layer vs lever layer, both entries run
  with an in-memory `enabled: false`: allow vs ask) ahead of the
  unchanged original; acceptance-qualified.md's blockage account
  corrected again with a pointer to plane-runtime.md §3; §1/§3 of
  plane-runtime.md rewritten (the standing open state, its cost, the
  restore procedure; the closed-state account kept as superseded
  history).
- **O5 proof** — 18/18 suite green (`open_plane.sh` new: every
  reverse case above + provisioning backup/naming/idempotence +
  doctor findings); live e2e `e2e1` in <workspace-root>/open-plane-e2e:
  proposal + specs both dispatched through the shipped client, each
  round's frames show `skill_tool openspec-author` then
  `openspec instructions … --json` (and a compound `ls;echo|` command
  executing — the shape that interrupted five attempts in the closed
  runtime), zero validator invocations, boundaries clean,
  `openspec validate e2e1 --strict` rc 0 run by the caller. Evidence:
  `.ai-dlc/tasks/open-plane-impl/evidence/e2e1-live-run.md` + frames.

## v0.9.0 — the planning plane lands, the budget goes, the tail is wired (changes `devteam` + `landing`)

Upstream has no verification capability — every openspec subcommand
reads the spec tree, none opens an implementation. v0.8.0's oracle plane
(git-tagged rollback) was our substitute; this quarter deletes it rather
than keep a judgement no upstream capability backs. Delivery becomes:
head advanced ∧ product files landed ∧ `openspec validate --strict` rc 0
∧ cost green ∧ human merge approval with a rationale. Known consequence,
accepted: no machine judges artifact correctness; only a human reading
the deliverable catches a structurally broken one.

- **1.1 Deletions** — `git rm bin/oracle.py` (377 lines),
  `probes/oracle_benchmark.py` (70), `probes/benchmark_inline_reference.py`
  (92), dir emptied and removed; `tests/collapse/fixtures/broken-site/`
  (2 files, served the deleted checker tests). Rollback anchor verified:
  `git cat-file -e v0.8.0:bin/oracle.py`.
- **1.2/1.3 report.py surgery** — oracle.json read, exemption_list,
  oracle keys, `oracle_status`, G-ORACLE-1, and the WORKER_FAILURE gate
  type/stage removed; `init --change <id>` recorded as `change_id`;
  `deliver` runs `openspec validate <change> --strict` itself (cwd=repo,
  rc + full output captured, 60s timeout; no change id → spec_valid
  false, "no change id recorded"); failing validator output carried
  VERBATIM as `validator_output`; failure outcomes honestly derived in
  precedence spec_invalid → cost_over → merge_pending. Gate list
  everywhere: G-COST-1, G-COST-2, G-DELIVER-1, MERGE_GATE. E1 session
  guard, `session`, G-COST-2 grand totals, turn density, four states,
  MERGE_GATE, bill/cost kept.
- **1.5** — every delivery report carries `correctness`:
  `machine_checked: false`, the three criteria applied, and the plain
  sentence that no machine judges artifact correctness.
- **1.4 Suite** — 14 → 9 scripts, all green: 6 retired
  (m1_neg3_no_reconciliation, m2_neg_unverified, m3_neg1_sdd_propose_only,
  m3_neg2_worker_failure, glue_external_checkers, m3_pos1_zero_openspec —
  reconciliation/unverified/worker-gate concepts deleted;
  zero-openspec invariant inverted: validation is now the criterion);
  m1_positive rewritten to the new delivered path; m1_neg1 rewritten to
  the spec-invalid path (renamed m1_neg1_spec_invalid.sh); glue_surface
  re-audited (oracle plane absent, gates exactly 4); new dt1_gates.sh =
  task 1.6 as an executable audit; e2_neg's final oracle grep adjusted to
  the not-machine-checked marker (tasks.md 1.4: adjust tests referencing
  an oracle verdict).
- **Doctor/install** — the oracle self-test is gone (executable loop =
  bin/report.py only); a validate smoke asserts `--strict` discriminates
  (valid change passes, scenario-less requirement rc 1); headers and
  layout echoes updated; `gates.oracle_required` dropped from
  collapsed.config.yaml.
- Skills: ai-dlc v0.9 (discipline 1 = strict validation is the plan
  criterion, no machine checks the artifact; RECONCILE block and oracle
  kinds deleted; CHECK = validate + present the diff), ai-dlc-doctor
  v0.9, ai-dlc-swarm's oracle instruction corrected; `.claude/skills`
  regenerated via `./install.sh --target claude`.
- Executor bill and raw outputs: `evidence/v0.9.0-devteam/d1/`.

**devteam D2–D5 (the planning plane, change `devteam`):**

- **D2** — the retired-plane surface deleted (7 items): supervisor
  stage schemas, worker kinds and their wiring that no executable
  reads anymore.
- **D3** — `bin/plan.py`: roles/prompt/dispatch/boundary/accept. A
  behavior-only handoff package (strict schema), openspec's own
  authoring instructions embedded verbatim, one named session per
  role (`plan-<change>-<role>`), the boundary check (only
  `openspec/changes/<change>/` plus gateway bookkeeping), and the
  phase gate = `openspec validate --strict`'s own verdict.
- **D4** — `docs/plane-runtime.md`: the three measured permission
  layers, the service sandbox, the external-directory procedure, plus
  four reverse cases (invisible target, boundary violation, permission
  ask headless = interrupt, compound command vs the shell structure
  guard — measured live).
- **D5** — end-to-end on `<workspace-root>/e2e-devteam` (change
  `site-index`), including the frame proof that the JSONL stream is
  the round's real record. The task branch waited at its human merge
  gate until this release's close; verified against every task's own
  command (nav content, byte-identical idempotency, third-page
  add/remove cycle restoring committed bytes), then merged, archived
  (`2026-08-30-site-index`), worktree and branch removed.

**landing L1–L7 (change `landing`):**

- **L1** — the budget capability deleted outright: no code in this
  repo computes, caps, stops, warns or annotates on a token total;
  usage is read where upstream already records it.
- **L2** — the tail wired: `plan.py close` reads a merge-gate answer
  that must carry an approval **and** a rationale, merges the task
  branch, runs upstream `openspec archive`, records the close, and
  removes the worktree and branch (`--keep-task-branch` records
  retention instead).
- **L3** — resume instead of restart: done artifacts are skipped
  without a client call, `revision_pending` cancels the skip,
  deterministic session names make resumption the default.
- **L4** — the health check rewritten to what we still own:
  executables and gateway reachability (doctor 1-executable).
- **L5** — the qualified acceptance: a disposable `git clone --local`
  copy of a pre-existing repository (a CSV-parsing benchmark project,
  inline form, + its 11 untracked
  paths carried verbatim) ran the full path end to end. The specs
  role's opening compound `ls` command asked five times headless
  (interrupt, exit 7 — correct); the offline matcher reproduction
  proved every subcommand already matched a LOW allow rule and two
  code-level floors (shell-AST structure guard, operator escalation)
  override any rule shape. The human chose to open the permissions
  fully for the run; attempt 6 completed cleanly, design and tasks
  followed first-try, validation rc 0, implementation inline
  (`serialize_csv`, 24 tests, suite 85 passed), the gate was answered
  by explicit delegation, merged, archived, and disposed: permission
  window closed and verified three ways, copy deleted, source verified
  untouched. Record: `evidence/v0.9.0-landing/acceptance-qualified.md`.
- **L7** (user-authored group) — acceptance-target safety: dispatch
  admission refuses a target holding dependency source this project
  may never modify (exit 12, before the client, nothing recorded); a
  partial working-tree view waits for a human acceptance
  (`--accept-partial-view`); `plan.py sweep` removes what a run
  introduced, never a baseline path, retaining openspec/ for a person
  unless `--purge-openspec`; the earlier mis-targeted run is
  reclassified as a rehearsal with its deliverable handed over as a
  patch and both runtime openings revoked.
- **L6** — housekeeping: parked task records of retired stages
  preserved to `evidence/v0.9.0-landing/parked-task-records/` and
  removed; `devteam` archived through this change's own tail
  (`2026-08-30-devteam`, 17 requirements); `landing` archived the same
  way (`2026-08-30-landing`, 14 requirements). Suite 17/17 on the
  finished tree; doctor green. Tag `v0.9.0`.

## v0.8.0 — glue-only: external checkers replace self-written judgment (change `glue-only-architecture`)

The efficiency PRD protected oracle.py's 812 lines as "the judge". This
change measured the counterexample: `run_property`'s hand-written rules
scored a deliberately broken site **4/4 pass** while html-validate +
linkinator named every defect (both 404s, missing lang/title, stray end
tag). Judgment moves to tools we did not write; our code is glue — spawn,
read exit codes and JSON, tally.

- **G1**: `executor/openspec_gateway.py` (133 lines, zero code callers)
  deleted; ai-dlc-spec ×2 deleted — the spec surface is now what
  `openspec init --tools claude` installs (6 skills + 6 `opsx` commands,
  CLI-written, nothing hand-copied); ai-dlc-doctor 20 → 11 lines; attic/
  husks (28 orphaned .pyc + 1 stray file) removed.
- **G2**: oracle kind `external_checkers` — registered sets only
  (`web` = html-validate@11.10.0 `--formatter json` + linkinator@8.1.0
  `--format json`, both pinned). The runner records name/version/exit
  code/finding count per invocation and never opens an artifact. Checker
  unavailable → `unverified` rc 2, stop for the human.
  `run_property`/`PROPERTY_RULES` deleted from bin/oracle.py.
- **G3**: the frozen broken-site fixture goes RED with both unresolved
  links and the HTML errors named; the retired `html_document` rule
  demonstrably PASSED the same bytes — comparison recorded in
  `evidence/v0.8.0-glue/`. Suite 12 → 14, all green;
  `openspec validate glue-only-architecture --strict` rc 0.
- Two boundaries recorded: `openspec verify-change` is advisory, never a
  gate (it keyword-searches and prefers SUGGESTION over WARNING — the
  abolished D2-AUDIT shape); gentle-ai contributed nothing (its review
  "does not authorize, block, or govern delivery").

Executor: fresh-session worker (E1 discipline held — accumulated context
0 at start), **174 turns / 2.42M input-equivalent**; G-COST-1 fired at
the 800k main-control cap, total with dispatch+review rows 2,717,613.
Honest miss on the PRD's 提升效率 ask: the supervision line stayed solved
(~176k for two main-control turns) but the executor line quadrupled vs
the E1 run's 43 turns — 174 assistant messages for 84 tool uses. Turns
are budget; the next brief caps them explicitly. Human gates closed
2026-08-30: cap → 2.75M (add_budget, full 2,717,613 acknowledged), merge
approved (tag v0.8.0; change archived as 2026-08-30-glue-only-architecture
with specs synced into openspec/specs/).

## v0.7.0 — efficiency: session isolation, unhidable total, turn metric, pruned surface (efficiency PRD §5)

M1's real bill was 8,085,558 input-equivalent — 94.6% the supervision
session re-reading its own history. v0.7.0 removes that line and makes
the total impossible to scope away.

- **E1**: `report.py session` (accumulated-context measure) + `init
  --transcript` guard (over 50k → exit 18, refuse to host the task,
  demand a fresh session). **G-COST-2**: `grand_total_input_equivalent`
  over ALL ledger rows always prints beside the task scope, in `cost`
  and on the delivery report's first screen; `counted:false` moves a row
  between budgets, never out of existence. Acceptance re-run: the
  benchmark project in a fresh session, dispatched from a 97k/turn heavy session with the
  dispatch turn billed — total **519,076 ≤ 600,000** envelope (86% under
  M1), supervision line 7,650,832 → **97,374** (78×), oracle 25/25. The
  500k task cap breached by including the dispatch row → G-COST-1 fired
  live; the cap decision is open at a human gate.
- **E2**: turns billed from transcripts (`assistant_messages`);
  `turn_density = turns ÷ artifact KB` computed at deliver, red over 5.0
  with the fix note; three turn rules in the skill. Negative: fragmented
  12-turn/0.6-KB run → 19.69 RED. **Miss, stated**: the ≤15-turns target
  was calibrated against the wrong unit — the billable turn is the API
  call (43 measured, M1 47, −8.5%), not the executor's message batch
  (self-reported 14). Density 4.82 green but worse than M1's 3.73 (this
  run landed fewer bytes). The 150–200k extrapolation did not
  materialize; executor line is flat once the session is fresh.
- **E3**: 184 paths deleted (attic/ 169 — rollback is the verified tag
  `v0.5.1-delegated-final`; both ai-dlc-team dead-wiring trees; scripts/,
  probes/v1-3, targets ×3, versions.lock). Skills single-sourced
  (`supervisor/skills` tracked; `.claude/skills` install-generated).
  Skill markdown 50 KB double → 12,068 B single; ai-dlc-doctor rewritten
  to the 3 executables; judgment Python untouched by deletion. Acceptance:
  suite 12/12 verbatim; retired-name grep clean except the upstream
  constraint line; non-test active files 16.

Suite: 12 scripts (M1×4 + M2×1 + M3×4 + E×3), all green. Evidence:
`evidence/v0.7.0-efficiency/`.

Human gates closed 2026-08-29 (answers relayed through the supervision
session): E1 cap → 600,000 (`add_budget`, dispatch row stays counted);
MERGE_GATE approved for benchmark-e1 (7a2ad49, delivered) and M3 arm A
site-inline (5f1379b, delivered); narrow-worker dispatch stays
**OFF by default** on the cost-valve data.

## v0.6.0 — M3: skills on demand + the narrow-worker cost valve (collapse PRD §8)

Skills: `ai-dlc-swarm` added (thin dispatcher — one worker, brief written
by main control, verification stays with main control, failure → Needs
your decision, no re-dispatch); `ai-dlc-spec` rewritten against the real
openspec CLI 1.10.0 (the old text invoked nonexistent `explore`/`propose`
subcommands — the AI authors the markdown, the CLI validates) with an
ON-DEMAND-ONLY trigger. `report.py`: `--route sdd-proposed` stamps
PROPOSED/Needs-your-decision (no spec files, no openspec call, no work
until acceptance); `gate --type WORKER_FAILURE` escalates a failed
worker with options retry-once/take-inline/shrink-scope.

Acceptance: ① normal task end-to-end with a sentinel openspec on PATH →
call log empty, no spec tree (m3_pos1); ② 写规格 → `validate --strict`
green and a scenario-less spec rejected rc 1 (m3_pos2); negatives: 8-file
task → sdd-proposed propose-only (m3_neg1); worker failure → decision
gate, exactly 1 dispatch, no `openjiuwen` reference anywhere in the runtime
(m3_neg2). Suite: 9/9.

③ the cost valve, measured (evidence/v0.6.0-m3): same 8-file site intent,
two arms — inline 195,113 input-equiv · 443 s · 7/7 oracle · merge_pending;
one-narrow-worker 357,471 · 1,483 s · 0 files (worker timed out 2×600 s,
escalated per contract). Routing default (inline, worker OFF) confirmed
on this sample. The experiment doubles as the non-parsing second task the
standing single-sample caveat called for.

## v0.6.0 — M2: the tree pruned (collapse PRD §6)

The delegated orchestrator moved to `attic/` — 13 executor modules,
runtime/, skills-overlay/, vendor/, the installer scripts, the 70-key
config, demo fixtures, and the entire delegated test suite (13 files →
`attic/tests/`), each with its measured retirement reason in
`attic/README.md`. Nothing deleted; history intact; rollback anchor
stays `v0.5.1-delegated-final`.

What remains executes the collapse: `bin/oracle.py` + `bin/report.py`
(679 lines), `executor/openspec_gateway.py` (133 — ≤ 800 required),
`config/collapsed.config.yaml` (7 keys), skills ai-dlc / ai-dlc-spec /
ai-dlc-doctor / ai-dlc-team. Enforced gate IDs: **5** (G-ORACLE-1,
G-COST-1, G-DELIVER-1, MERGE_GATE, G-SPEC-on-demand; the extra IDs in
ai-dlc-team are the legacy matrix's descriptions, not runtime gates).

Acceptance held: all 5 `tests/collapse/` scripts re-run **verbatim** on
the pruned tree — positive + 3 M1 negatives + the unverified-stop
negative, all green. `install.sh` rewritten for the collapsed layout;
`--doctor` now self-tests the oracle both ways (reference → PASS, the
run3b mutation → RED) and the G-COST-1 block. README rewritten.

## v0.6.0 — M1: the collapse proves itself (collapse PRD ai-dlc-collapse-prd.html)

Baseline tagged `v0.5.1-delegated-final` (d0a4842); four-run evidence
archived to `evidence/four-run-baseline/` (4,963,611 input tokens, 0/4
correct deliveries, every number recomputed from the archived events).

**M1 delivered**: the benchmark project ran inline on the collapsed surface and
**delivered: true, Ready** — the first correct delivery in the
project's recorded history. Oracle 25/25 (0.005s); 4 files 12,889 B;
61 tests green; bill 32,038 cold + 402,688 cached + 21,732 out ≈
434,726 input-equiv, 548s wall — below every delegated run's input side
even counting cache 1:1. Evidence: `evidence/v0.6.0-m1/`.

New surface (~800 lines, replaces 9,670):
- `bin/oracle.py` — G-ORACLE-1 as delivery criterion; §3 pre-start
  conflict block (reconciliation.json, human adjudication, spec-authority
  exemptions reported in the deliverable); reference_module | property |
  existing_suite; nobody may author an oracle.
- `bin/report.py` — four-state human surface; G-COST-1 wired (breach →
  stop + decision gate; `counted:false` transparency rows); G-DELIVER-1
  from the real git diff; MERGE_GATE with rationale contract; the real
  bill from session transcripts (cold/cache/output separated).
- skill `ai-dlc` — routing table (inline default; ONE narrow worker at
  4+ files; SDD propose-only), behavior-not-shape task text, four
  states, hard prohibitions. `ai-dlc-team`'s matrix line reversed:
  writing code is the default; not writing it needs a reason.
- `config/collapsed.config.yaml` — 7 keys (was 70); openjiuwen dispatch
  OFF by default.

Negatives all red (suite `tests/collapse/`): run3b mutation → oracle
RED; over-cap → exit 17 + Needs-your-decision (also fired LIVE at 150k —
user re-scoped the task bill to the executor line, cap 500k); missing/
unadjudicated reconciliation → rc 3 blocked.

Honest boundaries: single sample (the benchmark project); executor model glm-5.3 vs
workers' glm-5.2 (disclosed); supervision context 7.65M recorded
uncounted per user decision.

## unreleased — S1+S6 (architecture analysis: external oracle + four-state human surface)

The architecture analysis (`ai-dlc-architecture-analysis.html`, "217")
opened with the measurement no internal gate could make: two
benchmark-project runs, same code/config/task, both `delivered:true`
with all 17 gates
green — and 3 and 4 stdlib-csv divergences respectively that a 30-second
external probe found (`probes/oracle_benchmark.py`; run2's severe one:
`ab"cd,e\n` → `[['abcd,e\n']]`, a row collapse). Every quality stage
closed on declarations this run's own workers wrote: developer docstrings
→ auditor extracts invariants from them → D3 patches gaps in the same
declarations → VERIFY runs tests written from them. Seven self-declared
gaps across both runs, zero real bugs caught. S1 breaks the loop; S6
shrinks the human surface to what a person can actually hold.

### S1 — G-ORACLE-1 (external criteria, leader-executed, zero MaaS)

- **Declaration gate** `_g_oracle_1` at D0: the plan must name a
  criteria source no worker in this run wrote — `reference_module`
  (stdlib adapter; today `csv` → `probes/oracle_benchmark.py`'s 25-case
  corpus; workers may propose case INPUTS, never expected values),
  `property` (leader-known rules: `exists_nonempty`, `html_document`),
  or `existing_suite` (must pre-exist in the base repo AND stay
  untouched this run). Red doesn't stop the run — delivery does.
- **Execution** `_run_oracle` at VERIFY, after G-NEG: deterministic
  subprocess/stdlib checks run by the leader, ~30s, ZERO extra MaaS
  calls. Verdict → `results/oracle.json` + `ORACLE_RUN` event.
- **Delivery wiring**: `delivered = head_advanced ∧ landed_files ∧
  oracle_pass`. No oracle → outcome `unverified`; oracle fail/error →
  `oracle_failed`. Invariant counts / gaps-patched are demoted to
  process metrics (they stay in the ledger; they are no longer quality
  signals).
- **Reverse case proven**: `tests/unit/test_oracle.py::ReverseReplay`
  replays the two archived runs' shipped modules against the probe —
  run1 RED (3/25), run2 RED (4/25, `field_with_quote_mid` named). Eval
  entries `oracle.benchmark-o1b` / `oracle.benchmark-o2a` pin both green
  histories as red (`oracle_status: absent`, `red_expected`). The gate
  that was green on both runs is red on both.

### S6 — the four-state human surface

- `state.json` carries `human_state` on every write, derived (never
  stored ahead): **Working** / **Checking** (VERIFY) / **Ready**
  (DONE ∧ oracle green ∧ nothing deferred) / **Needs your decision**
  (gate waiting, deferred lineages, failure, or unverified finish). The
  60 event types demote to the ledger.
- MERGE_GATE question body rebuilt (`_merge_gate_question`): ≤15 lines,
  oracle conclusion on line 1, up to 3 named divergences, one process
  line, deferred lineages if any. `write_gate_request` unchanged; the
  full summary payload remains the ledger.
- Stub planner declares a property oracle (html_document on the pages +
  exists_nonempty on the asset); hooks `AI_DLC_TEST_STUB_ORACLE=absent`
  (ships unverified) and `=fail` (declares a path nobody writes →
  oracle RED at VERIFY).

**Re-pins (behavior changes, pinned honestly):** lm-4/lm-5 — umbrella
runs that name their files never reach D0, declare no oracle, and now
finish `outcome=unverified, delivered:false` while their files still
land; lm-5 additionally asserts the ≤15-line UNVERIFIED gate question.
Suites: unit 141 (+37 `test_oracle.py`), lastmile 6, negative 8,
telemetry 5, concurrency 4, parallel 5, judge 9, skills 8, recovery 8,
evals 7/8 (`cliff.country-d-a3` red by design).

## v0.5.0 — 2026-08-28 (lastmile: delivery, sharding, deferral)

Milestones M1–M5 of the lastmile PRD (`ai-dlc-lastmile-prd.html`). The
premise retraction that opened it: workers wrote 57 files / 220,136 bytes
across three worktrees while the product repos received **0 bytes** —
five runs, four death modes, one shared root cause. The refit time model
(`duration ≈ sum_in/6257 + sum_out/39.4`, R²=0.986, decode 90%) closed
the caching line for good; everything below routes around openjiuwen's
hard 600s×2 ceiling instead of tuning it. openjiuwen, openspec/openjiuwen untouched (§9).

### M1 — the delivery plane (Q1 G-STAGE-1, Q4 ledger, G-DELIVER-1)

- **Stage commits**: the direct tier's only commit point used to sit
  after D3 (F4) — any earlier death left finished product as `??`
  untracked files. Every stage boundary now commits
  (`_stage_commit`), and **G-STAGE-1** judges both directions on
  `git status --porcelain` dirt: dirty tree must advance the branch,
  clean tree stays green. Mutation hook
  `AI_DLC_TEST_SKIP_STAGE_COMMIT=1` drives the red case.
- **G-DELIVER-1** — the only gate that would have judged all five 217
  runs red: success ⇒ repo HEAD ≠ base_sha AND ≥1 merged product file
  (orchestration plane excluded via `attribution.excluded_from_surface`).
  Judged on the target repo, not the worktree; mutation hook
  `AI_DLC_TEST_SKIP_MERGE=1` proves the reverse.
- **Q4 delivery ledger** on every terminal path — `results/delivery.json`
  + `DELIVERY_REPORT` event: landed files/bytes vs worktree files/bytes,
  deferred execs, timeout cliffs. A FAILED run now reports its untracked
  work as numbers instead of silence (the M0 rescue input).
- Gate-2 attribution rolls up by role without collapsing execs
  (`_role_attribution`) — keying by role silently kept only the last
  developer, a lie the moment D1 shards. `GATE_CHECK` events now carry
  their `gate` id (they were anonymous in the stream).

### M2 — telemetry escape fix (T4 + G-TEL-1)

- `normalize_session_text` restores the literal `\n`/`\t`/`\r` escapes
  BEFORE whitespace collapse: on disk a newline is two characters, so
  `\s+` never saw it and any goal key spanning a line break matched
  nothing (12 real execs, telemetry landed for exactly 1).
- **G-TEL-1**: coverage = execs-with-usage / execs-closed, floor 0.9
  (`telemetry.coverage_floor`); below → `TELEMETRY_COVERAGE_LOW` warn.
  Zero closed execs is not judged.

### M3 — judge grading + preload (Q2 G-JUDGE-1, T3, Q3)

- Absent or invalid manifest at gate-2 → **JUDGE_ABSENT, yellow**, with
  the banner 「本次无独立判题，判断仅基于 worker 自证」 — a scheduling
  loss is not a tautology (per001 died red at 18:37:50 with a valid
  manifest landing 358s later). Present-but-unkillable stays red;
  G-JUDGE-2 leakage unchanged.
- **T3 preload**: the judge window opens at D1 (direct) / S5 (full)
  with a `JUDGE_DUE` soft reminder — cases are authored while the
  pipeline works, not after the gate asks.
- **Q3**: the gate-2 summary carries `invariant_gaps{total,
  uncovered_in_audit_file, patched_by_d3, audit_present}` — the audit's
  open gaps on the second line, not buried in a worktree file.

### M4 — D1 sharding (T1 + G-TIMEOUT-1 + UMBRELLA_DISPATCH)

- **D0 blueprint**: when the task names no files, one small planner
  call writes `blueprint.json` (`{"files":[…]}`) — git-excluded and
  attribution-excluded, a planning artifact. Any failure falls back to
  the umbrella D1 **with a pre-dispatch `UMBRELLA_DISPATCH` warning**
  (R-3: never guess a split).
- **Sharded D1**: ≥ `workflow.d1_shard_min_files` (4) content files →
  disjoint shards in parallel workflow waves (G-PAR-1 judged per wave,
  G-SCOPE-enforced), then the pytest suite as a serial tail that
  observes the shards' output. Shard sizing and wave structure are
  Z2's budget packer — the first cut sharded by file count, which the
  playbook PRD retracted (see Z2).
- **G-TIMEOUT-1**: duration ∈ [570,600]s or attempts ≥ 2 →
  `TIMEOUT_CLIFF` event + delivery-ledger entry. country-a died at
  1200.224s; per001's 222 passing tests rode attempt 2 finishing 18s
  early — that shape is now a loud warning, never a silent success.

### M5 — non-blocking recovery (T2)

- `_recover_exec` waits at most `recovery.nonblocking_wait_seconds`
  (60) for an advisor plan, then **defers the exec** (`deferred_human`,
  `RECOVERY_DEFERRED` event) instead of raising. bra001 welded the line
  in place for 1,353s (33% of wall) and then discarded everything.
- Per-stage continuation semantics: D1 zero-files-plus-deferral = honest
  stop; deferred auditor → empty audit + `INVARIANT_AUDIT_ABSENT`;
  deferred tester → gaps stay open (`GAPS_UNPATCHED`), VERIFY judges
  the suite as-is; pipeline tiers (planning/IMPLEMENT) still fail
  honestly on artifact dependencies. Deferred execs ride the gate-2
  summary, the delivery ledger and summary.json.

### Z1 — telemetry correctness (playbook PRD: the triple-count)

- country-d attempt-1's three concurrent D1 shards each reported the sum
  of ALL four wave sessions while G-TEL-1 read coverage 8/8 = 1.00:
  sibling shard goals share task text + boilerplate and only diverge
  at the owned-file list, ~210 chars in — past the truncated
  120-char `goal_key`. Matching now uses the FULL normalized `## Task`
  segment (`goal_probe`); the truncated key remains for display only.
- `normalize_session_text` restores `\uXXXX` escapes too (json.dumps
  writes the shard boilerplate's em-dash escaped — a full-segment
  probe would otherwise miss every shard session).
- **G-TEL-2**: no two execs may report an identical telemetry session
  set (`session_collisions`). Red is a run-stopping `PipelineError` —
  fictional usage must not survive to the ledger. G-TEL-1 asks "is
  there a number"; G-TEL-2 asks "is the number right".
- `tests/telemetry/run-telemetry.sh` rewritten 5-scenario: two-launch
  discovery (real goals from the wave manifest + serial briefs, one
  session per goal, per-goal sums reconcile), absent-dir honest zeros,
  one-session-two-goals collision → G-TEL-2 red + FAILED, archived-
  country-d replay (history stays red), and re-collection of the real
  attempt-1 sessions: 3 wave execs over 4 disjoint sessions,
  Σsum_out = 48,004 reconciles exactly.

### Z2 — the right sharding axis (playbook PRD: price output, not files)

- The retraction: D1_SHARDED claimed each shard was "sized away from
  the 600s cliff" while sharding by FILE COUNT. Measured reality: a
  single attempt tops out at ~20,334 out-tokens (~36 tok/s under the
  600s wall) and exploration multiplies final content ~5× — country-d's
  shard 1 held 8 HTML pages + 4 SVGs, died at exactly 1200.2s.
- **D0 four-piece plan**: the planner brief now demands
  `files[{path, est_out_tokens, depends_on}]` + `order` +
  `risks[{what, mitigate}]` + `proof`, with est_out_tokens = predicted
  TOTAL output including exploration (~`workflow.exploration_factor`
  × final content size; the brief tells the planner the multiplier).
- **G-PLAN-1**: a size-less blueprint (the legacy string array) is
  REJECTED — verdict red, no D1_SHARDED, no workflow wave; the run
  falls back to a visible UMBRELLA_DISPATCH carrying the gate's
  problems (the legacy names still scope the umbrella). File-count
  sharding is never silently performed. Red does not stop the run —
  the loud fallback is the designed path. Task-marker file lists (no
  D0 ran) get the same refusal: no sizes, no sharding.
- **Budget packer**: `_pack_shards` bin-packs plan entries in plan
  order against `workflow.shard_out_token_budget` (12,000 ≈ 60% of
  the measured single-attempt ceiling); an entry priced above the
  budget becomes a flagged singleton. **Waves**: `_shard_waves` builds
  dependency barriers (a shard whose files depend_on another shard's
  files waits) — each wave is its OWN workflow invocation
  (`wf-D1`, `wf-D1-w2`, …); a cycle collapses to one wave with deps
  ignored and a warning, never a dispatch-time deadlock.
- **Tests are priced too**: the serial single-file tests tail clifed
  at exactly 1200s on country-d attempts 1 AND 2 (and the D3 patcher
  inherited the whole suite and clifed with it). The planner brief now
  asks for the suite as one or more `tests/` files each with its own
  est; a multi-file suite dispatches as a PARALLEL wave of disjoint
  test writers (`D1_TESTS_WAVE`, `_d1_tests_file_goal` — no
  conftest.py, observe-don't-invent, write-early) after every content
  wave; a single-file suite keeps the serial tail, its est on record.
- **D1_SHARDED event** now carries `waves`, `budget`, `est_total`,
  `shard_ests`, `oversize`, `notes` — the note states what was actually
  done (budget-packed ≤ N), not a comfort claim.
- **est-vs-actual**: every budgeted exec (shards + the tests tail, the
  tail priced from the plan's tests/* ests) records its est at
  EXECUTOR_STARTED and lands in `results/delivery.json.est_vs_actual`
  with telemetry's sum_out and the signed error — the
  exploration_factor's recalibration input. A missing session reports
  `actual: null`, never a −100% fiction.
- Config: `workflow.shard_out_token_budget: 12000`,
  `workflow.exploration_factor: 5.0` (defaults AND shipped yaml in
  sync). Stub openjiuwen writes the four-piece plan (4×4,000 + tests
  1,900 → 2 shards, one wave); `AI_DLC_TEST_STUB_BLUEPRINT=legacy`
  writes the v0.5.0 string array for G-PLAN-1's rejection case.

### Tests

- New: `tests/unit/test_lastmile.py` (10 units — escape, cliff math,
  coverage, stage/delivery verdicts on scratch repos),
  `tests/lastmile/run-lastmile.sh` (5 scenarios: sharding e2e,
  G-STAGE-1 red + failure ledger, G-DELIVER-1 red, cliff replay,
  M5 deferral ≤1s with JUDGE_ABSENT banner).
- Stub openjiuwen: `blueprint.json` branch, worktree product-file walk
  (the tests tail observes the shards), cwd-keyed parse-error marker
  (the old brief-path key collided across tasks at the ai-dlc root),
  `AI_DLC_TEST_STUB_CLIFF` / `AI_DLC_TEST_STUB_FAIL_ONCE` hooks.
- Stub workflow: parse-error `once` arms only item 0 (thread-race
  determinism). Telemetry fixture carries all four D1-family goal
  continuations. Judge suite `jmissing` expects `JUDGE_ABSENT`.
- Z1/Z2 additions: `tests/unit/test_plan_sharding.py` (12 units —
  packer, waves, G-PLAN-1 verdicts, est-vs-actual rows),
  `tests/telemetry/run-telemetry.sh` 5 scenarios, lastmile lm-6
  (legacy rejection e2e) + lm-1 strengthened for the budget fields.
- Z5 additions: `tests/unit/test_z5.py` (10 units — G-FIX-1 both
  directions, repo-notes prepend + one-page cap, leading indicators),
  negative `gfix1` (weakened-oracle fixer must die at G-FIX-1).

### Z5 — hooks, persistent CLAUDE.md, leading indicators (playbook P3–P5)

- **G-FIX-1** (`_g_fix_1`, called in `_fix_round`): a fix window must
  not weaken the oracle. Existing `tests/**` content changes, ANY
  `vendor/**` change, and test deletions inside a FIX window are gate
  red (`GATE_CHECK` + `GATE_FAILED` + run dead). New test files stay
  green — adding coverage is the opposite of weakening — and the D3
  tester is exempt (writing tests is its job; its brief already
  polices invented asserts). Mutation proof: `gfix1` in the negative
  suite (stub fixer "fixes" a finding by appending to an existing
  `tests/test_*.py` → G-FIX-1 red, state FAILED).
- **P4 persistent CLAUDE.md**: `ContextStore.render_digest` now
  prepends the repo-root `CLAUDE.md` (one page, 2 KiB cap) as a REPO
  NOTES section. `project()` overwrites the worktree `CLAUDE.md` with
  the digest, so without the prepend the repo's own conventions were
  silently lost exactly where the worker reads. Truncation order:
  ledger → instruction → repo notes → intent.
- **P5 leading indicators** (`_leading_indicators` in
  `_delivery_report`): `plan_to_dispatch_s`, `est_bias` (mean
  est_error — a systematically positive bias means the exploration
  factor under-prices content), `cliff_proximity` (shards whose
  ACTUAL out-tokens crossed the packing budget), invariant totals +
  audit gaps, first verify verdict — recomputed from `events.jsonl`,
  a pure function of recorded history.

Suites after Z1–Z5: unit 75 · lastmile 6 · recovery 8 · concurrency 4 ·
telemetry 5 · parallel 5 · judge 9 · negative 8 · skills 8 — all green,
plus the Z3 eval suite (`tests/eval/run-evals.sh`, 4 replay green +
2 adopt on the live acceptance run) behind `scripts/eval-guard.sh`
(G-EVAL-1).

### Z2b — pricing the tests plane (what attempt-3's cliffs bought)

Attempt-3 (b3f7a2) DELIVERED — 17 files, 400,284 bytes, every gate
green including G-DELIVER-1 and a live-proven G-TEL-2 — but all four
TIMEOUT_CLIFFs lived in the tests plane while the impl waves ran
cliff-free: the est model priced test files with the content factor
(5×) although a suite's writer also RUNS the suite (pytest output is
out-tokens; measured est 4k → actual 33.9k, est 9.5k → 30.6k, overall
est_bias +0.954), and D3 sent ONE tester over 25 invariant gaps.

- `workflow.tests_exploration_factor: 8.0` — the planner brief now
  carries a separate tests multiplier and demands small focused suites,
  each under the shard budget on its own.
- **G-PLAN-1** additionally rejects a tests file priced over the
  budget ("plan smaller focused suites") — a singleton shard cannot
  save a test file that cannot fit one 600s attempt.
- **D3 gap sharding** (`_d3_patch_sharded`): > `d3_gap_shard_max` (8)
  gaps fan out like the D1 tests wave — one tester per slice, each
  owning EXACTLY `tests/test_gaps_<n>.py` (disjoint by construction,
  write-early + observe-don't-invent constraints). Small gap sets keep
  the original single-tester path (`_d3_patch_single`).
- Units: `tests/unit/test_z2b.py` (6 — G-PLAN-1 tests-oversize both
  directions, content-oversize stays the packer's warning, goal pins
  filenames + carries gap ids, chunk math). Suites: unit 81, rest
  unchanged, all green.

### Z2c — the tests plane's death mode is exploration, not writing

Attempt-4 (z2bacc, 03:22) DELIVERED — 16 files / 298,942 B, every gate
green, ZERO impl cliffs (est errors −3%…−25%) — but the tests plane
cliffed again and took the D2 auditor with it (read 13 files + the
suite, died at exactly +1200s). The natural experiment inside the run
pins the lever: the structure writer that SAMPLED two pages and wrote
a skeleton first delivered in 8 minutes; the conftest writer that read
everything burned 30,305 out-tokens with zero writes.

- `workflow.tests_one_per_shard: true` — one writer per test file;
  attempt-4's BOTH paired tests shards clifed while the single-file
  recovery children survived (`_pack_shards(one_per_shard=…)`).
- **ORDER OF WORK discipline** in every tests-plane/auditor goal
  (`tests_sample_files: 3`, `tests_max_pytest_runs: 2`,
  `audit_sample_files: 3`): read at most N impl files end-to-end,
  write the skeleton ON DISK within the first few minutes, refine
  after; pytest -k to select your own tests; `--collect-only`
  preferred over full runs for the auditor.
- **`INVARIANT_AUDIT.absent`** — a deferred auditor left gaps=0 that
  read like a clean audit; the event, `delivery.json
  .invariant_audit_absent`, and leading indicators (`audit_absent`)
  now carry the difference explicitly. T2's "run on, record the
  absence" design stands — the flag makes the absence machine-readable.
- Units: `tests/unit/test_z2c.py` (9 — one-per-shard packing both
  directions, order-of-work needles in all three goal builders, the
  absent flag through event/report/indicators). The two pre-existing
  `_delivery_report` fixtures gained `_audit_absent = False` (they
  enumerate exactly what the report reads). Suites: unit 90, rest
  unchanged, all green.

**Unvalidated on a live run** — these knobs landed at 03:30, after
attempt-4 closed at 03:22. The stop-restart PRD (`ai-dlc-stop-restart
-prd.html`) froze this state as the commit/rollback point and replaces
the knob-stacking direction with the structural fix (tests co-sharded
with their content, O1–O3) validated once on the benchmark project (A1–A5).

## stop-restart (2026-08-29): the structural fix, not another knob

The PRD's diagnosis: bin packing WORKS on the impl plane (attempt-3's
11 content shards: 7.6k–14.3k actual, zero cliffs two runs straight)
while all seven cliffs across attempts 3–4 live on the tests/audit
planes, each 2–3× over budget — because a test writer's cost is
READING the product and running the suite, both proportional to the
whole site. `tests_one_per_shard` cannot cure that: splitting test
files copies the reading cost N times (attempt-3 measured it — a
clifed D3 writer auto-split, BOTH children clifed). The fix is
ownership.

### O1 — tests co-sharded with their content (G-PLAN-2)

- Plan format: every content entry carries `test` +
  `test_est_out_tokens`; the pair is ONE priced entry (`price` =
  est + test_est) and the packer never separates it. A co-located
  test prices ~1–2k net (nothing to re-read), NOT the 8× tests
  factor — that factor now prices only the integration suite.
- **G-PLAN-2** rejects (with the same loud umbrella fallback as
  G-PLAN-1): content entries without test paths, > `integration_tests_max`
  standalone tests/ entries, shared test ownership, and pairs priced
  over budget — the message says SPLIT THE PAGE'S CONTENT, never
  strip the test. Both PRD reverse cases are unit-proved (the
  4-standalone-entries plan and the unpaired plan).
- Shard goals: write the file, then IMMEDIATELY its test; do NOT run
  the whole pytest suite (siblings don't exist yet — the run is
  impossible by construction, which is the point); cross-file
  behaviour belongs to the integration writer.
- `shard_out_token_budget` 12,000 → **14,000** (R-3: page+test pairs
  reach ~17k; 12k left 15% headroom under the 20,334 ceiling).
- `colocated_tests: false` restores the legacy tests wave wholesale.

### O2 — one integration suite as the serial tail

At most ONE standalone tests/ entry (G-PLAN-2 enforced), dispatched
serially after every content wave (`D1_INTEGRATION_TAIL`): the only
writer allowed to read the whole product and run pytest
(`tests_max_pytest_runs` is its knob). Cross-file assertions only —
per-file behaviour already has its per-file tests.

### O3 — the D2 auditor reads declarations, not the product

The audit input is the INV-NN docstrings O1's shard goals mandate,
plus the plan. The auditor consolidates declarations, verifies a
≤ `audit_sample_files` sample, and ADDS undeclared invariants — the
model call STAYS (country-e's I33 was auditor-invented; a parser can
never find that class). Attempt-4's auditor died reading 13 files +
the suite at exactly +1200s.

### G-READ-1 — the exploration-burn alarm

Any exec with `sum_out > exploration_burn_out_tokens` (15,000) and
ZERO attributed files emits `EXPLORATION_BURN` and lands in the
delivery ledger + leading indicators — the "read 18 minutes, wrote
0 bytes, returned success" shape that booked as a normal success.
`_detect_exploration_burns` is pure over the event stream, so
leading indicators REPLAY history: pre-G-READ-1 archives surface as
`exploration_burns_missed` (attempt-3's 30,583-token/0-write exec
reads there — the PRD's reverse case). `_watch_exec` runs both
watchers (G-TIMEOUT-1 + G-READ-1) over every closed exec.

Units: `tests/unit/test_stoprestart.py` (14 — G-PLAN-2 accept + both
PRD reverse cases + over-budget/ownership/colocated-off, both goal
builders, G-READ-1 replay/live/ledger). lastmile lm-1 re-pinned to
the O1 shape (colocated_tests, D1_INTEGRATION_TAIL, no tests wave,
budget 14,000, est rows = shards + 1). Suites: unit 104 · lastmile 6
· telemetry 5 · concurrency 4 · parallel 5 · judge 9 · skills 8 ·
recovery 8 · negative 8 · eval 5/6 (cliff.country-d-a3 RED — the
discriminating eval, unfixed by design).

## v0.4.1 — 2026-08-28 (time model, concurrency unlock, vendored skills)

Milestones N0–N5 of the skills PRD (`ai-dlc-skills-prd.html`). The PRD's
§7 time model — `duration ≈ sum_in/2925 + sum_out/41` (R²=0.964, n=67),
decode at 41 tok/s dominating, 89% of output being tool args — sets the
axis: round count and serialized dispatch are where the time goes, so
that is what the gates now measure.

### N0 — telemetry first (`executor/telemetry.py`, T4 + G-TEL-1)

- Every `EXECUTOR_COMPLETED` carries `telemetry{sum_in,sum_out,turns,
  cache_read}` read from the worker's own session logs
  (`~/.claude-maas/projects/<encoded-worktree>/*.jsonl`). **One assistant
  message = several streaming records each with usage → dedup by
  message.id, keep the LAST per id** (naive summation inflates 4–5×;
  after the fix the 67-session population reproduces §7 exactly: 41 tok/s,
  median sum_out 2,909, cache zero 67/67 — `evidence/v0.4.1-e2e/
  telemetry-fit.txt`).
- Missing session → `telemetry{missing:true, zeros}` + `TELEMETRY_MISSING`
  event. Never a silent 0 (G-TEL-1 negative).

### N1 — concurrency unlock (P1 + P2 + G-PAR-1)

- **P1**: the planner goal demands `files:` markers per task item;
  marker-less items are predicted pre-gate-1 (`TASK_SCOPE_FALLBACK_
  PREDICTED`), listed as `serial_fallback_items` in the gate-1 summary,
  and IMPLEMENT degrades to serial dispatch — visibly, never guessed.
- **P2**: reviewer round 1 reviews the full diff; rounds r≥2 review only
  the previous findings + the files changed since (symmetric-diff snapshot
  around the fixer window).
- **G-PAR-1**: at every multi-item dispatch close, Σ per-item `duration_s`
  (executor-reported, one monotonic clock) / stage wall ≥ 1.5. Event
  timestamps are deliberately NOT the source — a workflow wave stamps
  every STARTED at dispatch and every COMPLETED at result-processing, so
  event-stamp "durations" always read n×wall and would call a serialized
  wave parallel: exactly the illusion this gate dispels. Measured:
  IMPLEMENT 1.97× at concurrency 3; 0.99× → red at concurrency 1.

### N2 — vendor + overlay + installer (G-VND-1/2, G-SKILL-1)

- `vendor/matt-pocock-skills/` — five skills + LICENSE pinned at
  `6654f6b…`, fetched by SHA from codeload, 11 sha256s in `UPSTREAM.lock`
  (`scripts/vendor-sync.sh`, `--verify` = G-VND-1).
- `skills-overlay/` — 15 `O-XXX-N` clauses (4 tdd, 4 firefighter, 4 audit,
  3 writing), each ledgered in `OVERLAY.md` with its why (G-VND-2 checks
  markers ⇄ entries 1:1). Upstream bodies are never edited; the installed
  `SKILL.md` = HEAD.md + separator + verbatim upstream, with the upstream
  text contiguous and byte-comparable inside the merge.
- `scripts/install-skills.sh` — installs workers (`ai-dlc-tdd`,
  `ai-dlc-audit`) to `~/.claude-maas/skills/` and supervisor
  (`ai-dlc-tdd`, `ai-dlc-firefighter`, `ai-dlc-writing`) to
  `<repo>/.claude/skills/`; a worktree destination is REFUSED (attribution
  window). ECHO = sha256(merged body)[:8] embedded as the file's last
  line; `--check` re-derives it (G-SKILL-1). `install.sh --skills` runs
  the chain; doctor gained the three checks. `versions.lock` records the
  new policy: published packages are consumed as packages; unpackageable
  text we must rewrite goes vendor + overlay, verifiable by construction.

### N3+N4 — supervisor wiring (W1/W2/P3) + G-FIRE-4

- `judge/request.json` now names `authoring_skill: ai-dlc-tdd` and carries
  `rules` — the upstream "independent source of truth" line quoted
  verbatim plus the kill_probe demand (W1).
- `recovery/<exec_id>.request.json` — symmetric with the judge window:
  authoring skill, original scope, failed status, required fields (W2).
- The supervisor skill documents the overlap timing: NEED_JUDGE → start
  authoring immediately (due-by is gate-2, not start-by); NEED_RECOVERY →
  the request file is the advisor's machine-readable brief (P3).
- **G-FIRE-4**: with `recovery.require_evidence: true` (default false),
  a plan must carry non-empty `repro_command`/`repro_output` and ≥3
  hypotheses each with a prediction, checked after action validity and
  before the G-FIRE-1 rails. A diagnosis-only plan → `RECOVERY_NO_EVIDENCE`
  + forced human escalation.

### N5 — efficiency wording in goals (T1–T3 + positive constraints)

- `compose_goal(method=…)` renders a `## Method` section before
  `## Constraints`: targeted-edit-first (developer/fixer), review-delta-
  only (reviewer), ≤200-word final reply (all). The REPLY PROTOCOL
  preamble is untouched — G-CTX proved this exact wording.
- Every shipped constraint now states the write scope positively
  ("implementation files are read-only inputs you verify") instead of
  prohibitions; zero `Never …` texts remain (O-WRIT-2).
- `workflow.method_lines: false` is the rollback switch pending the N6
  A/B; skill naming in goals stays off until `skills.worker_enabled`.

### Fixed

- **config_loader `_coerce`**: inline comments were stripped AFTER boolean
  coercion, so every commented boolean in the shipped config (`false  #
  why`) loaded as the truthy STRING 'false'. `require_evidence: false`
  silently enabled G-FIRE-4 everywhere. Comments now strip first.
- Stub `workflow` now honors manifest concurrency (real ThreadPoolExecutor
  semantics) and both stubs self-report `duration_s` like the real pair.

### Tests (all green)

unit 41 · parallel 5 · negative 7 · judge 9 · recovery 8 · concurrency 4 ·
telemetry 2 · skills 8. Deferred: N6 worker-skill A/B (needs real MaaS
runs), N7 git guardrail hook (optional).

## v0.4.0 — 2026-08-28 (advisor planes: P0 concurrency, judge, fire-fighter)

Milestones M1–M3 of the advisor PRD (四面分工). Claude Code joins the
pipeline on three new planes — none of them carrying approval authority
(A0: only a human `gates/gate-N.answer.json` passes a gate). M4–M7
(R0 advisor base, R3 planner tier, skill commands, real-run tuning)
are deferred.

### M1 — P0 concurrency protection (`executor/run_lock.py`)

The 2026-08-28 tourism incident (four concurrent launches of one task_id,
four events.jsonl writers, a zombie TASK_FAILED 16 minutes post-mortem)
is now structurally impossible:

- `run.lock` acquired `O_CREAT|O_EXCL` (pid) **before the first byte** a
  launch writes into the task dir. Second launch of a live task → exit 2,
  zero writes. Dead holder → reclaimed with `STALE_LOCK_RECLAIMED` as
  event #1.
- **P0-2 orphan guard**: after every worker wait the bridge re-checks
  ownership. Lost lock → `OrphanExit` (rc 3): envelope parked at
  `result.orphan.json`, no state/event writes, no poisoned FAILED verdict.
- **P0-3**: `seq` strict monotonicity asserted before DONE is claimed.
- `tests/concurrency/run-concurrency.sh` — 4 scenarios, incl. a stub hook
  that steals the lock mid-dispatch.

### M2 — R1 judge 出题人 (`executor/judge_runner.py`)

Independent pytest cases authored by Claude Code, run mechanically by the
leader at gate-2:

- Judge dir `.ai-dlc/tasks/<id>/judge/` — physically outside the worktree
  (path isolation, honestly disclosed as not a sandbox). Window opens
  `NEED_JUDGE` (non-blocking): direct tier before D1, pipeline after
  gate-1 (spec frozen). The request file carries the exact
  `source_sha` template the manifest must echo.
- `judge.manifest.json`: case ledger (`id`/`asserts`/`from`/`test`) +
  `kill_probe` (`file`/`find`/`replace`). Suite runs in a throwaway temp
  dir with `cwd=<worktree>` — judge never enters the attribution window.
- **Presentation**: JUDGE_CAUGHT (worker green, judge red) rides FIRST in
  the gate-2 summary with failing ids + asserts; AGREE_PASS labelled the
  weak signal it is; JUDGE_MISSING visible, never silent.
- **G-JUDGE-1** (lethality): the kill probe is applied to a temp copy;
  zero catches = tautology = red. Missing/unapplicable probe = red.
  **G-JUDGE-2** (isolation): case text grepped against the worktree
  CLAUDE.md + every brief goal (task-quoted text excluded as public).
  **G-JUDGE-3** (A0): an all-red judge still passes with a human approval —
  proven, not assumed.
- `source_sha` staleness: `JUDGE_STALE` on drift, warn (default) or block
  per config; tasks.md checkbox reconciliation is normalized out.
- `tests/judge/run-judge.sh` — 8 scenarios (agree/caught/taut/leak/
  stale-warn/stale-block/full-tier fingerprints/missing).

### M3 — R2 fire-fighter 救火员

Worker failure is a recovery input, not a death sentence:

- `NEED_RECOVERY` (exec, status, original scope) → advisor writes
  `recovery/<exec_id>.plan.json` (`redispatch|split|escalate` + diagnosis
  + goal_patch). Leader applies the §6.3 decision table mechanically.
- **G-FIRE-1**: plan scope must be a subset of the original window
  (umbrella/dir semantics via `attribution.path_in_scope`) — else
  `RECOVERY_SCOPE_EXPANDED` and forced escalation.
- **G-FIRE-2**: `recovery.redispatch_limit` (default 2) per failure
  lineage → `RECOVERY_EXHAUSTED` → human.
- **G-FIRE-3**: zero claude-code product bytes — plans under `.ai-dlc/`,
  replacement work dispatched to fresh worker execs (lineage-linked;
  downstream attribution resolves lineage).
- Acceptance replay: the real parse_error death (openjiuwen stdout not
  JSON) now recovers and completes (`fparse`).
- `tests/recovery/run-recovery.sh` — 5 scenarios +
  `tests/recovery/plan_answerer.py` (plays the advisor).

### Config

```yaml
judge:
  enabled: true            # window + gate-2 run
  run_at: gate-2
  blocking: false          # A0 — the judge never gates progress
  isolation_check: true    # G-JUDGE-2
  stale_source_policy: warn
  run_timeout_seconds: 300
recovery:
  advisor_enabled: true    # worker non-success → NEED_RECOVERY flow
  redispatch_limit: 2
  plan_timeout_seconds: 600
```

### Found in flight (fixed same session)

1. Tasks.md checkbox flips after judging read as spec drift → normalized
   out of the specs fingerprint.
2. Recovery execs' attribution invisible to D2/VERIFY-D consumers
   (they looked up the original exec only) → `_lineage_files()`.
3. Escalate plans fell into the split validator ("split plan has no
   items") → decision-table ordering fixed.
4. The stub's parse-error marker lived in the worktree → tripped G-SCOPE;
   moved to the task root.

## v0.3.0 — 2026-08-28 (quality & efficiency: triage, invariant channel)

M1 of the 质量/效率 PRD. The pipeline now decides how much process a task
deserves before spending a single MaaS call, and the test discipline it
enforces is checked mechanically instead of hoped for.

### S0 task triage (R1) — `executor/triage.py`

- Deterministic scoring (0 MaaS calls): multi-file +2, cross-cutting/security
  keywords +2/+1, explicit audit/compliance demand +3, brownfield +1, long
  task text +1. Thresholds configurable (`triage:` section).
- Three tiers: **direct** (developer + auditor, 2–3 calls, single G-NEG gate),
  **lean**, **full** (unchanged v0.2.0 pipeline). Verdict lands in
  `triage.json` with score/signals/reasons for复盘; `TRIAGE_DECIDED` event.
- `--profile direct|lean|full` beats the verdict and says so in the reasons
  (`OVERRIDE: …`) — the escape hatch is itself auditable.

### Direct tier (R1) — the 15-minute path

- D1 developer (scope from files named in the task, must deliver impl +
  pytest + docstring invariants) → D2 auditor (`audits/invariants.json`,
  machine-checked `{"id","statement","source","covered_by"}` array) →
  D3 tester **only** if the audit reports an uncovered invariant.
- VERIFY-D: pytest green + G-NEG mutation check + leader-gap check; one gate
  stop (gate 2), then merge. Minimal event log incl. `INVARIANT_AUDIT`.
- `audits/**` excluded from the product surface (process artifact, like
  `findings.json`), in attribution + context projection + config.

### Scenario↔test matrix (R3) — G-SCN, the seventh gate

- Pipeline tester briefs mandate `# scenario: <name>` markers on every test.
- At S5 the matrix maps spec scenarios (openspec `#### Scenario:`) to markers
  (case/whitespace-forgiving). Gaps → ONE tester re-dispatch with the gap
  list, then red: `GATE_FAILED gate=G-SCN`. Rechecked at VERIFY.
- Fights the v0.2.0 experiment's failure mode: the B-arm bug was an invariant
  written in a docstring but never tested; the matrix makes coverage of
  *spec scenarios* mechanically checkable.

### Test & evidence

- `tests/unit/` (13): triage routing/override/serialization (AC1, AC8①),
  matrix green/red/forgiving/empty (AC8③).
- Stub openjiuwen hooks: `MATRIX_GAP`, `INVARIANT_GAP`; trivial-tests mutation
  keeps its scenario marker so G-NEG stays isolated from G-SCN.
- Negative suite 7/7 RED-as-expected (glead/gscope/gctx/gneg/gspec/gscn/grole);
  delete-module 4/4 wired; direct/full/D3-patch stub e2e green.
- Real-MaaS csv benchmark + judge rubric archived under `evidence/v0.3.0-e2e/`.

## v0.2.0 — 2026-08-27 (pipeline rebuild)

Roles are now derived from the schema, the leader provably writes nothing, and
context reaches workers through the only channel that works. Delivered against
the AI-DLC 流水线重构 PRD (hard constraint: zero changes to openspec /
openjiuwen sources; new code only in `ai-dlc/executor/` and
`.claude/skills/`).

### Wiring defects fixed (E1–E7, see `tests/wiring-audit.sh`)

- **E1 spec role was fake** — hardcoded templates, no openspec calls. Now the
  four planning roles (analyst / requirements / architect / planner) each own
  exactly one openspec artifact, driven by `openspec instructions`; per-wave
  exit is `openspec` judging the artifact done.
- **E2 workflow fanout was dead code** — never invoked outside its definition.
  Now every multi-item wave (S2, IMPLEMENT, S5) fans out through the real
  `workflow` with disjoint-scope pre-checks; 4 live call sites.
- **E3 no worktree** — roles ran in the main workspace. Now every task gets
  `<repo.parent>/wt/<task_id>` on branch `change/<task_id>`, merged back at S8.
- **E4 fields dropped by openjiuwen** — permanent upstream constraint (goal-only
  stdin channel). Worked around by goal-inlining (`compose_goal`) + the
  CLAUDE.md projection; documented, not "fixed". Also discovered live: the real
  openjiuwen rejects unknown brief fields (`invalid_brief: unexpected field`) —
  briefs now carry exactly the eight schema fields, and `item_id` never enters
  a direct openjiuwen brief.
- **E5 AC17 was tautological** — leader bytes were counted by the leader.
  Replaced by hash-snapshot attribution (`attribution.py`): product-surface
  snapshots at every window boundary, `leader_authored_bytes` provably 0,
  registered allowlist (openspec archive, tasks.md checkbox reconciliation)
  logged as `LEADER_REGISTERED_WRITE`, never silent.
- **E6 AC18 counted ghost roles** — role count now derives from the attribution
  table only (exec_id → attributed files → role).
- **E7 unscheduled roles** — fixer is now scheduled (S6, ≤ fix_iteration_limit,
  then BLOCKED + NEED_SUPERVISOR); role registry is schema-derived with loud
  schema-drift failure.

### New subsystems

- **GCS (Global Context Store)** — `context/intent.md` (supervisor is sole
  writer) + append-only `ledger.jsonl` (author+seq) + per-stage digest
  projected to `<worktree>/CLAUDE.md` (the probe-verified channel; 8KB cap,
  truncation priority intent > instruction > ledger, `CTX_TRUNCATED` never
  silent). Gate rationales reflow into the ledger and thus into every
  downstream worker's projection.
- **Six gates with mutation tests** — G-LEAD / G-SCOPE / G-ROLE / G-CTX /
  G-SPEC / G-NEG; `tests/negative/run-negative.sh` proves all six go red
  (6/6 red-as-expected). G-NEG is content-agnostic: overwrite impl with a
  sentinel, require ≥1 pytest failure, restore byte-exact.
- **openspec_gateway** — the only module talking to the openspec CLI
  (init / new change / status / instructions / apply / validate --strict /
  archive). `validate` parses stdout JSON even on exit 1 (strict failures).
- **role_registry** — artifacts[] → roles with DAG waves; `lean` profile merges
  analyst+requirements and architect+planner (4→2 planning MaaS calls).
- **config_loader** — 2-level YAML subset, repo `.ai-dlc/config.yaml` wins.

### Supervisor skill (v0.2 contract)

`/feature` writes `context/intent.md` before launching the bridge; `/approve`
must record the human's rationale (reflowed to workers); `/status` translates
the v0.2 event stream (attribution, CTX_*, LEADER_REGISTERED_WRITE, gate
verdicts); `/cancel` documents the honest v0.2 behavior (gate-level cancel;
worktree preserved).

### Fixed in flight (found by the gates themselves)

- Real E2E run 1 went red at G-CTX: openjiuwen rejected the single-exec brief
  (`unexpected field: item_id`) — stubs don't validate, reality does. Fixed;
  worker-status failures now precede canary checks (root cause before symptom).
- Real E2E run 2 went red at G-CTX again — a TRUE positive class: glm-5.2
  under multi-turn load drops "echo the canary as your reply's first line"
  (verified: a 1-turn probe complies, an 80-turn planning task does not).
  G-CTX now carries two channels: the reply text AND a file receipt — the
  goal's FIRST ACTION is copying the CLAUDE.md canary into `.ctx-echo`, which
  the leader consumes and deletes after every wave (a stale receipt can never
  vouch for a later wave). The token still exists only in the projection, so
  either channel proves delivery.
- Real E2E run 3: architect died `capacity_error` — workflow's own
  `DEFAULT_ITEM_TIMEOUT` is 120s and the bridge never passed `item_timeout`.
  Now wired from `workflow.item_timeout_seconds` (1500) into every manifest.
- Real E2E run 4: G-SCOPE red at IMPLEMENT — the no-`files:`-markers fallback
  built one item PER TASK all with scope `"."` (mutual overlap), and
  `path_in_scope` treated `"."` as matching nothing. Fixed: fallback is ONE
  umbrella item; `"."` means the whole worktree; G-NEG's target set now comes
  from the attribution table (what developers actually wrote), never from a
  scope literal.
- Worktree excludes: git reads `info/exclude` from the COMMON git dir for
  linked worktrees — per-worktree exclude files are silently ignored. Fixed;
  `__pycache__`/`*.pyc` also excluded from the product surface.
- Comparative E2E run 1 (csv-parser task, no `files:` markers): the single
  umbrella item starved — developer died `needs_escalation: client timed out`
  at 1200s (openjiuwen caps a client attempt at 600s; upstream constant). The
  fallback now builds one umbrella item PER TASK, dispatched SERIALLY so each
  task gets its own worker time budget (temporal disjointness instead of
  spatial), stopping honestly at the first failed item.

### Real-MaaS E2E (green)

`evidence/v0.2.0-e2e/task-real-020/` — hello.html task, profile full:
S1 → S2 (architect ∥ requirements fanout) → S3 → GATE 1 → IMPLEMENT →
S5 (tester ∥ reviewer, findings=0) → VERIFY (G-SPEC/G-NEG/G-LEAD/G-SCOPE/
G-ROLE/G-CTX all ✓) → GATE 2 → archive → merge. 6 roles, 7 executors,
`leader_authored_bytes: 0`, 12/12 tests green, mutation check green.
Attribution: analyst→proposal, architect→design, requirements→spec,
planner→tasks, developer→hello.html, tester→tests/test_hello.py.

### Evidence

- `evidence/wiring-audit-baseline-v0.1.0.json` → `evidence/wiring-audit-v0.2.0.json`
  (E1/E2/E3/E5/E6/E7 red→green; E4 stays a documented constraint)
- `tests/negative/results/` — six-gate mutation suite output
- `evidence/v0.2.0-e2e/` — real-MaaS end-to-end run

## v0.1.0 — 2026-08-25 (re-tagged after release-gate verification)

First releasable version. One command, real code, observable process, failing tests go red, humans can block.

> The original v0.1.0 tag was cut before the pipeline had ever run (release-gate
> finding: "tag first, verify later — order reversed"). The tag was deleted and
> re-cut on this commit, after the blockers below were fixed and the acceptance
> evidence was archived under `evidence/v0.1.0-e2e/`.

### Release-gate fixes (2026-08-25, second pass)

- **B1 — systemd unit used a nonexistent flag.** `jiuwenswarm-start --mode gateway`
  crashed in a restart loop (`status=2/INVALIDARGUMENT`); the CLI only accepts
  `{all,web,app,dev}`. Now `ExecStart=...jiuwenswarm-start app`, verified
  `active` with the gateway listening on `127.0.0.1:19001` inside the unit's
  cgroup. Also fixed inert env var names: the gateway reads
  `GATEWAY_HOST`/`GATEWAY_PORT` (verified in `gateway/app_gateway.py:1606-1607`),
  not `JIUWENSWARM_GATEWAY_*`. `ProtectHome=read-only` does not block executing
  `<local-dir>/bin` binaries (verified live).
- **B2 — doctor did not read `.env`.** Doctor now sources the repo `.env`
  (fallback: process env, then `~/.jiuwenswarm/config/.env`), rejects
  placeholder values (`example.com` / `your-model-name`), and performs a real
  MaaS chat round-trip printing model name and latency. Verified all-green
  with `HTTP 200 in ~7.6s, model glm-5.2`.
- **B3 — the pipeline had never run.** Full E2E executed for real on a scratch
  repo: 3 openjiuwen → claude-maas → MaaS calls (developer, tester, reviewer),
  pytest verify green (13/13), both gates exercised. Artifacts — `state.json`,
  `events.jsonl` (24 events), gates/, checkpoints/, executions/ — archived in
  `evidence/v0.1.0-e2e/task-20260825105115-fd6639/`.
- **5th instance of the recurring parameter defect, caught and fixed:**
  `openjiuwen --file X --cwd Y` — `openjiuwen` silently ignores `--cwd` (it only
  parses `--file`; `workflow` has no `--cwd` either). The acceptance command and
  the model client would have run in the wrong working directory. Fixed by
  passing `cwd=` to `subprocess.run` and removing the fake flag from
  `runtime_bridge.py`, `tests/e2e-demo-runner.py`, and the runtime SKILL.md.
- **New gate: parameter-reality check** (`tests/param-reality-check.sh`).
  Scans systemd units, shell scripts, Python `subprocess` calls, and Markdown
  command blocks; asserts every flag exists in the command's real `--help`
  surface (subcommand- and python-script aware). Current state: 100 flags /
  150 invocations verified. Its negative test plants three fake flags across
  three surfaces and requires the gate to go red on each while staying green
  on a clean control root (6/0). This gate is what caught the SKILL.md
  `--cwd` doc defects above on its first run.
- **Delete-module test 4/4** — `runtime_bridge.py` case re-run with the
  timeout raised 300 → 900 s (`E2E_TIMEOUT`), plus `MODULES` env for
  single-module re-runs.

### What works

- **`/team feature "..."`** — single command runs the full pipeline
- **Path B (workflow fanout)** — role dispatch via `manifest_builder → workflow → openjiuwen ×N → claude-maas -p`, NOT `--mode team`
- **Four roles, four independent processes** — spec, developer, tester, reviewer each get a fresh `openjiuwen → claude-maas -p` with no shared context (the Fixer role exists in `brief_builder` but is not scheduled by the v0.1.0 pipeline)
- **Two blocking human gates** — GATE 1 (after spec) and GATE 2 (before ship), file-based, cannot be bypassed
- **File bus** — `state.json` + `events.jsonl` (seq-monotonic) written throughout
- **Scope isolation** — `scope` whitelist + git worktree; empty-scope write-ops rejected as `invalid_brief` with `attempts: 0`
- **OpenSpec integration** — `openspec new change` + `validate` for spec contracts
- **`doctor`** — health check with 14+ assertions

### Verified acceptance criteria

| AC | Standard | Result |
|----|----------|--------|
| AC17 | leader write_file = 0 | ✓ PASS (computed from `events.jsonl` by `tests/compute_ac.py`, not the runtime's self-report) |
| AC18 | role diversity ≥ 2 | ✓ PASS (4 roles: spec, developer, tester, reviewer) |
| AC16 | gates have discriminative power | ✓ PASS (mutation tests: 5/5) |
| D2 fix | all executor modules wired | ✓ PASS (delete-module tests: 4/4) |
| D1 fix | gates call real code | ✓ PASS (3 real negative tests) |
| E2E | pipeline runs end to end with real model calls | ✓ PASS (exit 0, pytest 13/13; evidence in `evidence/v0.1.0-e2e/`) |
| Param reality | all repo flags exist in real `--help` output | ✓ PASS (100 flags / 150 invocations) |
| doctor | all green incl. real MaaS round-trip | ✓ PASS (HTTP 200, ~7.6 s) |
| gateway | systemd service active on 127.0.0.1:19001 | ✓ PASS |

### Known limitations (v0.1.0)

1. **`permissions: ask` does not block in headless mode** (D5). Security boundary is `scope` + worktree, NOT `ask`. Documented in README and doctor output.
2. **`files_changed` and `tokens` from openjiuwen are always empty** (D4). Runtime self-computes `files_changed` via `git diff`; tokens marked as `unavailable` (not 0).
3. **No crash resume / checkpoint recovery** — V1 runs the pipeline once, start to finish. Resume is v0.2.0.
4. **No cancel** — no graceful cancellation mechanism. v0.2.0.
5. **No heartbeat monitoring** — no health supervision during execution. v0.2.0.
6. **No token budget enforcement** — `swarmflow_budget` is set in config but not enforced by the pipeline. v0.2.0.
7. **No PR auto-creation** — pipeline produces code + tests + review, but does not create a GitHub PR. v0.2.0.
8. **No OpenCode/Codex adaptation** — V1 is Claude Code only. v0.2.0.
9. **`--mode team` not used** (D3) — openjiuwen team mode degenerates to leader writing all code. Path A (fixing team mode) is a P1 probe for v0.2.0.
10. **Shebang fix required** (D6) — `openjiuwen` and `workflow` need shebang pointing to `python3.12`. `install.sh --fix-executor` handles this.

### Defects addressed

- **D1** (P0): Three negative gates were tautological — rewrote to call real code + mutation tests
- **D2** (P0): Executor modules were never called — runtime_bridge is now the sole entry point, all modules wired (verified by delete-module tests)
- **D3** (P0): `--mode team` degenerates — switched to Path B (workflow fanout)
- **D4** (P1): Audit fields empty — Runtime self-computes `files_changed` via git diff
- **D5** (P1): `ask` doesn't block — documented, scope + worktree are the real boundary
- **D6** (P1): Shebang — fixed by `install.sh --fix-executor`
