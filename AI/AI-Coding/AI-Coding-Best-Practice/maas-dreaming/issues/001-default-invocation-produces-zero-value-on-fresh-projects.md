# Issue 001: Default `/maas-dreaming` ignores project source code and git history entirely

**Severity:** High — fundamental data-source gap, not just a cold-start edge case  
**Component:** `scripts/dream_agent_report.py`, `scripts/dream_sources.py`, `scripts/dream.py`  
**Reproducible:** 100% on any project without pre-existing Claude Code memory artifacts

## Summary

Running `/maas-dreaming` on a real project (66 files, 142 git commits, 12 test files) produces a report with zero actionable findings. The skill **does not scan source code, git history, or any project files**. Its only data sources are:

1. Claude Code session `.jsonl` transcript files (conversation logs)
2. Pre-existing structured memory files (`memory/episodic/*.md`)

On a project that has never had Claude Code memory written to it, both sources are empty (or contain only the current session's self-referential metadata). The 66 source files and 142 commits are completely invisible to the tool.

### What the skill scans vs. what it ignores

| Data source | Scanned? | This project has |
|-------------|----------|-----------------|
| `~/.claude/projects/<key>/*.jsonl` (Claude session logs) | Yes | 1 file (current session only, 7 metadata records) |
| `memory/episodic/*.md` (structured memory entries) | Yes (by `dream.py`, but not invoked by default) | None |
| Source code (`*.py`, `*.sh`, `*.yaml`, etc.) | **No** | 66 files |
| Git history (`git log`, `git diff`, `git blame`) | **No** | 142 commits |
| README.md / CLAUDE.md / AGENTS.md content | **No** (only checked for conflict detection against existing memory) | All present |
| Test files | **No** | 12 files |

The skill is architecturally a **memory hygiene tool** (clean/dedup/validate existing memory entries), not a **project analysis tool** (scan code and history to generate insights). This is a fundamental expectation mismatch with what a user anticipates when running "dreaming" against a project folder.

## Root causes

### 0. Fundamental data-source gap — source code and git history are invisible

**Files:** `scripts/dream_sources.py:263-283` (`discover_source`), `scripts/dream.py:591` (`source_dir.glob("*.md")`)

`discover_source()` searches exclusively for:
- `mimocode.db`, `trajectory.db` (SQLite databases)
- `transcript.jsonl`, `trajectory.jsonl` (JSONL logs)
- `transcript.md`, `trajectory.md` (Markdown transcripts)
- `*.jsonl` glob in `~/.claude/projects/<key>/`

`dream.py` scans exclusively `memory/episodic/*.md` files.

Neither component reads any source file in the repo, runs `git log`, or inspects project structure. The `scan_to_dream.py` script exists as an adapter that *can* walk a directory tree and produce a dream-compatible Markdown input, but it is never called by the default `/maas-dreaming` path — it requires explicit invocation:

```bash
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/dir.dream.md
```

**Fix options:**
- (a) **Integrate `scan_to_dream.py` into the default path**: when no trajectory source exists but the repo has files, auto-run the scanner to generate a bounded dream input. This gives the skill something meaningful to analyze on first run.
- (b) **Add a git-history adapter**: a new trajectory source that reads `git log --format` and converts recent commits into evidence records. This is the richest signal for "what happened in this project" and costs nothing to extract.
- (c) **Hybrid cold-start**: on first run, generate a project snapshot (file tree + recent git log + key config files) as a one-time trajectory input, then switch to incremental session-based dreaming on subsequent runs.

### 1. Signal classifier false positive on self-referential content

**File:** `scripts/dream_signals.py:26`  
**Pattern:** `r"\bwrong\b"` in the `corrections` signal class

The trajectory evidence includes the skill's own attachment record (the SKILL.md description loaded by Claude Code when the skill activates). The description contains the phrase "confidently wrong stale references" — explaining what the skill *prevents*. The word "wrong" triggers the `\bwrong\b` correction-class regex, producing:

```
corrections=1, preferences=0, decisions=0, recurring=0
```

This is a false positive. The signal scanner classifies raw text without distinguishing record type (user message vs. system attachment vs. metadata). An attachment containing the skill's own documentation is not a user correction.

**Fix options:**
- (a) Filter by `role`: only classify records where `role == "user"` or `role == "assistant"`. System/attachment records carry no correction intent.
- (b) Filter by `project_match` + `role`: require `project_match=true` AND a meaningful role before classifying.
- (c) Skip records whose `preview` contains the skill's own name in an attachment context (fragile, not recommended).

### 2. Trajectory source is the current session itself

**File:** `scripts/dream_sources.py:263-283` (`discover_source`)

On a fresh project, `discover_source` finds the *current session's* `.jsonl` file — the very session that invoked `/maas-dreaming`. This file contains:

| Record | Content |
|--------|---------|
| Mode metadata | `{"mode": "normal", ...}` |
| Permission mode | `{"permissionMode": "bypassPermissions", ...}` |
| File history snapshot | session housekeeping |
| User message | the `/maas-dreaming` command itself |
| Skill attachment | the full SKILL.md content |
| Skills list attachment | the skills registry |
| Session metadata | cwd, branch, version |

None of these represent prior user work, coding decisions, corrections, or preferences. The report is analyzing the act of running the skill, not any real development trajectory.

**Fix options:**
- (a) Implement a minimum-evidence gate: if fewer than N records with `role="user"` exist (excluding skill invocations), emit a short "insufficient trajectory" result and skip the full report.
- (b) Exclude the current session's `.jsonl` from discovery (requires the session ID to be passed in or inferred).
- (c) Require at least 2 distinct session `.jsonl` files before generating a full report.

### 3. Default path never runs deterministic maintenance

**File:** `SKILL.md:22-36` (Default behavior section)

The SKILL.md explicitly says the default invocation runs only `dream_agent_report.py` (the scaffold), not `dream.py` (the deterministic maintenance engine). The five core value propositions listed in SKILL.md lines 62-74 — dedup, stale-path validation, L3 compression, conflict detection, symbol verification — all live in `dream.py` and are never invoked unless the user separately runs the `dream-maintenance` command.

This means the default `/maas-dreaming` can only produce value when:
1. There is rich multi-session trajectory data, AND
2. The host agent (Claude) does manual synthesis from the raw evidence preview

On a fresh project, neither condition holds.

**Fix options:**
- (a) When memory artifacts exist (`MEMORY.md`, `memory/*.md`), automatically run `dream.py --repo-root REPO` in dry-run mode as part of the default invocation and include its findings in the report.
- (b) At minimum, check for existing memory files and report their stale-path status even in the scaffold path.
- (c) Add a "nothing to dream about" fast-exit when both trajectory and memory are empty, with a user-friendly message explaining when the skill becomes useful.

### 4. No cold-start guidance

There is no early-exit or user guidance when the skill runs against a project with no memory and minimal trajectory. The user sees a structurally complete report (headers, sections, signal scan) that looks like it *did* something, but every section is empty or contains only false positives. This erodes trust in the tool.

**Fix:** When both conditions hold — (no existing memory files) AND (trajectory records < threshold OR all records are from the current session) — emit a concise message:

```
No accumulated memory or multi-session trajectory found for this project.
maas-dreaming becomes useful after several coding sessions have built up
memory entries and trajectory data. Run it again after working on this
project for a few sessions.
```

## Impact

- **User trust:** A first-time user running `/maas-dreaming` sees a report with a false-positive correction and zero actionable output. This makes the skill appear broken.
- **Resource waste:** The skill reads the JSONL, classifies records, writes a report file, writes an index — all producing nothing useful.
- **Misaligned expectations:** SKILL.md advertises dedup, stale-path repair, L3 compression, and conflict detection. The default invocation delivers none of these, even when memory artifacts exist.

## Recommended fix priority

1. **Cold-start gate with honest messaging** (root cause 4) — cheapest fix, biggest UX improvement. Tell the user what the tool actually needs before it can help.
2. **Integrate `scan_to_dream.py` + git-history adapter into default path** (root cause 0) — this is the strategic fix. A project with 66 files and 142 commits has rich signal; the skill just refuses to look at it.
3. **Signal classifier role filtering** (root cause 1) — eliminates false positives on the trajectory it does read.
4. **Minimum-evidence gate on trajectory** (root cause 2) — prevents self-analysis of the invoking session.
5. **Run dry-run `dream.py` when memory exists** (root cause 3) — delivers the advertised maintenance value.

## Architectural observation

The skill is positioned as "memory dreaming and garbage-collection" but a user running `/maas-dreaming` on a project folder naturally expects it to *look at the project*. The existing `scan_to_dream.py` already has the capability to walk a directory, redact secrets, skip heavy folders, and produce bounded Markdown — it just is not wired into the default path. Connecting it would transform the first-run experience from "nothing found" to a meaningful project snapshot that the host agent can synthesize.
