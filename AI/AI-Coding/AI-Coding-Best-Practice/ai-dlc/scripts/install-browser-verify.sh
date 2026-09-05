#!/usr/bin/env bash
# G1 — install the pinned Playwright MCP server + Chromium binary (host
# step, one time; PRD docs/prd-browser-verify-and-agent-bench.md §04).
#
# Everything this script does lands OUTSIDE the ai-dlc repo: the npm
# install at /opt/playwright-mcp (root-owned) and the Chromium binary
# Playwright downloads beside it.  The repo itself gains nothing but this
# script, the workspace skill it ships, and the pin it writes — no
# upstream source is copied in, no fork, no patch (INV-37).
#
# Local (not global) npm install: `npm install --prefix "$ROOT"` keeps
# @playwright/mcp self-contained under $ROOT/node_modules, isolated from
# the host's other npm projects.  The pin (.aidlc-pin.json) records
# tag + tree_sha256 over the whole installed tree; browser_verify_pin_state
# refuses the dispatch if the tree was modified after the pin (INV-36).
#
# Idempotent: re-running re-installs the pinned version and re-writes the
# pin.  A locally modified tree fails the digest check first — fix or
# re-pin deliberately, never blindly.
#
# Usage:
#   scripts/install-browser-verify.sh [--tag 1.0.0] [--write-pin]
#                                     [--uninstall]
set -euo pipefail

# the pinned @playwright/mcp npm version — a variable at the top so a
# bump is one-line.  This is an unmodified upstream release (INV-37).
PINNED_VERSION="0.0.80"
TAG="$PINNED_VERSION"
WRITE_PIN=1
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --write-pin) WRITE_PIN=1; shift ;;
    --no-pin) WRITE_PIN=0; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "install-browser-verify.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

ROOT=${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}
PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3.9)

say() { echo "install-browser-verify: $*"; }
die() { echo "install-browser-verify: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "runs as root (the tree is root-owned read-only)"

if [[ $UNINSTALL -eq 1 ]]; then
  # the rollback path (PRD §09): remove the tree and pin — records stay
  rm -rf "$ROOT"
  say "uninstalled (removed $ROOT)"
  exit 0
fi

# ── 1. the npm install (local, not global) ───────────────────────────
mkdir -p "$ROOT"
say "npm install @playwright/mcp@$TAG -> $ROOT (local, not global)"
npm install --prefix "$ROOT" "@playwright/mcp@$TAG"

# ── 2. the Chromium binary (Playwright's own download command) ───────
say "playwright install chromium (official binary download)"
"$ROOT/node_modules/.bin/playwright" install chromium

# ── 3. the pin — tree_sha256 over the whole installed tree ──────────
# Self-contained pin-writing (no shared helper): an inline Python walk
# that mirrors browser_verify_tree_digest in bin/plan.py byte-for-byte —
# every file under $ROOT except .aidlc-pin.json, sha256 of its bytes with
# its relative path, sorted, hashed.  The two must agree or the pin
# check will always mismatch; both exclude .aidlc-pin.json so writing the
# pin does not move the digest (chicken-and-egg).
if [[ $WRITE_PIN -eq 1 ]]; then
  [[ -x "$PY" ]] || die "no python >= 3.9 found"
  ROOT="$ROOT" TAG="$TAG" "$PY" - <<'PYEOF'
import hashlib, json, os, pathlib, datetime
root = pathlib.Path(os.environ["ROOT"])
tag = os.environ["TAG"]
lines = []
pin_name = ".aidlc-pin.json"
for p in sorted(root.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(root).as_posix()
    if rel == pin_name:
        continue
    try:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        continue
    lines.append(f"{digest}  {rel}")
h = hashlib.sha256()
for line in sorted(lines):
    h.update(line.encode("utf-8") + b"\n")
tree_sha256 = h.hexdigest()
size_bytes = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()
                 and p.relative_to(root).as_posix() != pin_name)
pin = {
    "tag": tag,
    "sha": None,
    "tree_sha256": tree_sha256,
    "sparse_paths": ["node_modules/@playwright/mcp"],
    "installed_at": datetime.datetime.now(
        datetime.timezone.utc).isoformat(),
    "size_bytes": size_bytes,
}
pin_file = root / pin_name
pin_file.write_text(json.dumps(pin, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
print(f"install-browser-verify: pin written — tag={pin['tag']} "
      f"size_bytes={pin['size_bytes']} tree_sha256={pin['tree_sha256'][:12]}…")
PYEOF
  pin="$ROOT/.aidlc-pin.json"
  [[ -f "$pin" ]] || die "pin write returned but no pin stands at $pin"
  # read-back assert: written is not standing until read back
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); assert d.get('tag') and d.get('tree_sha256'), 'pin missing fields'; print('install-browser-verify: pin read-back ok —', d['tag'])" "$pin" \
    || die "the pin did not survive the read-back"
fi

say "done — @playwright/mcp@$TAG + chromium at $ROOT, pin $([[ -f $ROOT/.aidlc-pin.json ]] && echo standing || echo absent)"
