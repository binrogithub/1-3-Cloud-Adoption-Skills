# Setup Matt Pocock Skills

This README describes only the `setup-matt-pocock-skills/` skill directory under `AI/AI-Coding`.

## Purpose

`setup-matt-pocock-skills` bootstraps the repository metadata expected by several engineering workflow skills. It configures issue-tracker conventions, triage labels, and domain document layout under `docs/agents/`.

## Directory Structure

```text
setup-matt-pocock-skills/
  README.md
  SKILL.md
  domain.md
  issue-tracker-github.md
  issue-tracker-gitlab.md
  issue-tracker-local.md
  triage-labels.md
```

## Files

### `SKILL.md`

The main setup skill. It inspects the repo, confirms conventions with the user, and writes the agent-facing configuration files.

### `issue-tracker-*.md`

Templates and guidance for supported issue tracker backends.

### `triage-labels.md`

Defines the label vocabulary expected by the triage workflow.

### `domain.md`

Defines how downstream skills should discover and consume `CONTEXT.md`, `CONTEXT-MAP.md`, and ADR locations.

## Source

Imported and adapted from `https://github.com/mattpocock/skills`.
