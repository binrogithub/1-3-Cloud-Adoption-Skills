#!/usr/bin/env bash
# Test the subagent-registration step of scripts/install-understand-anything.sh.
#
# Sets up a fake already-cloned pinned tree (with .git + tag v2.9.0) under a
# temp AI_DLC_UNDERSTAND_ANYTHING_ROOT, populates agents/*.md with fake agent
# definitions, then runs the install script with AI_DLC_JIUWENSWARM_AGENTS_DIR
# pointed at a temp location.  Asserts the agent files land with mode 0444 and
# correct content, and that a second run is idempotent (no failure, no
# duplication).
#
# Run:  tests/test_understand_anything_subagents.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

SCRIPT="$ROOT/scripts/install-understand-anything.sh"
[[ -f "$SCRIPT" ]] || { echo "FAIL: install script not found"; exit 1; }

# ── 1. fake pinned tree ──────────────────────────────────────────────
UA_ROOT="$T/ua-root"
AGENTS_SRC="$UA_ROOT/understand-anything-plugin/agents"
mkdir -p "$AGENTS_SRC"

# fake agent files with proper frontmatter (matches the real format)
cat > "$AGENTS_SRC/project-scanner.md" <<'EOF'
---
name: project-scanner
description: |
  Scans a codebase directory to produce a structured inventory.
---
# project-scanner

Scan the project and write scan-result.json.
EOF

cat > "$AGENTS_SRC/file-analyzer.md" <<'EOF'
---
name: file-analyzer
description: |
  Analyzes individual files to extract code-level nodes and edges.
---
# file-analyzer

Analyze files in batches and write batch-N.json.
EOF

cat > "$AGENTS_SRC/graph-reviewer.md" <<'EOF'
---
name: graph-reviewer
description: |
  Validates knowledge graphs for correctness, completeness, and quality.
---
# graph-reviewer

Review the assembled graph and render approval or rejection.
EOF

# make it look like an already-cloned git repo standing at the pin tag
git init -q "$UA_ROOT"
git -C "$UA_ROOT" config user.name test
git -C "$UA_ROOT" config user.email test@test
git -C "$UA_ROOT" add -A
git -C "$UA_ROOT" commit -q -m "fake pin"
git -C "$UA_ROOT" tag v2.9.0

# ── 2. temp destinations ─────────────────────────────────────────────
AGENTS_DST="$T/agents-dst"
SKILLS_DIR="$T/skills"
mkdir -p "$SKILLS_DIR"
# skills_state.json must exist with installed_plugins for step 4
python3 -c "import json,pathlib; pathlib.Path('$SKILLS_DIR/skills_state.json').write_text(json.dumps({'installed_plugins': []}))"

# ── 3. run the install script ───────────────────────────────────────
AI_DLC_UNDERSTAND_ANYTHING_ROOT="$UA_ROOT" \
AI_DLC_JIUWENSWARM_AGENTS_DIR="$AGENTS_DST" \
AI_DLC_SKILLS_DIR="$SKILLS_DIR" \
bash "$SCRIPT" > "$T/install.out" 2>&1 \
  || { echo "FAIL: install script exited non-zero"; cat "$T/install.out"; exit 1; }

# ── 4. assert agent files landed with mode 0444 and correct content ──
for name in project-scanner.md file-analyzer.md graph-reviewer.md; do
  dst="$AGENTS_DST/$name"
  [[ -f "$dst" ]] \
    || { echo "FAIL: $name not installed into $AGENTS_DST"; cat "$T/install.out"; exit 1; }
  # mode must be 0444 (r--r--r--)
  mode=$(stat -c '%a' "$dst")
  [[ "$mode" == "444" ]] \
    || { echo "FAIL: $name has mode $mode, want 444"; exit 1; }
  # content must match the source
  diff -q "$AGENTS_SRC/$name" "$dst" >/dev/null 2>&1 \
    || { echo "FAIL: $name content mismatch"; diff "$AGENTS_SRC/$name" "$dst"; exit 1; }
done

# the install output must mention registration
grep -q 'registered.*subagent' "$T/install.out" \
  || { echo "FAIL: install output does not mention subagent registration"; cat "$T/install.out"; exit 1; }

# ── 5. idempotent re-run ─────────────────────────────────────────────
# count files before re-run
before=$(find "$AGENTS_DST" -name '*.md' -type f | wc -l)

AI_DLC_UNDERSTAND_ANYTHING_ROOT="$UA_ROOT" \
AI_DLC_JIUWENSWARM_AGENTS_DIR="$AGENTS_DST" \
AI_DLC_SKILLS_DIR="$SKILLS_DIR" \
bash "$SCRIPT" > "$T/install2.out" 2>&1 \
  || { echo "FAIL: second install run exited non-zero"; cat "$T/install2.out"; exit 1; }

# count files after re-run — must be the same (no duplication)
after=$(find "$AGENTS_DST" -name '*.md' -type f | wc -l)
[[ "$before" == "$after" ]] \
  || { echo "FAIL: re-run changed file count ($before -> $after) — not idempotent"; exit 1; }

# content must still be correct after re-run (overwrite, not corrupt)
for name in project-scanner.md file-analyzer.md graph-reviewer.md; do
  diff -q "$AGENTS_SRC/$name" "$AGENTS_DST/$name" >/dev/null 2>&1 \
    || { echo "FAIL: $name content corrupted after re-run"; exit 1; }
done

# ── 6. uninstall removes the agents ──────────────────────────────────
AI_DLC_UNDERSTAND_ANYTHING_ROOT="$UA_ROOT" \
AI_DLC_JIUWENSWARM_AGENTS_DIR="$AGENTS_DST" \
AI_DLC_SKILLS_DIR="$SKILLS_DIR" \
bash "$SCRIPT" --uninstall > "$T/uninstall.out" 2>&1 \
  || { echo "FAIL: uninstall exited non-zero"; cat "$T/uninstall.out"; exit 1; }

for name in project-scanner.md file-analyzer.md graph-reviewer.md; do
  [[ ! -f "$AGENTS_DST/$name" ]] \
    || { echo "FAIL: $name still present after uninstall"; exit 1; }
done

echo "UNDERSTAND ANYTHING SUBAGENTS: pass (3 agents registered mode 0444, idempotent re-run, uninstall clean)"
