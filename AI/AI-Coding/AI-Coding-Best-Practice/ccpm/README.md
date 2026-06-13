# CCPM Skill

This README describes only the `ccpm/` skill directory under `AI/AI-Coding`.

## Purpose

`ccpm` is a spec-driven project management and delivery-orchestration skill for AI coding workflows. It uses PRDs, technical epics, GitHub Issues, git worktrees, and parallel agent execution to keep implementation traceable from requirements to shipped code.

This repository version is a lightweight import of the upstream `automazeio/ccpm` skill. The goal is to preserve the original workflow and script-first operating model while packaging it into the local AI Coding skill library.

## Directory Structure

```text
ccpm/
  README.md
  SKILL.md
  references/
    conventions.md
    execute.md
    plan.md
    structure.md
    sync.md
    track.md
    scripts/
      blocked.sh
      epic-list.sh
      epic-show.sh
      epic-status.sh
      help.sh
      in-progress.sh
      init.sh
      next.sh
      prd-list.sh
      prd-status.sh
      search.sh
      standup.sh
      status.sh
      validate.sh
  agents/
    openai.yaml
```

## Files

### `SKILL.md`

The main entry point. It routes the agent into CCPM's five phases:

- plan
- structure
- sync
- execute
- track

### `references/*.md`

The phase-specific operating guides and shared conventions copied from the upstream CCPM skill.

### `references/scripts/*.sh`

Deterministic bash helpers for status, standup, search, next, blocked, validation, and epic or PRD inspection. CCPM expects these scripts to be run directly instead of reimplementing those operations with LLM reasoning.

### `agents/openai.yaml`

UI metadata for skill browsers or launchers.

## Source

Upstream project: `https://github.com/automazeio/ccpm`
