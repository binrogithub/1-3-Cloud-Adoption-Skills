#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="both"
MODE="copy"
BUILD_DIR="$ROOT/dist/maas-dreaming"
CHECK_ONLY=0

usage() {
  cat <<'USAGE'
Usage: bin/install-skill.sh [--target codex|claude|both] [--mode copy|symlink] [--check]

Build and install maas-dreaming as a loadable skill.

Defaults:
  --target both
  --mode copy
  MCE_KEEP_SKILL_BACKUP=0

Flags:
  --check   Only check staleness; exit 1 if installed bundle differs from source.

Targets:
  codex  -> ${CODEX_HOME:-$HOME/.codex}/skills/maas-dreaming
  claude -> $HOME/.claude/skills/maas-dreaming
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$TARGET" in
  codex|claude|both) ;;
  *)
    echo "error: --target must be codex, claude, or both" >&2
    exit 2
    ;;
esac

case "$MODE" in
  copy|symlink) ;;
  *)
    echo "error: --mode must be copy or symlink" >&2
    exit 2
    ;;
esac

python3 "$ROOT/scripts/build_skill.py" --output "$BUILD_DIR" >/dev/null

# Staleness check: compare built bundle against installed destination.
check_stale() {
  local dest="$1"
  local stale=0
  if [ ! -d "$dest" ]; then
    echo "warning: no installed skill at $dest — run: bin/install-skill.sh" >&2
    stale=1
  elif ! diff -rq "$BUILD_DIR/scripts" "$dest/scripts" --exclude='__pycache__' >/dev/null 2>&1; then
    echo "warning: installed skill at $dest differs from source — run: bin/install-skill.sh" >&2
    stale=1
  fi
  return $stale
}

if [ "$CHECK_ONLY" = "1" ]; then
  exit_code=0
  if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
    if ! check_stale "${CODEX_HOME:-$HOME/.codex}/skills/maas-dreaming"; then
      exit_code=1
    fi
  fi
  if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
    if ! check_stale "$HOME/.claude/skills/maas-dreaming"; then
      exit_code=1
    fi
  fi
  exit $exit_code
fi

install_one() {
  local dest="$1"
  local parent
  parent="$(dirname "$dest")"
  mkdir -p "$parent"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ "${MCE_KEEP_SKILL_BACKUP:-0}" = "1" ]; then
      local stamp
      stamp="$(date +%Y%m%d-%H%M%S)"
      local backup_root
      backup_root="$parent/.skill-backups"
      mkdir -p "$backup_root"
      mv "$dest" "$backup_root/$(basename "$dest").bak-$stamp"
    else
      rm -rf "$dest"
    fi
  fi

  if [ "$MODE" = "symlink" ]; then
    ln -s "$BUILD_DIR" "$dest"
  else
    cp -a "$BUILD_DIR" "$dest"
  fi

  test -f "$dest/SKILL.md"
  echo "$dest"
}

if [ "$TARGET" = "codex" ] || [ "$TARGET" = "both" ]; then
  install_one "${CODEX_HOME:-$HOME/.codex}/skills/maas-dreaming"
fi

if [ "$TARGET" = "claude" ] || [ "$TARGET" = "both" ]; then
  install_one "$HOME/.claude/skills/maas-dreaming"
fi
