#!/usr/bin/env bash
# C1 — deploy the pinned Understand-Anything skill tree (host step, one
# time; PRD docs/prd-codegraph-understand-anything-backend.md §04).
#
# Everything this script does lands OUTSIDE the ai-dlc repo: the tree
# at /opt/understand-anything (read-only, root-owned), one allow entry
# in the gateway's config, and one pointer skill in the gateway workspace.
# The repo itself gains nothing but this script, the skill it installs
# and the pin it writes — no upstream content is ever copied in (G-E).
#
# Idempotent: every step checks before it acts. Re-running after a pin
# tag change upgrades the tree; a locally modified tree fails the
# digest check first (I3) — fix or re-pin deliberately, never blindly.
#
# Usage:
#   scripts/install-understand-anything.sh [--tag v2.9.0]
#                                         [--write-pin] [--skill-only]
#                                         [--uninstall]
set -euo pipefail

TAG="v2.9.0"
WRITE_PIN=0
SKILL_ONLY=0
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --write-pin) WRITE_PIN=1; shift ;;
    --skill-only) SKILL_ONLY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "install-understand-anything.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

ROOT=${AI_DLC_UNDERSTAND_ANYTHING_ROOT:-/opt/understand-anything}
URL=${AI_DLC_UNDERSTAND_ANYTHING_URL:-https://github.com/Egonex-AI/Understand-Anything.git}
SPARSE_PATHS=(understand-anything-plugin)
GW_CONFIG="$HOME/.jiuwenswarm/config/config.yaml"
SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)/supervisor/skills/workspace/codegraph/SKILL.md"
SKILLS_DIR="${AI_DLC_SKILLS_DIR:-$HOME/.jiuwenswarm/agent/workspace/skills}"
PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3.9)
PLAN="$(cd "$(dirname "$0")/.." && pwd)/bin/plan.py"

say() { echo "install-understand-anything: $*"; }
die() { echo "install-understand-anything: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "runs as root (the tree is root-owned read-only)"

if [[ $UNINSTALL -eq 1 ]]; then
  # the rollback path (PRD §09): tree, config entry, skill — records stay
  # remove registered subagents BEFORE the tree is gone — derive the
  # basename list from the pinned tree if it still stands, else fall
  # back to the known set so a second uninstall (tree already removed)
  # still cleans up (PRD §05 idempotent)
  AGENTS_DST="${AI_DLC_JIUWENSWARM_AGENTS_DIR:-$HOME/.jiuwenswarm/agents}"
  AGENTS_SRC="$ROOT/understand-anything-plugin/agents"
  if [[ -d "$AGENTS_SRC" ]]; then
    agent_names=()
    for f in "$AGENTS_SRC"/*.md; do [[ -f "$f" ]] && agent_names+=("$(basename "$f")"); done
  else
    # tree already gone — fall back to the known Understand-Anything
    # agent basenames (v2.9.0); only remove these, never touch unrelated
    # user agents in the shared directory
    agent_names=(
      architecture-analyzer.md article-analyzer.md assemble-reviewer.md
      design-analyzer.md domain-analyzer.md file-analyzer.md
      graph-reviewer.md knowledge-graph-guide.md project-scanner.md
      tour-builder.md
    )
  fi
  removed=0
  for name in "${agent_names[@]}"; do
    if [[ -f "$AGENTS_DST/$name" ]]; then
      rm -f "$AGENTS_DST/$name"
      removed=$((removed + 1))
    fi
  done
  say "removed $removed registered subagent(s) from $AGENTS_DST"
  rm -rf "$ROOT"
  rm -rf "$SKILLS_DIR/codegraph"
  "$PY" - "$GW_CONFIG" <<'PYEOF'
import json, sys, pathlib
cfg = pathlib.Path(sys.argv[1])
t = cfg.read_text()
want = '    "/opt/understand-anything": "allow"\n'
if want in t:
    cfg.write_text(t.replace(want, ""))
    print("install-understand-anything: config entry removed")
else:
    print("install-understand-anything: config entry already absent")
PYEOF
  "$PY" - "$SKILLS_DIR/skills_state.json" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
st = json.loads(p.read_text())
before = len(st.get("installed_plugins", []))
st["installed_plugins"] = [x for x in st.get("installed_plugins", [])
                           if x.get("name") != "codegraph"]
p.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
print(f"install-understand-anything: registration removed "
      f"({before} -> {len(st['installed_plugins'])})")
PYEOF
  say "uninstalled (records under /var/lib/aidlc/records are kept as evidence)"
  exit 0
fi

# ── 1. the tree: sparse clone, or pin check on an existing one ───────
if [[ $SKILL_ONLY -eq 0 ]]; then
  if [[ ! -d "$ROOT/.git" ]]; then
    say "sparse clone $URL @ $TAG -> $ROOT"
    # the repo is small (~16 files in the plugin subtree); blobless +
    # sparse + depth 1 keeps the clone minimal
    git clone --filter=blob:none --sparse --depth 1 --branch "$TAG" \
        "$URL" "$ROOT"
  else
    standing=$(git -C "$ROOT" describe --tags --exact-match 2>/dev/null || true)
    [[ "$standing" == "$TAG" ]] \
      || die "tree stands at '${standing:-untagged}'; pin wants $TAG — upgrade deliberately (edit the pin tag and re-run), never blindly"
    say "tree already stands at $TAG"
  fi

  # git 2.27 writes the dir list WITHOUT the /* and !/*/ header
  # patterns — the cone file is written by hand
  git -C "$ROOT" config core.sparseCheckout true
  git -C "$ROOT" config core.sparseCheckoutCone true
  printf '/*\n!/*/\n' > "$ROOT/.git/info/sparse-checkout"
  for p in "${SPARSE_PATHS[@]}"; do printf '/%s/\n' "$p" >> "$ROOT/.git/info/sparse-checkout"; done
  git -C "$ROOT" sparse-checkout reapply

  # I3: read-only for everyone; the role reads, nobody writes (PRD INV-10)
  chown -R root:root "$ROOT"
  find "$ROOT" -type d -exec chmod 0555 {} +
  find "$ROOT" -type f -exec chmod 0444 {} +

  # ── 1b. register Understand-Anything subagents with jiuwenswarm ────
  # copy agents/*.md into ~/.jiuwenswarm/agents/ (the "user" layer that
  # AgentConfigService scans) so the Task tool can resolve subagent_type
  # names like project-scanner, file-analyzer, etc. (PRD §04).  Read-only
  # (INV-11), idempotent overwrite (INV-13), skip-not-fail if the agents
  # directory is absent (PRD §05 reverse gate).
  AGENTS_SRC="$ROOT/understand-anything-plugin/agents"
  AGENTS_DST="${AI_DLC_JIUWENSWARM_AGENTS_DIR:-$HOME/.jiuwenswarm/agents}"
  if [[ -d "$AGENTS_SRC" ]]; then
    mkdir -p "$AGENTS_DST"
    registered=0
    for f in "$AGENTS_SRC"/*.md; do
      [[ -f "$f" ]] || continue
      install -D -m 0444 "$f" "$AGENTS_DST/$(basename "$f")"
      registered=$((registered + 1))
    done
    say "registered $registered subagent(s) into $AGENTS_DST"
  else
    say "agents/ directory not found under the pinned tree — skipping subagent registration"
  fi
fi

# ── 2. the pin (C1) ─────────────────────────────────────────────────
if [[ $WRITE_PIN -eq 1 ]]; then
  [[ -x "$PY" ]] || die "no python >= 3.9 found"
  "$PY" "$PLAN" codegraph-pin --root "$ROOT" --tag "$TAG" --write
  pin="$ROOT/.aidlc-pin.json"
  [[ -f "$pin" ]] || die "--write-pin returned but no pin stands at $pin"
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print('install-understand-anything: pin written —', json.dumps({k: d[k] for k in ('tag','sha','size_bytes')}))" "$pin"
fi

# ── 3. the gateway config: one allow entry, backup first ────────────
# config.yaml is hand-edited; any "regenerate" would clobber it (the
# litellm side already paid that price) — so: copy aside, insert one
# line, read the file back and assert the entry stands
if [[ -f "$GW_CONFIG" ]] && ! grep -q '^    "/opt/understand-anything": "allow"' "$GW_CONFIG"; then
  cp "$GW_CONFIG" "$GW_CONFIG.bak.$(date +%s)"
  GW_CONFIG="$GW_CONFIG" "$PY" - <<'PYEOF'
import os, pathlib, sys
cfg = pathlib.Path(os.environ["GW_CONFIG"])
lines = cfg.read_text().splitlines(keepends=True)
entry = '    "/opt/understand-anything": "allow"\n'
out, seen, inserted = [], False, False
for line in lines:
    out.append(line)
    if not seen and line.strip() == "external_directory:":
        out.append(entry)
        inserted = True
    if entry in line:
        seen = True
if not seen and not inserted:
    sys.exit("no permissions.external_directory block found — add the entry by hand")
cfg.write_text("".join(out))
PYEOF
  # the read-back assert: written is not standing until read back
  grep -q '^    "/opt/understand-anything": "allow"' "$GW_CONFIG" \
    || die "the config entry did not survive the read-back"
  say "config: /opt/understand-anything allowed (backup taken)"
else
  say "config: entry already stands (or no config to edit)"
fi

# ── 4. the pointer skill (C1) — one entry, +1 only ──────────────────
[[ -f "$SKILL_SRC" ]] || die "skill source missing: $SKILL_SRC"
install -D -m 0644 "$SKILL_SRC" "$SKILLS_DIR/codegraph/SKILL.md"
SKILLS_DIR="$SKILLS_DIR" "$PY" - <<'PYEOF'
import datetime, json, os, pathlib
p = pathlib.Path(os.environ["SKILLS_DIR"]) / "skills_state.json"
st = json.loads(p.read_text())
plug = st.setdefault("installed_plugins", [])
if not any(x.get("name") == "codegraph" for x in plug):
    plug.append({"name": "codegraph", "marketplace": "builtin",
                 "version": "", "commit": "",
                 "source": "ai-dlc supervisor/skills/workspace/codegraph",
                 "installed_at": datetime.datetime.now(
                     datetime.timezone.utc).isoformat()})
    p.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
    print(f"install-understand-anything: registered codegraph ({len(plug)} plugins)")
else:
    print("install-understand-anything: codegraph already registered")
PYEOF
read_back=$(SKILLS_DIR="$SKILLS_DIR" "$PY" -c "import json,os; st=json.load(open(os.path.join(os.environ['SKILLS_DIR'],'skills_state.json'))); print(sum(1 for x in st['installed_plugins'] if x.get('name')=='codegraph'))")
[[ "$read_back" == "1" ]] || die "registration read-back found '$read_back' entries — refusing"
_agents_count=0
if [[ $SKILL_ONLY -eq 0 && -d "$ROOT/understand-anything-plugin/agents" ]]; then
  _agents_count=$(ls "$ROOT/understand-anything-plugin/agents"/*.md 2>/dev/null | wc -l)
fi
say "done — tree $TAG, pin $([[ -f $ROOT/.aidlc-pin.json ]] && echo standing || echo absent), skill installed, $_agents_count subagent(s) registered"
