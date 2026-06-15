---
name: maas-dreaming
description: Nightly (or on-demand) memory hygiene for AI coding agents — the thing native auto-memory does NOT do. Runs a "dream" pass over Claude Code / Mem0 project memory to deduplicate entries, validate that every referenced file path still exists (so the agent never acts on "confidently wrong" stale references), compress survivors into an L3 index, and detect when a new finding conflicts with an approved rule or CLAUDE.md — emitting a review-required conflict candidate and a proposed CLAUDE.md patch (never auto-applied). Use when memory has grown noisy/stale, on a nightly schedule, or whenever the user asks to dream/consolidate/clean up project memory, distill repeated workflows, or recall approved context. Built on vendored MiMo-Code + Mem0 with less than 10 percent first-party glue.
---

# maas-dreaming

Memory **dreaming and garbage-collection** for AI coding agents. Native
auto-memory only ever *grows*; this skill periodically summarizes, consolidates,
and cleans. Invoke it as a skill on demand, or run it every night (see
Scheduling).

## When to use
- Nightly, unattended — keep project memory deduped, path-valid, and consolidated.
- On demand — "dream / consolidate / summarize my memory", "did anything I
  learned conflict with our rules?", or before relying on memory for a big task.
- Reset — when the user says `/maas-dreaming clear`, clear only the current
  project's local memory after a dry-run/apply guard and backup.
- Directory scan — when the user asks to scan a folder and produce a dream file,
  generate a bounded Markdown dream source and feed it to the LLM dream leg.

## Default `/maas-dreaming` behavior

The default `/maas-dreaming` invocation must produce a **dreaming summary
report**, not a reset/clear report. Do not spawn a nested LLM from the default
skill path. The host agent that loaded this skill is the LLM entry. First write
a bounded report scaffold:

```bash
python3 BASE/scripts/dream_agent_report.py --repo-root REPO
```

Replace `BASE` with this skill's base directory and `REPO` with the user's
current project directory or explicit target directory. Then read the printed
report path and use the current host-agent turn to summarize durable findings or
state that no durable memory candidates were justified.

If the user adds free text after `/maas-dreaming` (for example
`/maas-dreaming focus on coding-style preferences; ignore one-off debug notes`),
forward it verbatim as `--instructions "<free text>"`. This mirrors the official
Anthropic Dreams `instructions` field: it is bounded to 4096 chars,
secret-redacted, and rendered as a `## Steering Instructions` section the host
agent must apply when deciding what to merge, drop, or surface.

The report also includes a deterministic `## Signal Scan` section: a cheap,
bounded classification of the trajectory evidence into **corrections**
(highest priority), **preferences**, **decisions**, and **recurring** pain.
Treat it as review-only evidence (no memory is written) that tells you where the
durable signals are — start there before scanning the raw preview.

Use the user's current project directory or explicit target directory as
`REPO`. Do not replace it with `git rev-parse --show-toplevel` in multi-project
repositories. `dream_agent_report.py` writes `inbox/dream-agent-*.report.md`
under the project's native memory root and prints the report path. It may create the
default native `memory/` directory when the project only has Claude Code
transcript `.jsonl` files.

Only invoke `scripts/reset_memory.py` when the user explicitly asks for
`/maas-dreaming clear`, reset, or memory deletion.

## What deterministic maintenance does (`scripts/dream.py`)
1. **Dedup** near-identical episodes (task + decisions signature).            [5.4]
2. **Validate stale paths** — every `files_touched[]` is checked against the real
   repo; missing ones are annotated `# STALE` (or dropped) so the agent stops
   acting on deleted files ("confidently wrong").                            [5.4]
3. **Compress** survivors into `semantic/dream-index.md` (the L3 index).      [5.4]
4. **Detect conflicts** — a new decision that contradicts an approved L3 rule or
   a `CLAUDE.md` rule → writes a `conflict-candidate` to `inbox/` **and a
   proposed `CLAUDE.md` patch**. It never edits `CLAUDE.md`; a human reviews and
   `git apply`s.                                                              [5.3]
5. **Optionally verify symbols + health** — `--verify-symbols` checks explicit
   `symbols:` / `symbols_touched:` references; every run reports the MiMo
   `MEMORY.md` size budget.

The explicit external LLM leg (`bin/dream-llm.sh`) reuses the renamed MiMo mirror at
`upstream/maas-code/` and adapts only the source-of-truth input: MiMo's
`mimocode.db` becomes a local Claude Code / Mem0 trajectory source when one is
available. If no trajectory is available, proposed promotions are marked
`[unverified]`. Use it only when explicitly requested or from automation that
intentionally wants a separate LLM process; it is not the default skill entry.

Deterministic maintenance is **dry-run** by default; pass `--apply` to rewrite
L2 memory/index artifacts.

## Operations (agent-invokable)
| Op | Command |
|----|---------|
| **dream-report** (default `/maas-dreaming`) | `python3 BASE/scripts/dream_agent_report.py --repo-root REPO [--memory-dir DIR] [--trajectory PATH] [--instructions TEXT] [--output-mode native\|project-root] [--out-dir DIR] [--keep N]` |
| dream-maintenance (deterministic cleanup) | `python3 scripts/dream.py --memory-dir DIR --repo-root REPO [--apply] [--verify-symbols] [--scope-filter auto|on|off]` |
| clear/reset current memory | `python3 scripts/reset_memory.py --repo-root REPO [--memory-dir DIR] [--apply] [--allow-parent]` |
| scan-dir (make dream source) | `python3 scripts/scan_to_dream.py DIR --output OUT.md` |
| dream-llm (explicit external LLM runner) | `bin/dream-llm.sh --repo-root REPO --claude-bin CMD [--memory-dir DIR] [--trajectory PATH]` |
| writeback (verified candidates → Mem0) | `python3 -m mce.cli writeback --memory-dir DIR --repo-root REPO --org ORG --mode review|apply` |
| run plan (unified executor) | `python3 -m mce.cli run --plan dream-writeback --memory-dir DIR --repo-root REPO --org ORG --mode review|apply` |
| distill (mine SOPs) | `python3 scripts/distill.py --memory-dir DIR --min-support 2 [--apply]` |
| retrieve (recall) | `python3 -m mce.cli retrieve --query "<task>" --max-items 5 --max-tokens 2000` |
| capture (write to L2) | `python3 -m mce.cli capture --text "<fact>" --org acme` |

`--memory-dir` defaults to the native Claude Code project memory
(`~/.claude/projects/<key>/memory`). `--repo-root`/`--repo-claude` locate the
files and `CLAUDE.md` to validate against.
If native Claude memory resolves to a parent workspace, `--scope-filter auto`
skips sibling-project memories that do not mention the current repo identity
(for example `maas-dreaming`). Use `--scope-filter off` only when intentionally
dreaming the whole parent memory root.
For deterministic maintenance, use the user's current project directory or
explicit target directory as `--repo-root`; do not replace it with
`git rev-parse --show-toplevel` in multi-project repositories, because that
maintains the parent workspace instead of the current project. Prefer running
scripts by absolute skill path from the user cwd instead of `cd`-ing into the
skill directory.

When the user invokes `/maas-dreaming clear`, run `scripts/reset_memory.py`
against the user's current project directory. Default is dry-run and prints the
memory artifacts that would be removed. Only pass `--apply` when the user
explicitly asks to apply/confirm the clear. If native Claude memory resolves to
a parent workspace, the script refuses by default; use `--allow-parent` only
when the user explicitly wants to clear that parent workspace memory. Every
apply run writes a backup beside the active memory directory before deleting.
After an allowed parent clear, apply mode creates the exact current-project
native memory directory so the next maas-dreaming run resolves to the current
project instead of falling back to the parent empty memory root. Use
`--no-init-exact` only when intentionally preserving parent-root resolution.

For folder-to-dream requests, run:

```bash
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/dir.dream.md
python3 BASE/scripts/dream_agent_report.py --memory-dir DIR --repo-root /path/to/dir --trajectory /tmp/dir.dream.md
```

The scanner is deterministic glue: it redacts obvious secrets, skips common
heavy folders (`.git`, `node_modules`, `vendor`, build caches), bounds file
content, and emits Markdown that the existing dream trajectory adapter reads.
For repeated runs, use a manifest so only changes are sent to the LLM:

```bash
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/full.dream.md --write-manifest /tmp/dream-manifest.json
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/delta.dream.md --since-manifest /tmp/dream-manifest.json --write-manifest /tmp/dream-manifest.next.json
```

This mirrors MiMo reconcile's fingerprint idea: walk the tree for correctness,
but skip unchanged file content in delta dream input.

## Installing this skill
Build and install the loadable skill bundle:

```bash
bin/install-skill.sh --target both --mode copy
```

This writes:
- Codex: `${CODEX_HOME:-$HOME/.codex}/skills/maas-dreaming`
- Claude Code: `$HOME/.claude/skills/maas-dreaming`

For project-local Claude Code use, copy or symlink the built bundle to
`.claude/skills/maas-dreaming`.

## Scheduling (nightly)
Run `bin/dream-nightly.sh` from cron / the `schedule` skill / `loop`. See
`runbook.md`. It ports MiMo `auto-dream.ts` skip gates: too-young projects and
recently dreamed projects are skipped unless `MCE_FORCE=1`. Start in dry-run for
a week, read the reports, then enable `MCE_APPLY=1`. Set `MCE_LLM=1` to add the
review-only LLM leg after deterministic dream.

## Output location & team sharing
By default the report goes to the **native** Claude memory root
(`~/.claude/projects/<key>/memory/inbox/`) — private to one developer and not
auto-discoverable. For multi-member teams that want to commit and share dream
findings, switch the artifact base:

| Mode | Flag | Base dir | Use |
|------|------|----------|-----|
| native (default) | _(none)_ | `~/.claude/.../memory` | private, per-developer |
| project-root | `--output-mode project-root` | `<repo>/.maas-dreaming/` | git-shareable across the team |
| explicit | `--out-dir ./memory` | `./memory/` | any path you choose |

Every mode writes `inbox/dream-agent-*.report.md` plus a skill-owned
`DREAMS.md` index (newest-first, with signal-count summaries) and applies
`--keep N` retention (default 20; `0` = unlimited) so reports never pile up.
Trajectory evidence is always read from the native memory root, so dedup/recall
stay coherent regardless of where the report is written.

In `project-root`/`--out-dir` mode the skill also writes
`POINTER.suggested.md`: the **one line a human pastes into the repo `CLAUDE.md`**
(reviewed via PR) so every teammate's next session auto-discovers the shared
index. The skill never edits `CLAUDE.md` itself.

**Team flow:** run `/maas-dreaming` with `--output-mode project-root` → commit
`.maas-dreaming/` → once, add the suggested `CLAUDE.md` pointer via PR. After
that, every member's sessions auto-load the shared, review-only dream index.

## Interactive auto-trigger (opt-in, no nested LLM)
For interactive users who do not run cron, an optional Stop hook can flag a due
dream that the **next real session's host agent** then runs — no LLM is spawned
from the hook. Two opt-in steps:

1. Register the Stop hook in `~/.claude/settings.json` (the skill never edits
   settings for you):
   ```json
   "hooks": { "Stop": [{ "type": "command",
     "command": "bash $HOME/.claude/skills/maas-dreaming/bin/dream-stop-hook.sh" }] }
   ```
   On session end it runs `should_run.py pending` for the current project: if the
   schedule gate (same interval as cron, `MCE_DREAM_INTERVAL_DAYS`, default 7
   days) is eligible, it writes a project-scoped `.dream-pending` flag under the
   native memory dir. It always exits 0 and never calls an LLM.
2. Add a session-start directive to your project (or global) `CLAUDE.md`:
   > **Auto Dream (maas-dreaming):** At session start, run
   > `python3 $HOME/.claude/skills/maas-dreaming/scripts/should_run.py pending-status --repo-root .`.
   > If it exits 0, run `/maas-dreaming`, then run the same script with
   > `clear-pending` to remove the flag and reset the timer.

This keeps the host-agent-only principle intact: the hook only schedules; the
actual dream is executed by a real host-agent turn.

## Governance (always on)
dedup/stale repair touch only L2 episode files · `CLAUDE.md`/`AGENTS.md` are
**never** auto-edited (conflicts → `inbox/` + proposed patch) · capture is
ADD-only, scoped, secret-filtered · recall is top-k under a token budget.
LLM dream also writes only review artifacts (`memory-md.<stamp>.proposed.patch`
plus latest alias `memory-md.proposed.patch`,
`memory-md.cumulative.proposed.patch` for multi-run review, optional
`global-memory.proposed.patch`, report files).
Automatic Mem0 writeback is explicit and audited: `--mode review` only writes
`inbox/writeback-<stamp>.jsonl`; `--mode apply` writes only verified or
repo-verified candidates through Mem0, relying on Mem0 entity linking for
graph-like memory rather than custom graph writes.

## Not in scope
L0 instruction layering (5.1) and the tier/index *format* (5.2) are **delegated
to native Claude Code** and intentionally not part of this skill. See
`../prd-remove.md`.

## Files
`scripts/dream.py` (5.3+5.4 merged) · `scripts/reset_memory.py` ·
`scripts/distill.py` · `mce/` glue (backbone/retrieve/cli) ·
`upstream/maas-code/` renamed MiMo mirror · `prompts/` fallback prompt copies ·
`assets/` mem0 config + schemas · `vendor/` upstreams · `demo/` runnable demo ·
`runbook.md`.
