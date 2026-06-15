# maas-dreaming

**Memory dreaming and garbage-collection for AI coding agents.** Native
auto-memory only ever *grows*; `maas-dreaming` periodically summarizes,
consolidates, and cleans. Run it nightly or invoke it as a skill on demand.

One **dream** pass over your Claude Code / Mem0 project memory:

- **dedup** near-identical episodes — [5.4]
- **validate stale paths** — every referenced file is checked against the real
  repo; missing ones are flagged so the agent stops acting on deleted files
  ("confidently wrong") — [5.4]
- **compress** survivors into an L3 index — [5.4]
- **detect conflicts** — a new finding that contradicts an approved rule or
  `CLAUDE.md` → a review-required `conflict-candidate` + a **proposed** `CLAUDE.md`
  patch (never auto-applied) — [5.3, folded into dream]
- **optionally verify symbols / health** — `--verify-symbols` greps explicit
  `symbols:` references and reports memory size against the MiMo 200 line / 10 KB
  target.
- **optionally run LLM dream** — `bin/dream-llm.sh` reuses MiMo's vendored
  `dream.txt` prompt, verifies against local trajectory evidence when available,
  and writes review-only `inbox/` artifacts.
- **optionally write verified candidates to Mem0** — `mce writeback` only writes
  `verified` / `repo-verified` candidates, emits JSONL audit, and delegates
  storage plus entity linking to Mem0.

It solves a real problem native memory doesn't: **memory rot** — duplicates and
references to files that no longer exist, which the agent then trusts.

## Quick start

```bash
bash demo/run-dream-demo.sh          # offline, deterministic, no model
# default skill behavior: write a host-agent-entry dreaming summary report
python3 scripts/dream_agent_report.py --repo-root .
# deterministic maintenance:
python3 scripts/dream.py --memory-dir ~/.claude/projects/<key>/memory --repo-root . --apply
# nested projects: default scope filtering skips sibling-project memories from parent Claude memory
python3 scripts/dream.py --repo-root . --scope-filter auto
# clear current-project local memory, with dry-run first and backup on apply:
python3 scripts/reset_memory.py --repo-root .
python3 scripts/reset_memory.py --repo-root . --apply
# intentional parent-workspace reset from a nested project; also initializes the exact project memory root:
python3 scripts/reset_memory.py --repo-root . --allow-parent --apply
# explicit external LLM leg with an explicit trajectory, no direct memory edits:
bin/dream-llm.sh --repo-root . --trajectory transcript.jsonl --claude-bin <host-agent-command>
# scan a directory into a dream source, then reuse MiMo dream.txt through the LLM leg:
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/dir.dream.md
python3 scripts/dream_agent_report.py --memory-dir ~/.claude/projects/<key>/memory --repo-root /path/to/dir --trajectory /tmp/dir.dream.md
# repeated runs: only send changed/added/deleted files to the LLM
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/full.dream.md --write-manifest /tmp/dream-manifest.json
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/delta.dream.md --since-manifest /tmp/dream-manifest.json --write-manifest /tmp/dream-manifest.next.json
# audited writeback: review first, then explicit apply
python3 -m mce.cli writeback --memory-dir ~/.claude/projects/<key>/memory --repo-root . --org acme --mode review
python3 -m mce.cli run --plan dream-writeback --memory-dir ~/.claude/projects/<key>/memory --repo-root . --org acme --mode apply
```

Nightly + skill invocation: see [`runbook.md`](./runbook.md).

## What's in / out

| In scope | Out of scope (delegated to native Claude Code) |
|----------|-----------------------------------------------|
| 5.3 write-side conflict detection (folded into dream) | 5.1 L0 instruction layering |
| 5.4 dream: dedup / stale-path / compress; distill SOPs | 5.2 tier & index *format* |
| 5.5 governed recall (top-k, token budget) | local memory injection (native auto-memory) |

Removed 5.1/5.2 per [`../prd-remove.md`](../prd-remove.md): native already does them.

## MiMo reuse boundary

This project should stay thin. It carries a full renamed MiMo Code mirror at
`upstream/maas-code/` and reuses those assets where they apply:
`upstream/maas-code/opencode/src/agent/prompt/dream.txt` is the primary LLM dream
prompt, and `auto-dream.ts` is the scheduling reference. First-party Python code
exists only where the Claude Code/Mem0 environment differs from MiMo: source
adapters, review-only patch writing, deterministic path/symbol checks, and tests.

## Layout

```
maas-dreaming/
  SKILL.md / AGENTS.md   the skill (AGENTS.md -> SKILL.md symlink)
  scripts/dream.py       deterministic dream: 5.3 + 5.4 + symbol/health checks
  scripts/reset_memory.py  clear current-project local memory with backup
  scripts/dream_agent_report.py  default host-agent-entry report helper
  scripts/dream_llm.py   review-only LLM dream adapter around MiMo dream.txt
  scripts/dream_sources.py  trajectory adapters for Claude/Mem0 exports
  scripts/scan_to_dream.py  directory -> Markdown dream source adapter
  scripts/should_run.py  auto-dream.ts scheduling adapter
  scripts/distill.py     mine repeated workflows -> SOP candidates
  mce/                   backbone, retrieve, writeback, executor, cli
  bin/dream-nightly.sh   cron/schedule entry point with smart skip gates
  bin/dream-llm.sh       review-only LLM dream entry point
  upstream/maas-code/    complete renamed mirror of vendor/mimo-code
  prompts/               MiMo prompt fallback copies
  assets/                mem0 config + schemas
  vendor -> ../vendor    Mem0 (Apache-2.0) + MiMo-Code (MIT)
  demo/                  run-dream-demo.sh + seed memory + sample repo
  tests/                 backbone, retrieve, dream, writeback
```

## Reuse / first-party

Built on vendored **Mem0** + **MiMo-Code**; first-party code is the thin dream
glue and the conflict detector. Governance is always on: `CLAUDE.md` is never
auto-edited, capture is ADD-only + secret-filtered, recall is budgeted, and
writeback is explicit + audited.
