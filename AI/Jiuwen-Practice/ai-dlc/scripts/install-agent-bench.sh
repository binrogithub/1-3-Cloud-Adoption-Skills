#!/usr/bin/env bash
# G2 — install the pinned Harbor evaluation harness (host step, one time;
# PRD docs/prd-browser-verify-and-agent-bench.md §04 G2).
#
# Harbor is the official Terminal-Bench 2.0 evaluation framework
# (harbor-framework/harbor, `pip install harbor`).  This script installs
# it into an isolated Python venv under /opt/agent-bench (override via
# AI_DLC_AGENT_BENCH_ROOT) — never into the host's global site-packages,
# so it cannot collide with other Python projects.  It then writes a
# .aidlc-pin.json beside the venv recording tag + tree_sha256; the
# dispatch (agent_bench_pin_state in bin/plan.py) refuses to proceed if
# the pinned tree no longer matches (INV-36 — the technical enforcement
# of "no changes to upstream").
#
# Pure glue: only official upstream releases are installed, never forked
# or patched.  Idempotent: re-running after a pin version change upgrades
# the venv; a locally modified venv fails the digest check first — fix or
# re-pin deliberately, never blindly.
#
# The pin-writing logic is self-contained in this script (a Python heredoc
# computing a tree-wide sha256 over the whole venv directory) rather than
# factored into a shared helper, so this script touches no file another
# role's install script also edits.  The digest algorithm here MUST stay
# identical to agent_bench_tree_digest() in bin/plan.py — the pin and the
# check can never be allowed to drift apart.
#
# Usage:
#   scripts/install-agent-bench.sh [--tag 0.1.0] [--write-pin] [--uninstall]
set -euo pipefail

# pinned Harbor version — a single variable at the top so a bump is one
# line.  Harbor is a young package; pin the exact release the dispatch was
# validated against (INV-40: a recorded result names the version it ran).
HARBOR_VERSION="0.22.0"
TAG="$HARBOR_VERSION"
WRITE_PIN=1
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --write-pin) WRITE_PIN=1; shift ;;
    --no-pin) WRITE_PIN=0; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "install-agent-bench.sh: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

ROOT=${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}
PY=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3.9 || command -v python3)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
info() { echo -e "  $1"; }
die() { echo -e "${RED}✗${NC} install-agent-bench: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "runs as root (the venv is root-owned read-only)"

if [[ $UNINSTALL -eq 1 ]]; then
  # the rollback path (PRD §09): venv + pin — history records stay
  rm -rf "$ROOT"
  ok "removed $ROOT (bench-history records under /var/lib/aidlc/bench-history are kept as evidence)"
  exit 0
fi

[[ -x "$PY" ]] || die "no python >= 3.9 found"

# ── 1. the venv + Harbor ─────────────────────────────────────────────
mkdir -p "$ROOT"
if [[ ! -d "$ROOT/venv" ]]; then
  info "creating venv at $ROOT/venv"
  "$PY" -m venv "$ROOT/venv"
else
  info "venv already stands at $ROOT/venv"
fi
info "installing harbor==$TAG into the venv"
"$ROOT/venv/bin/pip" install --upgrade "harbor==$TAG"
# the entry point the pin-state check looks for (INV-36 expected path)
[[ -x "$ROOT/venv/bin/harbor" ]] \
  || die "pip install returned but $ROOT/venv/bin/harbor is not executable"
ok "harbor $TAG installed in $ROOT/venv"

# ── 2. the pin (INV-36/INV-37) ───────────────────────────────────────
# Self-contained: compute a tree-wide sha256 over the whole venv directory
# and write .aidlc-pin.json in the shape agent_bench_pin_state() expects.
# The digest algorithm below is identical to agent_bench_tree_digest() in
# bin/plan.py — keep them in sync.
if [[ $WRITE_PIN -eq 1 ]]; then
  ROOT="$ROOT" TAG="$TAG" "$PY" - <<'PYEOF'
import hashlib, json, os, pathlib, datetime
root = pathlib.Path(os.environ["ROOT"])
tag  = os.environ["TAG"]
venv = root / "venv"
lines = []
if venv.is_dir():
    for p in venv.rglob("*"):
        if p.is_file():
            try:
                d = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                continue
            lines.append(f"{d}  {p.relative_to(root).as_posix()}")
h = hashlib.sha256()
for line in sorted(lines):
    h.update(line.encode("utf-8") + b"\n")
tree_sha256 = h.hexdigest()
size_bytes = 0
for p in venv.rglob("*") if venv.is_dir() else []:
    if p.is_file():
        try:
            size_bytes += p.stat().st_size
        except OSError:
            pass
pin = {
    "tag": tag,
    "sha": None,                # no git sha — this is a pip install, not a clone
    "tree_sha256": tree_sha256,
    "sparse_paths": ["venv"],
    "installed_at": datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "size_bytes": size_bytes,
}
pin_file = root / ".aidlc-pin.json"
pin_file.write_text(json.dumps(pin, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
print(f"install-agent-bench: pin written — "
      f"{json.dumps({k: pin[k] for k in ('tag', 'size_bytes')})}")
PYEOF
  pin="$ROOT/.aidlc-pin.json"
  [[ -f "$pin" ]] || die "pin heredoc returned but no pin stands at $pin"
  # read-back assert: written is not standing until read back
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); assert d.get('tag') and d.get('tree_sha256'), 'pin missing tag or tree_sha256'; print('install-agent-bench: pin read-back ok —', d['tag'])" "$pin" \
    || die "the pin did not survive the read-back"
  ok "pin standing at $pin"
fi

ok "done — harbor $TAG in $ROOT/venv, pin $([[ -f $ROOT/.aidlc-pin.json ]] && echo standing || echo absent)"
