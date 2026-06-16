# Code-dreaming

Memory hygiene and project knowledge engine for AI coding agents. Native auto-memory only ever grows — Code-dreaming periodically summarizes, consolidates, and cleans it. It also indexes your source code and git history so every session starts with useful project structure data.

## Key Features

- **Dedup** — merges near-identical memory episodes to reduce noise
- **Stale-path validation** — flags memory entries that reference deleted files, preventing the agent from acting on "confidently wrong" information
- **Compression** — consolidates survivors into a compact dream index
- **Conflict detection** — finds decisions that contradict approved rules or `CLAUDE.md` and emits a review-required candidate with a proposed patch (never auto-applied)
- **Symbol verification** — optional `--verify-symbols` checks explicit symbol references and reports memory size against a health budget
- **Code structure index** — tree-sitter–powered SQLite index of functions, classes, imports, call graphs, and file coupling across your project
- **Git history analysis** — parses commit history, computes file-coupling Jaccard scores, surfaces frequently co-changed file pairs
- **Team sharing** — export/import compressed index snapshots so new clones start with project knowledge
- **Signal scan** — classifies trajectory evidence into corrections, preferences, decisions, and recurring patterns
- **SOP distillation** — mines repeated workflows into standard operating procedure candidates
- **Governed recall** — top-k retrieval under a token budget

## Why It Matters

AI coding agents accumulate memory that rots over time: duplicates pile up, and references to deleted files persist — the agent then trusts stale information and makes wrong decisions. Code-dreaming solves this by running periodic hygiene passes that clean, compress, and validate memory. The code index gives new sessions immediate project awareness (structure, symbols, coupling, recent activity) without waiting for the agent to rediscover it from scratch.

## Prerequisites

- Python 3.10+
- Git (for history analysis and file discovery)
- Claude Code CLI (for skill invocation and trajectory sources)

## Dependencies

**Required:**
- `pyyaml >= 6`
- `tree-sitter >= 0.23`

**Bundled language grammars (P0):**
- `tree-sitter-python >= 0.23`
- `tree-sitter-javascript >= 0.23`
- `tree-sitter-typescript >= 0.23`

**Optional:**
- `zstandard >= 0.21` — for compressed artifact export/import (team sharing)
- Mem0 backbone — for governed capture and writeback (`pip install -e vendor/mem0`)

## Quick Start

```bash
# Install the skill
bin/install-skill.sh --target both --mode copy

# Run a dream report (default skill invocation)
python3 scripts/dream_agent_report.py --repo-root .

# Run deterministic maintenance (dry-run by default)
python3 scripts/dream.py --memory-dir ~/.claude/projects/<key>/memory --repo-root .
python3 scripts/dream.py --memory-dir ~/.claude/projects/<key>/memory --repo-root . --apply

# Build the code index
python3 scripts/code_index.py --repo-root . --db .code-dreaming/code-index.db

# Parse git history into the index
python3 scripts/git_adapter.py --repo-root . --db .code-dreaming/code-index.db
```

## Usage

### On Demand

Invoke `/code-dreaming` in Claude Code to produce a dreaming summary report. Add free text after the command to steer the run:

```
/code-dreaming focus on coding-style preferences; ignore one-off debug notes
```

Use `/code-dreaming clear` to reset current-project local memory (dry-run first, then `--apply` with backup).

### Nightly (Unattended)

```bash
# Cron
0 2 * * *  cd /path/to/code-dreaming && MCE_APPLY=1 bash bin/dream-nightly.sh /path/to/repo

# Or via /schedule in Claude Code
/schedule create "code-dreaming nightly" --cron "0 2 * * *" \
  --task "Run: MCE_APPLY=1 bash bin/dream-nightly.sh /path/to/repo"
```

Start in dry-run for a week, read the reports, then enable `MCE_APPLY=1`.

### Code Index & Queries

```python
from scripts.code_queries import CodeQueries

with CodeQueries(".code-dreaming/code-index.db") as cq:
    cq.overview()          # project metrics
    cq.search("dream")     # FTS5 symbol search
    cq.file_symbols(path)  # all symbols in a file
    cq.callers("func")     # who calls this function
    cq.callees("func")     # what this function calls
    cq.coupling(path)      # frequently co-changed files
    cq.changes_since(date) # recent commit activity
```

### Team Sharing

```bash
# Export compressed snapshot (commit .code-dreaming/code-index.db.zst)
python3 -m mce.cli artifact export --db .code-dreaming/code-index.db

# On new clone, import snapshot
python3 -m mce.cli artifact import --input code-index.db.zst
```

## Supported Languages

| Tier | Languages | Status |
|------|-----------|--------|
| P0 (bundled) | Python, JavaScript, TypeScript | Full symbol + edge extraction |
| P1 (optional) | Go, Rust, Java, C, C++ | Install additional tree-sitter grammars |
| P2 (on-demand) | Shell, SQL, YAML, etc. | Text-only indexing (path + hash, no symbols) |

Missing grammars degrade gracefully: files are still indexed with path, size, and content hash.

## Governance

- `CLAUDE.md` and `AGENTS.md` are **never** auto-edited — conflicts produce review-only patches
- Capture is ADD-only, scoped, and secret-filtered
- Recall is budgeted (top-k under a token limit)
- Writeback is explicit and audited — only verified candidates are written
- All maintenance is **dry-run by default**; pass `--apply` to write changes
