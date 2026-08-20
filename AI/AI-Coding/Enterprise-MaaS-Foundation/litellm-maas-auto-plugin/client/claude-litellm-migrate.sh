#!/usr/bin/env bash
set -euo pipefail

# claude-litellm-migrate.sh — safely migrate from the old global-remapping setup.
#
# Removes ONLY values proven to belong to the old integration from
# ~/.claude/settings.json and ~/.claude.json. Preserves unrelated env keys,
# OAuth state, themes, MCP configuration, project state, and user preferences.
#
# PRD: docs/PRD-release-closure-native-claude-litellm.md §3.3 (Safe migration)
#
# Usage:
#   claude-litellm-migrate.sh --dry-run            # show what would change
#   claude-litellm-migrate.sh --apply              # apply with timestamped backup
#   claude-litellm-migrate.sh --apply --old-base-url URL   # match a specific gateway
#   claude-litellm-migrate.sh --apply --old-key-fingerprint HASH  # match a specific key

DRY_RUN=1
APPLY=0
OLD_BASE_URL="${CLAUDE_LITELLM_OLD_BASE_URL:-}"
OLD_KEY_FP="${CLAUDE_LITELLM_OLD_KEY_FP:-}"
CLAUDE_DIR="${HOME}/.claude"
SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
CLAUDE_JSON="${HOME}/.claude.json"

# Legacy env keys the old integration wrote (from configure-claude-code.sh).
LEGACY_KEYS=(
  ANTHROPIC_BASE_URL
  ANTHROPIC_API_KEY
  ANTHROPIC_AUTH_TOKEN
  ANTHROPIC_MODEL
  ANTHROPIC_DEFAULT_OPUS_MODEL
  ANTHROPIC_DEFAULT_SONNET_MODEL
  ANTHROPIC_DEFAULT_HAIKU_MODEL
  ANTHROPIC_SMALL_FAST_MODEL
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
)

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
Usage: claude-litellm-migrate.sh [options]

Options:
  --dry-run                 Show what would change without writing (default).
  --apply                   Apply changes with a timestamped backup.
  --old-base-url URL        Match only this exact LiteLLM gateway URL.
  --old-key-fingerprint HASH  Match only this exact gateway key (full 64-char
                            SHA-256). Required to remove legacy credentials.
  --help                    Show this help.

This script removes only values proven to belong to the old integration:
  - ANTHROPIC_BASE_URL matching --old-base-url exactly
  - ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN matching --old-key-fingerprint
    (full 64-char SHA-256 — never a prefix)
  - ANTHROPIC_DEFAULT_OPUS_MODEL / SONNET / HAIKU / SMALL_FAST_MODEL mappings
  - ANTHROPIC_MODEL set to claude-glm-5.2 or claude-*

Model mappings are removed by exact value match. Legacy URL and credential
fields are NOT removed without exact ownership evidence (--old-base-url and
--old-key-fingerprint). A plain --apply without these flags only removes model
mappings; it does NOT complete migration if legacy URL/credentials remain.

It preserves unrelated env keys, OAuth state, themes, MCP config, and user
preferences. It does NOT delete the entire env object. It preserves the
original file owner, group, and mode — running as root does not take ownership
of another user's configuration.

Repeated --apply is a no-op. Migration failure leaves original files
byte-identical and exits nonzero.
EOF
}

# ── Parse arguments ───────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; APPLY=0; shift ;;
        --apply) APPLY=1; DRY_RUN=0; shift ;;
        --old-base-url) OLD_BASE_URL="$2"; shift 2 ;;
        --old-key-fingerprint) OLD_KEY_FP="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

# ── Compute the migration plan via python3 ───────────────────────────────────
# Python does the JSON manipulation: read settings.json + .claude.json,
# identify old-integration-owned values, and either print the plan (dry-run)
# or apply with backup (apply).

python3 - "$SETTINGS_FILE" "$CLAUDE_JSON" "$DRY_RUN" "$APPLY" "$OLD_BASE_URL" "$OLD_KEY_FP" <<'PYEOF'
import sys
import json
import os
import hashlib
import tempfile
import shutil
import stat
from pathlib import Path

settings_path = Path(sys.argv[1])
claude_json_path = Path(sys.argv[2])
dry_run = sys.argv[3] == "1"
apply = sys.argv[4] == "1"
old_base_url = sys.argv[5] if sys.argv[5] else None
old_key_fp = sys.argv[6] if sys.argv[6] else None

# Legacy keys the old integration wrote.
LEGACY_KEYS = {
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
}

# Keys whose VALUE indicates old-integration ownership (model mappings to GLM).
MODEL_MAPPING_KEYS = {
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
}

OLD_MODEL_VALUES = {"claude-glm-5.2", "claude-*", "glm-5.2", "glm-5.1"}


def is_old_value(key, value):
    """True if this env value is proven to belong to the old integration.

    PRD §3.2: Never infer credential ownership from a prefix. Without an exact
    full SHA-256 gateway-key fingerprint, preserve API/auth credentials and
    report them as unresolved manual review items. Match the old base URL
    exactly — if no exact URL is supplied, preserve it.
    """
    if value is None:
        return False
    sval = str(value)
    if key == "ANTHROPIC_BASE_URL":
        # Match the old LiteLLM gateway URL EXACTLY. If no exact URL is
        # supplied, do NOT infer from :4000 — preserve it (manual review).
        if old_base_url:
            return sval == old_base_url
        return False  # no exact URL → preserve (manual review)
    if key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        # Match the old gateway credential by EXACT full 64-char SHA-256
        # fingerprint only. Never infer from a prefix (sk-*, sk-ant-*) —
        # that can remove a user's native Anthropic key (PRD §3.2).
        if old_key_fp:
            if len(old_key_fp) != 64:
                return False  # invalid fingerprint length → preserve
            return hashlib.sha256(sval.encode()).hexdigest() == old_key_fp
        return False  # no fingerprint → preserve (manual review)
    if key in MODEL_MAPPING_KEYS:
        # Model mappings are safe to remove by exact value match — these
        # values (claude-glm-5.2, claude-*, glm-*) were only ever written by
        # the old integration. Native Claude model values survive.
        return sval in OLD_MODEL_VALUES
    if key == "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC":
        return sval in ("1", "true", "yes")
    return False


def redact(key, value):
    """Redact sensitive values for dry-run output — print only the field name
    and fingerprint, never a credential prefix (PRD §3.2)."""
    if key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") and value:
        fp = hashlib.sha256(str(value).encode()).hexdigest()
        return "[redacted, fp=%s]" % fp
    return value


def compute_env_removals(env):
    """Return list of (key, old_value) to remove from the env dict."""
    if not isinstance(env, dict):
        return []
    removals = []
    for key in sorted(LEGACY_KEYS):  # deterministic order (PRD §3.2)
        if key in env and is_old_value(key, env[key]):
            removals.append((key, env[key]))
    return removals


def check_target_safe(path, description):
    """P0 (PRD §3.2): Require every existing target to be a regular,
    non-symlink file owned by the invoking user. Wrong ownership exits nonzero
    before any backup or write. A symlink target is also refused.
    """
    if not path.exists():
        return  # absent targets are fine (nothing to migrate)
    try:
        st = os.lstat(str(path))
    except OSError as e:
        print("  FAIL: cannot stat %s (%s): %s" % (description, path, e), file=sys.stderr)
        sys.exit(1)
    import stat as _stat
    if _stat.S_ISLNK(st.st_mode):
        print("  FAIL: %s (%s) is a symlink — refusing to migrate." % (description, path), file=sys.stderr)
        sys.exit(1)
    if not _stat.S_ISREG(st.st_mode):
        print("  FAIL: %s (%s) is not a regular file — refusing to migrate." % (description, path), file=sys.stderr)
        sys.exit(1)
    if st.st_uid != os.getuid():
        print("  FAIL: %s (%s) is owned by uid %d, not the invoking user (uid %d)." % (description, path, st.st_uid, os.getuid()), file=sys.stderr)
        print("  Refusing to take ownership of another user's Claude configuration.", file=sys.stderr)
        sys.exit(1)


def parse_file(path, description):
    """Parse a JSON file. Returns (data, env, removals) or raises on error.

    PRD §3.2: Parse and validate every target file before writing any file.
    Parse failures exit nonzero.
    """
    if not path.exists():
        return None, None, []
    try:
        with path.open("r", encoding="utf-8") as f:
            content = f.read()
        data = json.loads(content)
    except (OSError, ValueError) as e:
        print("  FAIL: cannot parse %s (%s): %s" % (description, path, e), file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        return data, None, []

    env = data.get("env")
    if not isinstance(env, dict):
        return data, None, []

    removals = compute_env_removals(env)
    return data, env, removals


def print_dry_run(path, description, removals):
    """Print the dry-run plan for one file."""
    if not removals:
        return
    print("  %s (%s):" % (description, path))
    for key, old_val in removals:
        print("    remove %s = %s" % (key, redact(key, old_val)))


def make_backup(path, description, backup_ts):
    """P0 (PRD §3.2): Create a mode-0600 backup with umask 077 and fsync it so
    the backup is durable before any target is replaced. Returns the backup
    path and the original (uid, gid, mode) for preservation on write.
    """
    backup = path.with_suffix(path.suffix + ".migrate-backup.%d" % backup_ts)
    try:
        # umask 077 ensures the backup is never briefly world/group-readable
        # before chmod (PRD §3.2).
        old_umask = os.umask(0o077)
        try:
            shutil.copy2(str(path), str(backup))
            os.chmod(str(backup), 0o600)
        finally:
            os.umask(old_umask)
        # fsync the backup so it is durable on disk before we touch the target.
        with open(str(backup), "rb") as bf:
            os.fsync(bf.fileno())
    except OSError as e:
        print("  FAIL: cannot backup %s: %s" % (path, e), file=sys.stderr)
        raise
    st = os.lstat(str(path))
    return backup, (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode))


def write_target(path, description, data, env, removals, orig_meta):
    """Apply removals to one file atomically, preserving original uid/gid/mode.

    PRD §3.2: temp + rename + fsync; preserve original ownership and mode so
    running as root does not silently take ownership of another user's config.
    """
    for key, _ in removals:
        env.pop(key, None)
    if not env:
        data.pop("env", None)
    orig_uid, orig_gid, orig_mode = orig_meta
    try:
        old_umask = os.umask(0o077)
        try:
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        finally:
            os.umask(old_umask)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        # Preserve original mode, uid, gid (PRD §3.2).
        os.chmod(tmp, orig_mode)
        try:
            os.chown(tmp, orig_uid, orig_gid)
        except OSError:
            pass
        os.replace(tmp, str(path))
        try:
            os.chown(str(path), orig_uid, orig_gid)
        except OSError:
            pass
        os.chmod(str(path), orig_mode)
    except OSError as e:
        print("  FAIL: cannot write %s: %s" % (path, e), file=sys.stderr)
        raise


def restore_target(path, backup, orig_meta):
    """P0 (PRD §3.2): Restore a target from its backup and VERIFY the restored
    content matches the backup byte-for-byte. A failed rollback is a distinct
    nonzero hard error. Returns True on verified success, False on failure.
    """
    try:
        shutil.copy2(str(backup), str(path))
        orig_uid, orig_gid, orig_mode = orig_meta
        try:
            os.chown(str(path), orig_uid, orig_gid)
        except OSError:
            pass
        os.chmod(str(path), orig_mode)
        with open(str(path), "rb") as af, open(str(backup), "rb") as bf:
            if af.read() != bf.read():
                return False
        return True
    except OSError:
        return False


print("=== claude-litellm migration ===")
if dry_run:
    print("  (dry-run — no changes will be made)")
    print()

# P0: Validate fingerprint if supplied (PRD §3.2 — exactly 64 hex chars).
# Reject non-hex characters explicitly; a 64-char non-hex string is not a
# valid SHA-256 fingerprint.
if old_key_fp:
    if len(old_key_fp) != 64:
        print("  FAIL: --old-key-fingerprint must be exactly 64 hex characters (got %d)." % len(old_key_fp), file=sys.stderr)
        sys.exit(1)
    try:
        int(old_key_fp, 16)
    except ValueError:
        print("  FAIL: --old-key-fingerprint must be 64 hexadecimal characters (non-hex characters found).", file=sys.stderr)
        sys.exit(1)

# Phase 1: Parse ALL files first (PRD §3.2 — parse before any write).
files = [
    (settings_path, "settings.json"),
    (claude_json_path, ".claude.json"),
]
parsed = []
for path, desc in files:
    # P0: ownership/symlink/regular-file check before any write (PRD §3.2).
    check_target_safe(path, desc)
    data, env, removals = parse_file(path, desc)
    parsed.append((path, desc, data, env, removals))

all_removals = [r for _, _, _, _, removals in parsed for r in removals]

# Detect unresolved legacy URL/credential fields (PRD §3.2): these exist but
# cannot be proven old-integration-owned without exact ownership evidence.
unresolved = []
for path, desc, data, env, _ in parsed:
    if env and isinstance(env, dict):
        if "ANTHROPIC_BASE_URL" in env and not (old_base_url and is_old_value("ANTHROPIC_BASE_URL", env["ANTHROPIC_BASE_URL"])):
            unresolved.append((desc, "ANTHROPIC_BASE_URL", redact("ANTHROPIC_BASE_URL", env["ANTHROPIC_BASE_URL"])))
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            if key in env and not (old_key_fp and is_old_value(key, env[key])):
                unresolved.append((desc, key, redact(key, env[key])))

if not all_removals and not unresolved:
    print("  No old-integration values found. Nothing to migrate.")
    sys.exit(0)

# P0: --apply requires exact ownership evidence when legacy URL/credentials
# exist (PRD §3.2). Never perform a partial cleanup that leaves native Claude
# pointing at the gateway.
if apply and unresolved:
    print("  FAIL: legacy URL/credential fields exist but cannot be proven old-integration-owned.", file=sys.stderr)
    print("  Supply --old-base-url and --old-key-fingerprint (full 64-char SHA-256) to remove them.", file=sys.stderr)
    print("  Refusing partial cleanup that would leave native Claude redirected.", file=sys.stderr)
    for desc, key, val in unresolved:
        print("    unresolved: %s in %s = %s" % (key, desc, val), file=sys.stderr)
    sys.exit(1)

if dry_run:
    for path, desc, data, env, removals in parsed:
        print_dry_run(path, desc, removals)
    if unresolved:
        print()
        print("  Unresolved legacy fields (require --old-base-url / --old-key-fingerprint):")
        for desc, key, val in unresolved:
            print("    %s in %s = %s" % (key, desc, val))
    print()
    if all_removals:
        print("  %d value(s) would be removed." % len(all_removals))
    if unresolved:
        print("  %d unresolved field(s) require ownership evidence before removal." % len(unresolved))
    if all_removals and not unresolved:
        print("  Run with --apply to proceed.")
    sys.exit(0)

# Phase 2: Transactional apply (PRD §3.2).
# P0: Create and fsync ALL backups before the first target replacement, so a
# failure partway through always has a complete rollback set.
import time
backup_ts = int(time.time())
targets = [(p, d, dat, e, rem) for (p, d, dat, e, rem) in parsed if rem]
backups = []  # (path, desc, backup_path, orig_meta)
# Test hook: CLAUDE_LITELLM_MIGRATE_INJECT_FAIL=<index> raises after writing that
# target (0-based), proving cross-file rollback. No effect in production.
inject_fail = os.environ.get("CLAUDE_LITELLM_MIGRATE_INJECT_FAIL")
inject_idx = int(inject_fail) if inject_fail and inject_fail.isdigit() else -1
try:
    # Stage 1: back up every target and fsync.
    for path, desc, data, env, removals in targets:
        bak, orig_meta = make_backup(path, desc, backup_ts)
        backups.append((path, desc, bak, orig_meta))
        print("  backup: %s" % bak)
    # Stage 2: replace every target.
    for idx, ((path, desc, data, env, removals), (_, _, bak, orig_meta)) in enumerate(zip(targets, backups)):
        write_target(path, desc, data, env, removals, orig_meta)
        print("  applied: %s (%d keys removed)" % (desc, len(removals)))
        if idx == inject_idx:
            raise OSError("injected failure after writing %s" % desc)
except Exception:
    # P0: Rollback — restore every target and VERIFY restored content
    # (PRD §3.2). A failed rollback is a distinct nonzero hard error, not a
    # swallowed exception.
    print("  ROLLBACK: restoring %d file(s)..." % len(backups), file=sys.stderr)
    rollback_failed = False
    for path, desc, bak, orig_meta in backups:
        if not restore_target(path, bak, orig_meta):
            print("  FAIL: rollback verification failed for %s — file may be inconsistent!" % path, file=sys.stderr)
            rollback_failed = True
    if rollback_failed:
        print("  HARD ERROR: rollback incomplete. Inspect backups manually.", file=sys.stderr)
    else:
        print("  Rollback complete — original files restored and verified.", file=sys.stderr)
    sys.exit(1)

print()
print("  Migration complete. %d value(s) removed." % len(all_removals))
print("  Backups saved with .migrate-backup.* suffix (mode 0600).")
sys.exit(0)
PYEOF
