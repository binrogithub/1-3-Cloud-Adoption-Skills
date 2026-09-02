#!/usr/bin/env bash
# N6 — deploy the pinned OpenDesign reference tree (host step, one
# time; PRD docs/prd-uidesigner-opendesign.md §9).
#
# Everything this script does lands OUTSIDE the ai-dlc repo: the tree
# at /opt/open-design (read-only, root-owned), one allow entry in the
# gateway's config, and one pointer skill in the gateway workspace.
# The repo itself gains nothing but this script, the skill it installs
# and the pin it writes — no upstream content is ever copied in (G-E).
#
# Idempotent: every step checks before it acts. Re-running after a pin
# tag change upgrades the tree; a locally modified tree fails the
# digest check first (I3) — fix or re-pin deliberately, never blindly.
#
# Usage:
#   scripts/install-opendesign.sh [--tag open-design-vX.Y.Z]
#                                 [--write-pin] [--skill-only]
#                                 [--uninstall]
set -euo pipefail

TAG="open-design-v0.21.1"
WRITE_PIN=0
SKILL_ONLY=0
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --write-pin) WRITE_PIN=1; shift ;;
    --skill-only) SKILL_ONLY=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "install-opendesign.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

ROOT=${AI_DLC_OPENDESIGN_ROOT:-/opt/open-design}
URL=${AI_DLC_OPENDESIGN_URL:-https://github.com/nexu-io/open-design}
SPARSE_PATHS=(skills design-templates design-systems)
GW_CONFIG="$HOME/.jiuwenswarm/config/config.yaml"
SKILL_SRC="$(cd "$(dirname "$0")/.." && pwd)/supervisor/skills/workspace/ui-designer/SKILL.md"
SKILLS_DIR="${AI_DLC_SKILLS_DIR:-$HOME/.jiuwenswarm/agent/workspace/skills}"
PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3.9)
PLAN="$(cd "$(dirname "$0")/.." && pwd)/bin/plan.py"

say() { echo "install-opendesign: $*"; }
die() { echo "install-opendesign: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "runs as root (the tree is root-owned read-only)"

if [[ $UNINSTALL -eq 1 ]]; then
  # the rollback path (PRD §13): tree, config entry, skill — records stay
  rm -rf "$ROOT"
  rm -rf "$SKILLS_DIR/ui-designer"
  "$PY" - "$GW_CONFIG" <<'PYEOF'
import json, sys, pathlib
cfg = pathlib.Path(sys.argv[1])
t = cfg.read_text()
want = '    "/opt/open-design": "allow"\n'
if want in t:
    cfg.write_text(t.replace(want, ""))
    print("install-opendesign: config entry removed")
else:
    print("install-opendesign: config entry already absent")
PYEOF
  "$PY" - "$SKILLS_DIR/skills_state.json" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
st = json.loads(p.read_text())
before = len(st.get("installed_plugins", []))
st["installed_plugins"] = [x for x in st.get("installed_plugins", [])
                           if x.get("name") != "ui-designer"]
p.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
print(f"install-opendesign: registration removed "
      f"({before} -> {len(st['installed_plugins'])})")
PYEOF
  say "uninstalled (records under /var/lib/aidlc/records are kept as evidence)"
  exit 0
fi

# ── 1. the tree: sparse clone, or pin check on an existing one ───────
if [[ $SKILL_ONLY -eq 0 ]]; then
  if [[ ! -d "$ROOT/.git" ]]; then
    say "sparse clone $URL @ $TAG -> $ROOT"
    # E3: the full repo is 1.8 GB; blobless + sparse + depth 1 measured
    # 138M on this host (P0 probe 1)
    git clone --filter=blob:none --sparse --depth 1 --branch "$TAG" \
        "$URL" "$ROOT"
  else
    standing=$(git -C "$ROOT" describe --tags --exact-match 2>/dev/null || true)
    [[ "$standing" == "$TAG" ]] \
      || die "tree stands at '${standing:-untagged}'; pin wants $TAG — upgrade deliberately (edit the pin tag and re-run), never blindly"
    say "tree already stands at $TAG"
  fi

  # git 2.27 writes the dir list WITHOUT the /* and !/*/ header
  # patterns, leaving apps/ docs/ plugins/ packages/ on disk (measured,
  # P0 findings) — the five-line cone file is written by hand
  git -C "$ROOT" config core.sparseCheckout true
  git -C "$ROOT" config core.sparseCheckoutCone true
  printf '/*\n!/*/\n' > "$ROOT/.git/info/sparse-checkout"
  for p in "${SPARSE_PATHS[@]}"; do printf '/%s/\n' "$p" >> "$ROOT/.git/info/sparse-checkout"; done
  git -C "$ROOT" sparse-checkout reapply
  for stray in apps docs plugins packages; do
    [[ ! -e "$ROOT/$stray" ]] || die "'$stray' stands in the worktree — the sparse set did not apply cleanly"
  done

  # I3: read-only for everyone; the role reads, nobody writes
  chown -R root:root "$ROOT"
  find "$ROOT" -type d -exec chmod 0555 {} +
  find "$ROOT" -type f -exec chmod 0444 {} +
fi

# ── 2. the pin (N3) ─────────────────────────────────────────────────
if [[ $WRITE_PIN -eq 1 ]]; then
  [[ -x "$PY" ]] || die "no python >= 3.9 found"
  "$PY" "$PLAN" design-pin --root "$ROOT" --tag "$TAG" --write
  pin="$ROOT/.aidlc-pin.json"
  [[ -f "$pin" ]] || die "--write-pin returned but no pin stands at $pin"
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print('install-opendesign: pin written —', json.dumps({k: d[k] for k in ('tag','sha','size_bytes')}))" "$pin"
fi

# ── 3. the gateway config: one allow entry, backup first ────────────
# config.yaml is hand-edited; any "regenerate" would clobber it (the
# litellm side already paid that price) — so: copy aside, insert one
# line, read the file back and assert the entry stands
if [[ -f "$GW_CONFIG" ]] && ! grep -q '^    "/opt/open-design": "allow"' "$GW_CONFIG"; then
  cp "$GW_CONFIG" "$GW_CONFIG.bak.$(date +%s)"
  GW_CONFIG="$GW_CONFIG" "$PY" - <<'PYEOF'
import os, pathlib, sys
cfg = pathlib.Path(os.environ["GW_CONFIG"])
lines = cfg.read_text().splitlines(keepends=True)
entry = '    "/opt/open-design": "allow"\n'
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
  grep -q '^    "/opt/open-design": "allow"' "$GW_CONFIG" \
    || die "the config entry did not survive the read-back"
  say "config: /opt/open-design allowed (backup taken)"
else
  say "config: entry already stands (or no config to edit)"
fi

# ── 4. the pointer skill (N2) — one entry, +1 only ──────────────────
[[ -f "$SKILL_SRC" ]] || die "skill source missing: $SKILL_SRC"
install -D -m 0644 "$SKILL_SRC" "$SKILLS_DIR/ui-designer/SKILL.md"
SKILLS_DIR="$SKILLS_DIR" "$PY" - <<'PYEOF'
import datetime, json, os, pathlib
p = pathlib.Path(os.environ["SKILLS_DIR"]) / "skills_state.json"
st = json.loads(p.read_text())
plug = st.setdefault("installed_plugins", [])
if not any(x.get("name") == "ui-designer" for x in plug):
    plug.append({"name": "ui-designer", "marketplace": "builtin",
                 "version": "", "commit": "",
                 "source": "ai-dlc supervisor/skills/workspace/ui-designer",
                 "installed_at": datetime.datetime.now(
                     datetime.timezone.utc).isoformat()})
    p.write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
    print(f"install-opendesign: registered ui-designer ({len(plug)} plugins)")
else:
    print("install-opendesign: ui-designer already registered")
PYEOF
read_back=$(SKILLS_DIR="$SKILLS_DIR" "$PY" -c "import json,os; st=json.load(open(os.path.join(os.environ['SKILLS_DIR'],'skills_state.json'))); print(sum(1 for x in st['installed_plugins'] if x.get('name')=='ui-designer'))")
[[ "$read_back" == "1" ]] || die "registration read-back found '$read_back' entries — refusing"
say "done — tree $TAG, pin $([[ -f $ROOT/.aidlc-pin.json ]] && echo standing || echo absent), skill installed"
