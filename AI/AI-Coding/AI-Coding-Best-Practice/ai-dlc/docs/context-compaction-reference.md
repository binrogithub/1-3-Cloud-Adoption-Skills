# P2-4 · Context compaction — a standing reference (no code yet)

Low priority by the PRD's own judgment: no current task has touched a
context ceiling. This note exists so the approach is settled before
the first long task meets the wall, not improvised during it.

## The rule (from grok-build's xai-grok-compaction crate + Anthropic's
truncation lesson)

1. **Critical state lands on disk first.** The plan, the done-artifact
   list, and every decision live in the task record
   (`.ai-dlc/tasks/<id>/`) — written when made, not when the context
   gets tight. Anthropic's lead agent saves its plan to memory
   *immediately* because >200k contexts get truncated; the plane's
   records are that memory.
2. **Compaction touches conversation history only.** Records,
   checkpoints and evidence are never folded into a summary — a
   summary of evidence is not evidence.
3. **Recovery rebuilds from records, not from context residue.** A
   compacted session re-reads the task record and resumes; it never
   trusts what it "remembers" surviving in the window.
4. **Turn checkpoints (P1-5) bound the blast radius.** If compaction
   loses a working state, the last checkpoint restores it — the two
   mechanisms compose.

## When to promote this to code

Promote when a real author session first approaches the ceiling (the
usage frames carry `input_tokens` and `context_max`; `report.py
patterns` will show it). Until then, the rule above is the whole
deliverable —参照级, by design.

*Reference: `reference/grok-build/crates/common/xai-grok-compaction/`,
Anthropic multi-agent retrospection (plan saved to memory at once),
PRD devteam-agent-team-best-practices P2-4.*
