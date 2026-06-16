# Runbook — code-dreaming

Memory **garbage-collection** for AI coding agents. One *dream* pass over your
Claude Code / Mem0 project memory: **dedup** episodes, **validate stale paths**
(so the agent stops acting on deleted files), **compress** to an L3 index, and
**detect conflicts** with approved rules / `CLAUDE.md` (→ a review-required
candidate + a proposed patch, never auto-applied). Optional deterministic checks
verify explicit symbols and memory size. The optional LLM leg reuses MiMo's
vendored `dream.txt` prompt and writes review-only consolidation artifacts.

Two ways to run it: **A. nightly, unattended** · **B. on demand, as a skill**.

```bash
cd .../enterprise-context-engineering/code-dreaming
python3 --version          # 3.10+  (dream/distill/retrieve are stdlib)
```

---

## 0. Verify it works (end-to-end)

```bash
bash demo/e2e-test.sh      # isolated temp project; asserts the whole loop
bash demo/e2e-full-delta-dream.sh  # full scan -> manifest -> delta scan -> LLM report
```

Verified output (16/16 PASS):

```text
[1] dream dry-run
  PASS: dry-run finds 1 duplicate
  PASS: dry-run finds 1 stale path
  PASS: dry-run finds 1 conflict
  PASS: dry-run wrote nothing (no inbox)
[2] dream --apply
  PASS: duplicate episode removed
  PASS: stale path annotated
  PASS: L3 dream-index written
  PASS: conflict-candidate written to inbox
  PASS: proposed CLAUDE.md patch written
  PASS: CLAUDE.md NOT auto-edited (human gate)
[3] human applies the proposed patch
  PASS: patch applies; CLAUDE.md now annotated
[4] re-run after annotation (idempotent)
  PASS: no new duplicates on re-run
  PASS: marker not duplicated
[5] human fixes the rule -> conflict clears
  PASS: conflict gone after real fix
[6] distill mines an SOP candidate
  PASS: procedural SOP candidate written
[7] retrieve recalls approved L3
  PASS: retrieve returns RB-0001 under budget
E2E: 16 passed, 0 failed — RESULT: PASS
```

This is the full lifecycle: flagged → patch proposed → human applies → stays
flagged until a *real* fix → conflict clears → distill + retrieve still work.
Unit tests: `python3 -m pytest -q` (125 passing).

## Packaging as a skill

Build a clean runtime-only skill bundle:

```bash
python3 scripts/build_skill.py --output dist/code-dreaming
```

Install it for both Codex and Claude Code:

```bash
bin/install-skill.sh --target both --mode copy
```

Installed locations:
- Codex: `${CODEX_HOME:-$HOME/.codex}/skills/code-dreaming`
- Claude Code: `$HOME/.claude/skills/code-dreaming`

Use `--target codex` or `--target claude` for a single host. Use
`--mode symlink` during development when you want the installed skill to follow
the latest built bundle.

> **Format note (important):** episodic frontmatter uses **block lists** (`- `
> items), the format native memory and dream parse. Inline `["a","b"]` lists are
> NOT parsed — they read as one string. See `demo/e2e-test.sh` for the shape.

---

## A. Nightly (every evening)

`bin/dream-nightly.sh` runs one pass. **Dry-run by default**; `MCE_APPLY=1` writes.

**1) Claude Code scheduled agent (`/schedule`)** — preferred in-harness:

```text
/schedule create "code-dreaming nightly" --cron "0 2 * * *" \
  --task "Run: MCE_APPLY=1 bash bin/dream-nightly.sh /path/to/your/repo"
```

**2) plain cron:**

```cron
0 2 * * *  cd /path/to/code-dreaming && MCE_APPLY=1 bash bin/dream-nightly.sh /path/to/your/repo >> ~/.code-dreaming.log 2>&1
```

**3) `/loop`** during a long session: `/loop 24h MCE_APPLY=1 bash bin/dream-nightly.sh /path/to/your/repo`

Env: `MCE_MEMORY_DIR` (default native `~/.claude/projects/<key>/memory`),
`MCE_APPLY=1`, `MCE_DREAM_INTERVAL_DAYS=7`, `MCE_FORCE=1`, `MCE_LLM=1`, `PYTHON`.
The nightly wrapper uses smart skip gates: it skips projects
younger than the interval and projects dreamed too recently. `MCE_FORCE=1`
bypasses the gates. `MCE_LLM=1` runs `bin/dream-llm.sh` after the deterministic
pass and still writes only review artifacts.

> **Roll out safely:** dry-run (omit `MCE_APPLY`) for ~a week, read the reports +
> any `inbox/` conflicts, then enable `MCE_APPLY=1`.

---

## B. On demand — the `dream` skill

In Claude Code, invoke the skill. The default `/code-dreaming` path writes a
review-only dreaming summary report; clear/reset is a separate explicit command.
Equivalent commands:

```bash
# default /code-dreaming: report only; no nested LLM process
python3 scripts/dream_agent_report.py --repo-root .

# deterministic maintenance dry-run
python3 scripts/dream.py --memory-dir ~/.claude/projects/<key>/memory --repo-root .

# apply: dedup, repair stale, write L3 index, write inbox conflicts
python3 scripts/dream.py --memory-dir ~/.claude/projects/<key>/memory --repo-root . --apply
#   --drop-stale     remove stale entries instead of annotating
#   --repo-claude P  CLAUDE.md to check conflicts against (default <repo-root>/CLAUDE.md)
#   --verify-symbols check explicit symbols:/symbols_touched: with rg/grep
#   --scope-filter auto|on|off  skip sibling-project memories when native memory
#                 resolves to a parent workspace (default: auto)
#   --health-budget-lines 200 --health-budget-kb 10
```

When Claude Code stores memory at a large workspace root, `--scope-filter auto`
prevents a nested project from dreaming unrelated sibling-project memories. The
report shows `out-of-scope skipped: N`. Use `--scope-filter off` to process the
whole parent memory root intentionally.

For nested projects, pass the current project directory as `--repo-root`; do not
replace it with `git rev-parse --show-toplevel` unless the whole git root is
actually the project you want to dream.

Clear current-project local memory:

```bash
# /code-dreaming clear: dry-run, reports what would be removed
python3 scripts/reset_memory.py --repo-root .

# /code-dreaming clear --apply: backup, then remove selected memory artifacts
python3 scripts/reset_memory.py --repo-root . --apply

# only when intentionally clearing an inherited parent workspace memory root
python3 scripts/reset_memory.py --repo-root . --allow-parent --apply
# suppress current-project memory-root initialization only when preserving parent resolution
python3 scripts/reset_memory.py --repo-root . --allow-parent --apply --no-init-exact
```

The clear operation removes local memory artifacts (`*.md`, `*.jsonl`,
`*.sqlite*`, `episodic/`, `semantic/`, `inbox/`, `working/`) under the resolved
memory directory. It never edits repository files. If Claude memory resolves to
a parent workspace instead of the exact current project, it refuses unless
`--allow-parent` is passed. Apply mode writes a backup beside `memory/` first.
After an allowed parent clear, apply mode creates the exact current-project
native memory directory so later code-dreaming runs do not fall back to the
parent empty memory root.

Explicit external LLM dream with an explicit memory root or trajectory:

```bash
bin/dream-llm.sh --repo-root . --claude-bin <host-agent-command>
bin/dream-llm.sh --memory-dir ~/.claude/projects/<key>/memory --repo-root . --claude-bin <host-agent-command>
bin/dream-llm.sh --memory-dir DIR --repo-root . --trajectory transcript.jsonl --claude-bin <host-agent-command>
# optional: --max-days 7 --max-bytes 200000
```

Scan a directory into a dream source file, then run the dream prompt over it:

```bash
python3 scripts/scan_to_dream.py /path/to/dir --output /tmp/dir.dream.md
python3 scripts/dream_agent_report.py --memory-dir DIR --repo-root /path/to/dir --trajectory /tmp/dir.dream.md
# scanner caps: --max-files 200 --max-file-bytes 16384 --max-total-bytes 200000
```

The generated file is Markdown trajectory input. It is bounded, redacted, and
review-only; it does not write memory by itself.

For repeated directory dream runs, keep a manifest and send only changes:

```bash
python3 scripts/scan_to_dream.py /path/to/dir \
  --output /tmp/full.dream.md \
  --write-manifest /tmp/dream-manifest.json

python3 scripts/scan_to_dream.py /path/to/dir \
  --output /tmp/delta.dream.md \
  --since-manifest /tmp/dream-manifest.json \
  --write-manifest /tmp/dream-manifest.next.json
```

This matches MiMo's reconcile shape: it still walks the tree, but unchanged
fingerprints are counted and omitted from the LLM dream source.

Companions:

```bash
python3 scripts/distill.py --memory-dir DIR --min-support 2 --apply   # mine SOP candidates
python3 -m mce.cli retrieve --query "routing fallback" --max-items 5   # recall approved context
python3 -m mce.cli capture  --text "<fact>" --org acme --app gateway   # ADD-only write (needs Mem0)
python3 -m mce.cli writeback --memory-dir DIR --repo-root . --org acme --mode review
python3 -m mce.cli run --plan dream-writeback --memory-dir DIR --repo-root . --org acme --mode apply
```

---

## Reading the output

```
duplicates       : 1     ← near-identical episodes (one removed on --apply)
stale paths found: 1     ← files_touched[] pointing at deleted files
conflicts found  : 1     ← a decision contradicting an approved rule / CLAUDE.md
  [CONFLICT] CLAUDE.md: "Fallback is triggered only after timeout." vs <episode>
```

After `--apply`, check `inbox/`:
- `conflict-<date>-N.md` — governance record (existing rule vs new observation).
- `claude-md.proposed.patch` — unified diff that **annotates** the conflicting
  `CLAUDE.md` line with a `DREAM-CONFLICT` review marker. Close the loop:
- `dream-llm-<date>.report.md` — LLM dream evidence report when `bin/dream-llm.sh`
  or `MCE_LLM=1` was used.
- `memory-md.<date>.proposed.patch` — review-only proposed `MEMORY.md`
  consolidation for this run.
- `memory-md.proposed.patch` — latest alias for convenience.
- `memory-md.cumulative.proposed.md` — cumulative proposed `MEMORY.md` across
  LLM dream runs in this inbox.
- `memory-md.cumulative.proposed.patch` — diff from current `MEMORY.md` to the
  cumulative proposed memory.
- `global-memory.proposed.patch` — optional cross-project promotion proposal.
- `writeback-<date>.jsonl` — audited Mem0 writeback decisions. Review mode logs
  `would_write`; apply mode logs `written`, `skipped`, or `error`.

Mem0 writeback is explicit. It only writes `verified` / `repo-verified`
candidates, dedupes by stable candidate hash, applies the same secret filter as
`capture`, and delegates storage plus entity linking to Mem0.

```bash
git apply inbox/claude-md.proposed.patch     # only after you agree
# then actually rewrite the rule; the conflict clears on the next dream pass
```

The marker is a *review prompt*, not a fix — dream keeps flagging until a human
rewrites the rule (verified in e2e steps 4–5).

---

## Conflict detection — how it decides

Deterministic, **precision over recall**. A decision conflicts with a rule when:
1. they share ≥2 subject tokens (same topic), AND
2. the existing rule is **absolute** (`only` / `always` / `never` / …), AND
3. the new decision **widens/contradicts** it (`also` / `not only` / `instead` / …).

So "fallback **only** after timeout" vs "fallback must **also** fire on
health-check failure" → flagged; a decision that merely agrees, or is off-topic,
or contradicts a non-absolute rule → not flagged. Fuzzy conflicts are missed on
purpose (a human reviews each flag; we don't flood `inbox/`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No memory dir: ...` | pass an existing `--memory-dir` (needs `episodic/` or `*.md`) |
| stale/dedup/distill see nothing | frontmatter must use **block lists** (`- `), not inline `[...]` |
| `conflicts found: 0` but expected one | rule must be absolute (only/always/never) and decision must widen it |
| stale-path false positives | pass the correct `--repo-root` so relative paths resolve |
| `/code-dreaming clear` refuses parent memory | pass the exact project directory as `--repo-root`, or use `--allow-parent` only if clearing the parent workspace is intentional |
| stale-symbol false positives | use explicit `symbols:` metadata; heuristic body symbols are warning-only |
| LLM dream marks entries `[unverified]` | pass `--trajectory` or provide a supported local transcript/export |
| need to dream over an arbitrary folder | run `scripts/scan_to_dream.py DIR --output OUT.md`, then pass `--trajectory OUT.md` |
| repeated folder dream is too noisy | add `--since-manifest OLD.json --write-manifest NEW.json` and use the delta output |
| nightly skipped unexpectedly | use `MCE_FORCE=1` or increase `MCE_DREAM_INTERVAL_DAYS` |
| `conflicts found` keeps showing after patch | the marker is a prompt; rewrite the rule for real to clear it |
| capture says Mem0 missing | `pip install -e vendor/mem0` + configure `assets/mem0.config.yaml` |

## Scope
Only memory **hygiene** (5.3 + 5.4) + recall. L0 layering and the
tier/index *format* are native Claude Code behavior and were removed — see
[`../prd-remove.md`](../prd-remove.md).
