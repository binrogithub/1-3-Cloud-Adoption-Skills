# Triage

This README describes only the `triage/` skill directory under `AI/AI-Coding`.

## Purpose

`triage` provides a repeatable issue-triage state machine. It classifies incoming work, asks only the missing questions, and produces durable agent-ready briefs or explicit rejections.

## Directory Structure

```text
triage/
  README.md
  SKILL.md
  AGENT-BRIEF.md
  OUT-OF-SCOPE.md
```

## Files

### `SKILL.md`

The main skill definition. It guides the full triage workflow from context gathering to state transition.

### `AGENT-BRIEF.md`

Reference format for handing an issue to an implementation agent with enough context to act.

### `OUT-OF-SCOPE.md`

Reference format for documenting durable rejections or explicitly unsupported requests.

## Source

Imported and adapted from `https://github.com/mattpocock/skills`.
