# Diagnose

This README describes only the `diagnose/` skill directory under `AI/AI-Coding`.

## Purpose

`diagnose` is a disciplined debugging workflow for hard bugs, flaky behavior, and performance regressions. It enforces a structured loop of reproduce, minimize, hypothesize, instrument, fix, and regression-test.

## Directory Structure

```text
diagnose/
  README.md
  SKILL.md
  scripts/
    hitl-loop.template.sh
```

## Files

### `SKILL.md`

The main skill definition. It guides the agent through a feedback-loop-first debugging process and pushes toward evidence before fixes.

### `scripts/hitl-loop.template.sh`

A human-in-the-loop shell template for cases where a person must click through a UI or perform a manual verification step while keeping the debugging loop structured.

## Source

Imported and adapted from `https://github.com/mattpocock/skills`.
