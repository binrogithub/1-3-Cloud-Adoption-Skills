# E9: Documentation & SKILL.md

**Depends on:** E0–E8 (all epics)  
**Blocks:** nothing (final epic)  
**Estimate:** 0.5 day  
**PRD sections:** 8.2, 10.1

## Goal

Update all user-facing documentation to reflect the new code-index capabilities,
CLI commands, and nightly pipeline. This is the final epic — it documents
everything built in E0–E8.

## Stories

### S9.1: Update SKILL.md

Rewrite `SKILL.md` to cover the full capability set:

**New sections to add:**
- Project Knowledge Engine: what it does (code indexing + git history + memory)
- Quick Start: `mce index` → `mce query overview` → `/code-dreaming`
- Code Index: how it works, supported languages, incremental behavior
- Query API: available queries with examples
- Team Sharing: artifact export/import workflow
- Nightly Pipeline: setup and scheduling

**Sections to update:**
- Description: expand from "memory hygiene" to "project knowledge engine"
- Default behavior: now auto-indexes on first run
- Remove or fix the "confidently wrong" wording that triggers false positives

**Acceptance:**
- SKILL.md accurately describes all new capabilities
- Quick-start section works for a fresh user
- No wording that triggers false-positive signal classification

### S9.2: Update AGENTS.md

Update `AGENTS.md` to describe the new agent capabilities:

- Add: code-index awareness (the agent can query project structure)
- Add: git history context (the agent knows recent changes)
- Update: dream report now includes project overview, not just memory health

**Acceptance:**
- AGENTS.md accurately reflects new capabilities
- No stale references to old-only behavior

### S9.3: Create runbook.md

Create `docs/runbook.md` as an operator guide:

```markdown
# code-dreaming Runbook

## First-Time Setup
1. Install dependencies: `pip install -e ".[languages]"`
2. Install grammars: `python3 assets/tree-sitter/install_grammars.py --all`
3. Index project: `mce index`
4. Run first dream: `/code-dreaming`

## Daily Operations
- Incremental index: `mce index` (only re-indexes changed files)
- Query project: `mce query search "function_name"`
- Full dream report: `/code-dreaming`

## Nightly Pipeline Setup
- One-time: `python3 scripts/should_run.py --cron-setup .`
- Add the printed line to `crontab -e`

## Team Sharing
- Export: `mce artifact export`
- Commit: `git add .code-dreaming/code-index.db.zst artifact.json`
- New clone: `mce artifact import`

## Troubleshooting
- Empty report: check `mce query overview` — if 0 files, re-run `mce index`
- Missing grammar: `python3 assets/tree-sitter/install_grammars.py --check`
- Slow index: check `--max-files` limit, exclude large vendored dirs
- Stale data: delete `.code-dreaming/code-index.db` and re-index
```

**Acceptance:**
- Runbook covers setup, daily use, nightly pipeline, team sharing, troubleshooting
- All commands in the runbook actually work
- No references to unimplemented features

### S9.4: Update pyproject.toml metadata

Update project metadata in `pyproject.toml`:

- Description: reflect "project knowledge engine" scope
- Keywords: add `tree-sitter`, `code-index`, `knowledge-graph`
- Entry points: add `mce` CLI if not already present

**Acceptance:**
- `pyproject.toml` metadata is accurate
- Package description matches new capabilities

## Definition of Done

- [ ] SKILL.md rewritten with complete new capability documentation
- [ ] AGENTS.md updated
- [ ] `docs/runbook.md` created with operator guide
- [ ] `pyproject.toml` metadata updated
- [ ] All commands referenced in docs actually work (manual verification)
- [ ] No stale references to old-only behavior in any doc
