#!/usr/bin/env bash
set -euo pipefail

# claude-litellm-setup.sh — install the isolated GLM-5.2 launcher.
#
# Creates ~/.config/claude-litellm/env (mode 0600) with the GLM profile and
# installs the claude-litellm launcher to ~/.local/bin/claude-litellm.
#
# PRD: docs/PRD-release-closure-native-claude-litellm.md §3.1 (strict manifest trust)
#
# Usage:
#   claude-litellm-setup.sh --base-url URL  (key read from stdin or CLAUDE_LITELLM_KEY env)
#   claude-litellm-setup.sh --uninstall
#   claude-litellm-setup.sh --verify

BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
MODEL="claude-glm-5.2"
CONFIG_DIR="${CLAUDE_LITELLM_CONFIG_DIR:-$HOME/.config/claude-litellm}"
ENV_FILE="$CONFIG_DIR/env"
MANIFEST="$CONFIG_DIR/manifest.json"
BIN_DIR="${CLAUDE_LITELLM_BIN_DIR:-$HOME/.local/bin}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UNINSTALL=0
VERIFY=0

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ── Shared strict URL validator (PRD §3.1, §3.3) ──────────────────────────────
# Rejects: non-http(s), control/whitespace chars, embedded credentials (@),
# empty host. Used at install time (before writing a profile the launcher would
# reject) and inside parse_profile.
validate_url() {
    local url="$1"
    local label="${2:-URL}"
    case "$url" in
        http://*|https://*) ;;
        *) die "$label must start with http:// or https:// (got '$url')." ;;
    esac
    case "$url" in
        *$'\r'*|*$'\n'*|*$'\t'*|*' '*) die "$label contains control/whitespace characters." ;;
    esac
    case "$url" in
        *'@'*) die "$label must not contain embedded credentials." ;;
    esac
    local host_part
    host_part="${url#*://}"
    host_part="${host_part%%/*}"
    host_part="${host_part%%:*}"
    [ -n "$host_part" ] || die "$label has an empty host."
}

usage() {
    cat <<'EOF'
Usage: claude-litellm-setup.sh [options]

Options:
  --base-url URL      LiteLLM gateway URL (default: http://127.0.0.1:4000)
  --uninstall         Remove only integration-owned files (via manifest)
  --verify            Check profile, permissions, launcher, endpoint
  --help              Show this help

The gateway key is read from stdin or the CLAUDE_LITELLM_KEY environment variable.
It is NEVER accepted as a command-line argument.

This script does NOT modify ~/.claude/settings.json, ~/.claude.json,
or shell profiles.
EOF
}

# ── Parse arguments ───────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --base-url) BASE_URL="$2"; shift 2 ;;
        --model) die "--model is not supported. The model is fixed to claude-glm-5.2." ;;
        --uninstall) UNINSTALL=1; shift ;;
        --verify) VERIFY=1; shift ;;
        --help|-h) usage; exit 0 ;;
        --api-key) die "--api-key is not supported. Pipe the key via stdin or set CLAUDE_LITELLM_KEY." ;;
        *) die "unknown option: $1" ;;
    esac
done

# P0: Reject incompatible mode combinations (PRD §3.1).
mode_count=$((UNINSTALL + VERIFY))
if [ "$mode_count" -gt 1 ]; then
    die "incompatible flags: --uninstall and --verify cannot be combined."
fi

# ── Shared manifest + profile validator (PRD §3.1) ───────────────────────────
# One strict trust function used before install replacement, verify, and
# uninstall. Exits nonzero on any validation failure.
#
# Outputs a single token to stdout:
#   VALID    — manifest is complete and every referenced file matches its hash
#   MISSING  — manifest file does not exist
#   <reason> — manifest exists but is invalid (printed as a short reason)
#
# Sets the global MANIFEST_STATUS variable.
#
# P0: The manifest itself is validated with lstat — it must be a regular file,
# no symlink, owned by the current user, and exactly mode 0600. A symlinked or
# world-readable manifest is never trusted (PRD §3.1).
#
# P0: The manifest base_url is compared against the URL parsed from the EXISTING
# profile, not the invocation's default BASE_URL. This makes --verify and
# --uninstall work for any URL stored by installation, including remote gateways
# (PRD §3.1).
validate_manifest() {
    MANIFEST_STATUS="MISSING"
    [ -f "$MANIFEST" ] || return 0

    # P0: Validate the manifest file's own metadata before trusting its content.
    # lstat via python so we catch symlinks even when [ -f ] follows them.
    if ! python3 - "$MANIFEST" <<'PYMETA'
import os, sys, stat
p = sys.argv[1]
try:
    st = os.lstat(p)
except OSError:
    sys.exit(1)
if stat.S_ISLNK(st.st_mode):
    sys.exit(1)  # symlink — never trust
if not stat.S_ISREG(st.st_mode):
    sys.exit(1)  # not a regular file
if st.st_uid != os.getuid():
    sys.exit(1)  # wrong owner
if stat.S_IMODE(st.st_mode) != 0o600:
    sys.exit(1)  # not exactly 0600
sys.exit(0)
PYMETA
    then
        MANIFEST_STATUS="bad-manifest-meta"
        return 0
    fi

    # P0: Determine the expected base_url from the EXISTING profile, not the
    # invocation default. If the profile cannot be parsed, fall back to the
    # invocation BASE_URL (install/upgrade path where the profile may not yet
    # match). For verify/uninstall the profile is the authority.
    local expected_base_url="$BASE_URL"
    if [ -f "$ENV_FILE" ]; then
        # Parse just the base URL from the profile without the full die-on-fail
        # semantics (a malformed profile is a distinct failure reported below).
        local profile_url
        profile_url=$(python3 - "$ENV_FILE" <<'PYURL' 2>/dev/null || true
import sys
url = None
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("ANTHROPIC_BASE_URL="):
                url = line[len("ANTHROPIC_BASE_URL="):]
                break
except OSError:
    pass
if url:
    print(url)
PYURL
        )
        if [ -n "$profile_url" ]; then
            expected_base_url="$profile_url"
        fi
    fi

    MANIFEST_STATUS=$(python3 - "$MANIFEST" "$ENV_FILE" "$BIN_DIR" "$CONFIG_DIR" "$MODEL" "$expected_base_url" <<'PYVALIDATE'
import json, os, sys, hashlib, stat

manifest_path = sys.argv[1]
env_file = sys.argv[2]
bin_dir = sys.argv[3]
config_dir = sys.argv[4]
expected_model = sys.argv[5]
expected_base_url = sys.argv[6]

uid = os.getuid()

def fail(msg):
    print(msg)
    sys.exit(0)

def check_file_meta(path, require_hash=False):
    """Return (ok, reason) for a file's metadata: regular, no symlink,
    current-user owner."""
    try:
        st = os.lstat(path)
    except OSError:
        return (False, "missing")
    if stat.S_ISLNK(st.st_mode):
        return (False, "symlink")
    if not stat.S_ISREG(st.st_mode):
        return (False, "not-regular")
    if st.st_uid != uid:
        return (False, "wrong-owner")
    return (True, "")

try:
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
except (OSError, ValueError):
    fail("bad-json")

if not isinstance(m, dict):
    fail("not-dict")

# Schema version and creator.
if m.get("version") != 1:
    fail("bad-version")
if m.get("created_by") != "claude-litellm-setup.sh":
    fail("bad-creator")

# Canonical model and base URL must match the profile/expected values.
if m.get("model") != expected_model:
    fail("bad-model")
if m.get("base_url") != expected_base_url:
    fail("bad-base-url")

# Allowlisted, canonical path set.
allowed_paths = {
    os.path.join(bin_dir, "claude-litellm"),
    os.path.join(bin_dir, "claude-select"),
    os.path.join(config_dir, "env"),
    os.path.join(config_dir, "manifest.json"),
}
files_list = m.get("files", [])
if not isinstance(files_list, list):
    fail("bad-files")
for f in files_list:
    if f not in allowed_paths:
        fail("path-injection:%s" % f)

hashes = m.get("hashes", {})
if not isinstance(hashes, dict):
    fail("bad-hashes")

# Require nonempty 64-char lowercase SHA-256 for launcher, selector, profile.
required_hashes = {
    "launcher": os.path.join(bin_dir, "claude-litellm"),
    "selector": os.path.join(bin_dir, "claude-select"),
    "profile": env_file,
}
for role, fpath in required_hashes.items():
    h = hashes.get(role, "")
    if not isinstance(h, str) or len(h) != 64:
        fail("bad-hash:%s" % role)
    try:
        int(h, 16)
    except ValueError:
        fail("bad-hash:%s" % role)
    if h != h.lower():
        fail("bad-hash:%s" % role)
    # The referenced file must exist and match.
    ok, reason = check_file_meta(fpath)
    if not ok:
        fail("file-%s:%s" % (role, reason))
    try:
        with open(fpath, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        fail("file-%s:unreadable" % role)
    if actual != h:
        fail("hash-mismatch:%s" % role)

print("VALID")
PYVALIDATE
    )
}

# ── Manifest schema trust (no per-file hash match) (PRD §3.1) ─────────────────
# Used by uninstall: validates the manifest's own metadata (lstat: regular,
# no symlink, owner, 0600) and schema (version, creator, allowlisted paths,
# canonical model, base_url from profile), but does NOT require referenced
# files to match their hashes. A modified file is preserved and produces
# nonzero while other still-matching owned files may be removed.
#
# Sets MANIFEST_STATUS to VALID or a short reason (same vocabulary as
# validate_manifest, minus hash-mismatch).
validate_manifest_trust() {
    MANIFEST_STATUS="MISSING"
    [ -f "$MANIFEST" ] || return 0

    # P0: manifest self-meta (same as validate_manifest).
    if ! python3 - "$MANIFEST" <<'PYMETA'
import os, sys, stat
p = sys.argv[1]
try:
    st = os.lstat(p)
except OSError:
    sys.exit(1)
if stat.S_ISLNK(st.st_mode):
    sys.exit(1)
if not stat.S_ISREG(st.st_mode):
    sys.exit(1)
if st.st_uid != os.getuid():
    sys.exit(1)
if stat.S_IMODE(st.st_mode) != 0o600:
    sys.exit(1)
sys.exit(0)
PYMETA
    then
        MANIFEST_STATUS="bad-manifest-meta"
        return 0
    fi

    # base_url from the existing profile (same as validate_manifest).
    local expected_base_url="$BASE_URL"
    if [ -f "$ENV_FILE" ]; then
        local profile_url
        profile_url=$(python3 - "$ENV_FILE" <<'PYURL' 2>/dev/null || true
import sys
url = None
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("ANTHROPIC_BASE_URL="):
                url = line[len("ANTHROPIC_BASE_URL="):]
                break
except OSError:
    pass
if url:
    print(url)
PYURL
        )
        if [ -n "$profile_url" ]; then
            expected_base_url="$profile_url"
        fi
    fi

    MANIFEST_STATUS=$(python3 - "$MANIFEST" "$ENV_FILE" "$BIN_DIR" "$CONFIG_DIR" "$MODEL" "$expected_base_url" <<'PYTRUST'
import json, os, sys, stat

manifest_path = sys.argv[1]
env_file = sys.argv[2]
bin_dir = sys.argv[3]
config_dir = sys.argv[4]
expected_model = sys.argv[5]
expected_base_url = sys.argv[6]

def fail(msg):
    print(msg)
    sys.exit(0)

try:
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
except (OSError, ValueError):
    fail("bad-json")

if not isinstance(m, dict):
    fail("not-dict")
if m.get("version") != 1:
    fail("bad-version")
if m.get("created_by") != "claude-litellm-setup.sh":
    fail("bad-creator")
if m.get("model") != expected_model:
    fail("bad-model")
if m.get("base_url") != expected_base_url:
    fail("bad-base-url")

allowed_paths = {
    os.path.join(bin_dir, "claude-litellm"),
    os.path.join(bin_dir, "claude-select"),
    os.path.join(config_dir, "env"),
    os.path.join(config_dir, "manifest.json"),
}
files_list = m.get("files", [])
if not isinstance(files_list, list):
    fail("bad-files")
for f in files_list:
    if f not in allowed_paths:
        fail("path-injection:%s" % f)

hashes = m.get("hashes", {})
if not isinstance(hashes, dict):
    fail("bad-hashes")
# Hashes must be 64-char lowercase hex IF present, but may be absent/empty
# (a file with no hash is simply preserved at uninstall).
for role in ("launcher", "selector", "profile"):
    h = hashes.get(role, "")
    if h == "":
        continue
    if not isinstance(h, str) or len(h) != 64 or h != h.lower():
        fail("bad-hash:%s" % role)
    try:
        int(h, 16)
    except ValueError:
        fail("bad-hash:%s" % role)

print("VALID")
PYTRUST
    )
}

# ── Shared profile parser (PRD §3.1) — same parser as the launcher ────────────
# Validates: regular file, no symlink, current-user owner, mode 0600, exactly
# three keys (one of each), no unknown/duplicate, canonical model, valid URL.
# Sets GLM_BASE_URL, GLM_API_KEY, GLM_MODEL on success; exits nonzero on failure.
parse_profile() {
    local profile_path="$1"
    local label="${2:-profile}"
    # Existence and readability.
    [ -f "$profile_path" ] || die "%s not found at %s" "$label" "$profile_path"
    [ -r "$profile_path" ] || die "%s at %s is not readable." "$label" "$profile_path"
    # Reject symlinks.
    local real_path
    real_path="$(readlink -f "$profile_path" 2>/dev/null || echo "$profile_path")"
    [ "$real_path" = "$profile_path" ] || die "%s must not be a symlink." "$label"
    # Mode 0600.
    local fmode
    fmode="$(stat -c '%a' "$profile_path" 2>/dev/null || stat -f '%Lp' "$profile_path" 2>/dev/null || echo '000')"
    [ "$fmode" = "600" ] || die "%s must have mode 0600 (got %s)." "$label" "$fmode"
    # Ownership.
    local fowner
    fowner="$(stat -c '%u' "$profile_path" 2>/dev/null || stat -f '%u' "$profile_path" 2>/dev/null || echo '0')"
    [ "$fowner" = "$(id -u)" ] || die "%s must be owned by the current user." "$label"

    GLM_BASE_URL=""
    GLM_API_KEY=""
    GLM_MODEL=""
    local seen_url=0 seen_key=0 seen_model=0
    while IFS='=' read -r key value; do
        case "$key" in
            ''|\#*) continue ;;
        esac
        case "$value" in
            *$'\r'*) die "%s: CR not allowed in %s." "$label" "$key" ;;
            *$'\n'*) die "%s: newline not allowed in %s." "$label" "$key" ;;
        esac
        case "$key" in
            ANTHROPIC_BASE_URL|ANTHROPIC_API_KEY|ANTHROPIC_MODEL) ;;
            *) die "%s: unknown key '%s'." "$label" "$key" ;;
        esac
        case "$key" in
            ANTHROPIC_BASE_URL) [ "$seen_url" -eq 0 ] || die "%s: duplicate ANTHROPIC_BASE_URL." "$label"; seen_url=1 ;;
            ANTHROPIC_API_KEY) [ "$seen_key" -eq 0 ] || die "%s: duplicate ANTHROPIC_API_KEY." "$label"; seen_key=1 ;;
            ANTHROPIC_MODEL) [ "$seen_model" -eq 0 ] || die "%s: duplicate ANTHROPIC_MODEL." "$label"; seen_model=1 ;;
        esac
        [ -n "$value" ] || die "%s: %s is empty." "$label" "$key"
        case "$key" in
            ANTHROPIC_BASE_URL) GLM_BASE_URL="$value" ;;
            ANTHROPIC_API_KEY) GLM_API_KEY="$value" ;;
            ANTHROPIC_MODEL) GLM_MODEL="$value" ;;
        esac
    done < "$profile_path"

    [ -n "$GLM_BASE_URL" ] || die "%s: ANTHROPIC_BASE_URL is missing." "$label"
    [ -n "$GLM_API_KEY" ] || die "%s: ANTHROPIC_API_KEY is missing." "$label"
    [ -n "$GLM_MODEL" ] || die "%s: ANTHROPIC_MODEL is missing." "$label"
    # Canonical model.
    [ "$GLM_MODEL" = "$MODEL" ] || die "%s model is '%s' — only %s is permitted." "$label" "$GLM_MODEL" "$MODEL"
    # Valid URL (PRD §3.3): http:// or https://, no control chars, no embedded
    # credentials, nonempty host. Uses the shared validate_url function.
    validate_url "$GLM_BASE_URL" "$label ANTHROPIC_BASE_URL"
}

# ── Uninstall (manifest-driven, never rm -rf) ────────────────────────────────
if [ $UNINSTALL -eq 1 ]; then
    echo "Removing claude-litellm integration files..."
    # P0: Use schema trust (not full hash match) so a modified file is preserved
    # while other still-matching owned files may be removed (PRD §3.1).
    validate_manifest_trust
    if [ "$MANIFEST_STATUS" != "VALID" ]; then
        echo "  no valid manifest found — cannot safely remove (status: $MANIFEST_STATUS)" >&2
        echo "  Refusing to delete without proven ownership." >&2
        exit 1
    fi
    # Read the validated manifest and delete only exact allowlisted files with
    # matching nonempty hashes. An absent hash preserves the file (PRD §3.1).
    python3 - "$MANIFEST" "$BIN_DIR" "$CONFIG_DIR" <<'PYUNINSTALL'
import json, os, sys, hashlib

manifest_path = sys.argv[1]
bin_dir = sys.argv[2]
config_dir = sys.argv[3]

allowed_paths = {
    os.path.join(bin_dir, "claude-litellm"),
    os.path.join(bin_dir, "claude-select"),
    os.path.join(config_dir, "env"),
    os.path.join(config_dir, "manifest.json"),
}

with open(manifest_path, "r", encoding="utf-8") as f:
    m = json.load(f)

hashes = m.get("hashes", {})
role_to_path = {
    "launcher": os.path.join(bin_dir, "claude-litellm"),
    "selector": os.path.join(bin_dir, "claude-select"),
    "profile": os.path.join(config_dir, "env"),
}

removed = False
exit_nonzero = False

# Delete launcher, selector, profile only if hash matches.
for role, fpath in role_to_path.items():
    h = hashes.get(role, "")
    if not h or not os.path.isfile(fpath):
        # Absent hash → preserve (never authorize deletion without proof).
        if os.path.isfile(fpath) and not h:
            print("  preserved: %s (no hash in manifest)" % fpath)
            exit_nonzero = True
        continue
    if fpath not in allowed_paths:
        continue
    try:
        with open(fpath, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        print("  preserved: %s (unreadable)" % fpath)
        exit_nonzero = True
        continue
    if actual == h:
        os.remove(fpath)
        print("  removed: %s (hash matched)" % fpath)
        removed = True
    else:
        print("  preserved: %s (hash mismatch — user-modified)" % fpath)
        exit_nonzero = True

# Remove the manifest itself (it is the ownership record).
if os.path.isfile(manifest_path):
    os.remove(manifest_path)
    print("  removed: %s" % manifest_path)
    removed = True

# Remove empty config dir (only if empty — never rm -rf).
try:
    os.rmdir(config_dir)
    print("  removed: %s (empty)" % config_dir)
except OSError:
    pass

if removed and not exit_nonzero:
    print("Uninstall complete. Native claude settings were not touched.")
    sys.exit(0)
elif exit_nonzero:
    print("Uninstall completed with preserved files — exit nonzero.", file=sys.stderr)
    sys.exit(1)
else:
    print("Nothing removed.")
    sys.exit(0)
PYUNINSTALL
    exit $?
fi

# ── Verify (returns nonzero on any failure) ──────────────────────────────────
if [ $VERIFY -eq 1 ]; then
    errors=0
    echo "=== claude-litellm verification ==="

    # P0: Manifest is REQUIRED for verify (PRD §3.1). Missing/empty/forged
    # manifest fails verify.
    validate_manifest
    if [ "$MANIFEST_STATUS" != "VALID" ]; then
        echo "  FAIL: manifest is not valid (status: $MANIFEST_STATUS)" >&2
        exit 1
    fi
    echo "  manifest: OK (valid, hashes match)"

    # P0: Validate the profile with the same parser as the launcher.
    parse_profile "$ENV_FILE" "profile"
    echo "  profile: OK (mode 0600, owner, schema valid)"
    echo "  profile model: OK ($GLM_MODEL)"
    echo "  profile URL: OK ($GLM_BASE_URL)"

    # Launcher and selector existence (already checked by validate_manifest,
    # but confirm executability).
    [ -x "$BIN_DIR/claude-litellm" ] || { echo "  FAIL: launcher not executable"; errors=1; }
    [ -x "$BIN_DIR/claude-select" ] || { echo "  FAIL: selector not executable"; errors=1; }
    [ $errors -eq 0 ] && echo "  launcher: OK"

    # Endpoint — authenticate with the profile key.
    url="$GLM_BASE_URL"
    profile_key="$GLM_API_KEY"
    # Check endpoint health.
    http_code=$(curl -s --max-time 30 -o /dev/null -w "%{http_code}" "$url/health/readiness" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
        echo "  endpoint: OK ($url)"
    else
        echo "  FAIL: endpoint $url returned HTTP $http_code"
        errors=1
    fi
    # P0: Pass the bearer credential via a temp curl config file (mode 0600)
    # with EXIT/INT/TERM cleanup so interruption cannot leave it on disk.
    CURLCFG_FILE="$(mktemp)"
    chmod 600 "$CURLCFG_FILE"
    cleanup_cfg() { rm -f "$CURLCFG_FILE" 2>/dev/null || true; }
    trap cleanup_cfg EXIT INT TERM
    printf 'header = "Authorization: Bearer %s"\nheader = "Content-Type: application/json"\n' "$profile_key" > "$CURLCFG_FILE"
    # Canonical model must return 200.
    auth_code=$(curl -s --max-time 30 -o /dev/null -w "%{http_code}" \
        --config "$CURLCFG_FILE" \
        -d '{"model":"claude-glm-5.2","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' \
        "$url/v1/chat/completions" 2>/dev/null || echo "000")
    if [ "$auth_code" = "200" ]; then
        echo "  auth: OK (key authenticated, claude-glm-5.2 accessible)"
    else
        echo "  FAIL: key authentication or model access failed (HTTP $auth_code)"
        errors=1
    fi
    # ACL probes: require exactly 401 or 403.
    for internal_model in vision-openrouter vision-openrouter-secondary premium-openrouter glm-5.1-fallback; do
        block_code=$(curl -s --max-time 30 -o /dev/null -w "%{http_code}" \
            --config "$CURLCFG_FILE" \
            -d "{\"model\":\"$internal_model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" \
            "$url/v1/chat/completions" 2>/dev/null || echo "000")
        if [ "$block_code" != "401" ] && [ "$block_code" != "403" ]; then
            echo "  FAIL: internal model $internal_model returned HTTP $block_code (must be 401/403)"
            errors=1
        fi
    done
    [ $errors -eq 0 ] && echo "  ACL: internal models blocked (401/403)"
    cleanup_cfg
    trap - EXIT INT TERM
    if [ $errors -ne 0 ]; then
        exit 1
    fi
    echo "All checks passed."
    exit 0
fi

# ── Install ──────────────────────────────────────────────────────────────────
# Read the key from stdin or CLAUDE_LITELLM_KEY env — NEVER from argv.
API_KEY=""
if [ -n "${CLAUDE_LITELLM_KEY:-}" ]; then
    API_KEY="$CLAUDE_LITELLM_KEY"
elif [ ! -t 0 ]; then
    read -r API_KEY
fi
[ -n "$API_KEY" ] || die "gateway key is required. Pipe it via stdin or set CLAUDE_LITELLM_KEY."

# Reject CR/LF in the key.
case "$API_KEY" in
    *$'\r'*|*$'\n'*) die "gateway key contains newline characters — rejected." ;;
esac

# P0: Validate URL with the same strict parser the launcher uses (PRD §3.1).
# An install must not succeed with a profile the launcher will reject — this
# catches embedded credentials, empty hosts, and control characters at install
# time rather than at first launch.
validate_url "$BASE_URL" "base URL"

# P0: Transactional legacy migration (R10 §3, §4).
# The legacy claude-glm installation is validated as one complete ownership
# set in PREFLIGHT, backed up (not deleted) in BACKED_UP, and only removed in
# FINALIZED after the new install commits successfully. Any failure before
# FINALIZED restores the exact pre-run state.
LEGACY_CONFIG_DIR="$HOME/.config/claude-glm"
LEGACY_MANIFEST="$LEGACY_CONFIG_DIR/manifest.json"
LEGACY_LAUNCHER="$BIN_DIR/claude-glm"
LEGACY_ENV="$LEGACY_CONFIG_DIR/env"
LEGACY_SELECTOR="$BIN_DIR/claude-select"
LEGACY_PRESENT=0

# ── PREFLIGHT: validate all inputs, zero writes (R10 §3) ─────────────────────
if [ -d "$LEGACY_CONFIG_DIR" ] || [ -f "$LEGACY_LAUNCHER" ]; then
    LEGACY_PRESENT=1
    echo "  detected legacy claude-glm installation — validating ownership..."
    if [ ! -f "$LEGACY_MANIFEST" ]; then
        die "legacy claude-glm found but no manifest exists to prove ownership.
  Refusing to migrate. Remove the legacy installation manually:
    rm -f '$LEGACY_LAUNCHER' '$LEGACY_SELECTOR'
    rm -rf '$LEGACY_CONFIG_DIR'
  Then re-run this script."
    fi
    # Strict legacy manifest validation (R10 §2): all hashes must be non-empty,
    # all files must exist and match, no extra config-dir entries.
    if ! python3 - "$LEGACY_MANIFEST" "$LEGACY_LAUNCHER" "$LEGACY_ENV" "$LEGACY_SELECTOR" "$LEGACY_CONFIG_DIR" <<'LEGACYCHECK'
import json, os, sys, hashlib, stat

manifest_path, legacy_launcher, legacy_env, legacy_selector, legacy_config_dir = sys.argv[1:6]
uid = os.getuid()

def fail():
    sys.exit(1)

def check_file(path):
    """Return hash or None; refuse on symlink/wrong-owner/not-regular."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        fail()
    if st.st_uid != uid:
        fail()
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

# Manifest self-meta.
try:
    st = os.lstat(manifest_path)
except OSError:
    fail()
if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
    fail()
if st.st_uid != uid:
    fail()
if stat.S_IMODE(st.st_mode) != 0o600:
    fail()

try:
    m = json.load(open(manifest_path))
except (OSError, ValueError):
    fail()

if not isinstance(m, dict):
    fail()
if m.get("version") != 1:
    fail()
if m.get("created_by") != "claude-glm-setup.sh":
    fail()

# Hashes must contain exactly launcher, selector, profile — all non-empty.
hashes = m.get("hashes", {})
if not isinstance(hashes, dict):
    fail()
expected_keys = {"launcher", "selector", "profile"}
if set(hashes.keys()) != expected_keys:
    fail()
for role in expected_keys:
    h = hashes.get(role, "")
    if not isinstance(h, str) or len(h) != 64 or h != h.lower():
        fail()
    try:
        int(h, 16)
    except ValueError:
        fail()

# All three files must exist and match their hashes.
role_files = {"launcher": legacy_launcher, "selector": legacy_selector, "profile": legacy_env}
for role, fpath in role_files.items():
    actual = check_file(fpath)
    if actual is None:
        fail()  # missing file
    if actual != hashes[role]:
        fail()  # hash mismatch

# Config dir must contain only env and manifest.json — no extra entries.
try:
    entries = set(os.listdir(legacy_config_dir))
except OSError:
    fail()
if entries != {"env", "manifest.json"}:
    fail()

sys.exit(0)
LEGACYCHECK
    then
        die "legacy claude-glm manifest invalid or file hashes do not match.
  Refusing to migrate. Remove the legacy installation manually:
    rm -f '$LEGACY_LAUNCHER' '$LEGACY_SELECTOR'
    rm -rf '$LEGACY_CONFIG_DIR'
  Then re-run this script."
    fi
    echo "  legacy manifest verified."
fi

# Validate current claude-litellm installation if any targets exist.
# The shared claude-select is NOT a current-only target — it may belong to the
# legacy install. Only check claude-litellm-specific paths here.
validate_manifest
CURRENT_PRESENT=0
for target in "$BIN_DIR/claude-litellm" "$ENV_FILE" "$MANIFEST"; do
    [ -e "$target" ] && CURRENT_PRESENT=1
done
if [ "$MANIFEST_STATUS" != "VALID" ] && [ "$CURRENT_PRESENT" -eq 1 ]; then
    die "existing claude-litellm files present but manifest invalid ($MANIFEST_STATUS). Refusing to overwrite."
fi
# If claude-select exists but neither the current nor legacy manifest owns it,
# refuse (unowned collision).
if [ -f "$BIN_DIR/claude-select" ] && [ "$MANIFEST_STATUS" != "VALID" ] && [ "$LEGACY_PRESENT" -eq 0 ]; then
    die "an existing claude-select at $BIN_DIR/claude-select is not owned by this integration. Refusing to overwrite."
fi

# ── Create directories ───────────────────────────────────────────────────────
umask 077
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
mkdir -p "$BIN_DIR"

# ── STAGED: create complete new install in private staging (R10 §4) ──────────
STAGE_DIR="$(mktemp -d "$CONFIG_DIR/.stage.XXXXXX")"
BACKUP_DIR="$(mktemp -d "$CONFIG_DIR/.backup.XXXXXX")"
chmod 700 "$BACKUP_DIR"
cleanup_all() { rm -rf "$STAGE_DIR" "$BACKUP_DIR" 2>/dev/null || true; }
trap cleanup_all EXIT INT TERM

# Snapshot existing current files for rollback (empty if fresh install).
OLD_ENV=""; [ -f "$ENV_FILE" ] && OLD_ENV="$BACKUP_DIR/current.env" && cp -p "$ENV_FILE" "$OLD_ENV" 2>/dev/null || true
OLD_LAUNCHER=""; [ -f "$BIN_DIR/claude-litellm" ] && OLD_LAUNCHER="$BACKUP_DIR/current.launcher" && cp -p "$BIN_DIR/claude-litellm" "$OLD_LAUNCHER" 2>/dev/null || true
OLD_SELECTOR=""; [ -f "$BIN_DIR/claude-select" ] && OLD_SELECTOR="$BACKUP_DIR/current.selector" && cp -p "$BIN_DIR/claude-select" "$OLD_SELECTOR" 2>/dev/null || true
OLD_MANIFEST=""; [ -f "$MANIFEST" ] && OLD_MANIFEST="$BACKUP_DIR/current.manifest" && cp -p "$MANIFEST" "$OLD_MANIFEST" 2>/dev/null || true

# Stage the new profile (mode 0600).
STAGE_ENV="$STAGE_DIR/env"
cat > "$STAGE_ENV" <<EOF
ANTHROPIC_BASE_URL=$BASE_URL
ANTHROPIC_API_KEY=$API_KEY
ANTHROPIC_MODEL=$MODEL
EOF
chmod 600 "$STAGE_ENV"

# Stage the new launcher and selector.
STAGE_LAUNCHER="$STAGE_DIR/claude-litellm"
cp "$SCRIPT_DIR/claude-litellm" "$STAGE_LAUNCHER"
chmod 755 "$STAGE_LAUNCHER"
STAGE_SELECTOR=""
if [ -f "$SCRIPT_DIR/claude-select" ]; then
    STAGE_SELECTOR="$STAGE_DIR/claude-select"
    cp "$SCRIPT_DIR/claude-select" "$STAGE_SELECTOR"
    chmod 755 "$STAGE_SELECTOR"
fi

# Compute hashes from the staged files.
LAUNCHER_HASH=$(sha256sum "$STAGE_LAUNCHER" | cut -d' ' -f1)
SELECTOR_HASH=""
if [ -n "$STAGE_SELECTOR" ]; then
    SELECTOR_HASH=$(sha256sum "$STAGE_SELECTOR" | cut -d' ' -f1)
fi
ENV_HASH=$(sha256sum "$STAGE_ENV" | cut -d' ' -f1)

# Stage the new manifest.
STAGE_MANIFEST="$STAGE_DIR/manifest.json"
cat > "$STAGE_MANIFEST" <<EOF
{
  "version": 1,
  "created_by": "claude-litellm-setup.sh",
  "files": [
    "$BIN_DIR/claude-litellm",
    "$BIN_DIR/claude-select",
    "$CONFIG_DIR/env",
    "$CONFIG_DIR/manifest.json"
  ],
  "hashes": {
    "launcher": "$LAUNCHER_HASH",
    "selector": "$SELECTOR_HASH",
    "profile": "$ENV_HASH"
  },
  "model": "$MODEL",
  "base_url": "$BASE_URL"
}
EOF
chmod 600 "$STAGE_MANIFEST"

# ── BACKED_UP: move legacy files to backup (NOT delete) (R10 §4) ─────────────
if [ "$LEGACY_PRESENT" -eq 1 ]; then
    echo "  backing up legacy claude-glm files..."
    cp -p "$LEGACY_LAUNCHER" "$BACKUP_DIR/legacy.launcher" 2>/dev/null || true
    cp -p "$LEGACY_ENV" "$BACKUP_DIR/legacy.env" 2>/dev/null || true
    cp -p "$LEGACY_MANIFEST" "$BACKUP_DIR/legacy.manifest" 2>/dev/null || true
    # Selector: only back up if it's the legacy one (not already backed up as current).
    if [ -z "$OLD_SELECTOR" ] && [ -f "$LEGACY_SELECTOR" ]; then
        cp -p "$LEGACY_SELECTOR" "$BACKUP_DIR/legacy.selector" 2>/dev/null || true
    fi
fi
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "backup" ] && { echo "  FAIL(injected): after backup." >&2; exit 1; }

# ── Rollback routine (R10 §4: restores old + legacy state) ───────────────────
rollback() {
    local restore_failed=0
    # Remove partial new files.
    rm -f "$ENV_FILE" "$BIN_DIR/claude-litellm" "$BIN_DIR/claude-select" "$MANIFEST" 2>/dev/null || true
    # Restore current install from backup.
    if [ -n "$OLD_ENV" ] && [ -f "$OLD_ENV" ]; then cp -p "$OLD_ENV" "$ENV_FILE" 2>/dev/null || restore_failed=1; fi
    if [ -n "$OLD_LAUNCHER" ] && [ -f "$OLD_LAUNCHER" ]; then cp -p "$OLD_LAUNCHER" "$BIN_DIR/claude-litellm" 2>/dev/null || restore_failed=1; fi
    if [ -n "$OLD_SELECTOR" ] && [ -f "$OLD_SELECTOR" ]; then cp -p "$OLD_SELECTOR" "$BIN_DIR/claude-select" 2>/dev/null || restore_failed=1; fi
    if [ -n "$OLD_MANIFEST" ] && [ -f "$OLD_MANIFEST" ]; then cp -p "$OLD_MANIFEST" "$MANIFEST" 2>/dev/null || restore_failed=1; fi
    # Restore legacy install from backup (if it existed and was backed up).
    if [ "$LEGACY_PRESENT" -eq 1 ]; then
        [ -f "$BACKUP_DIR/legacy.launcher" ] && cp -p "$BACKUP_DIR/legacy.launcher" "$LEGACY_LAUNCHER" 2>/dev/null || true
        [ -f "$BACKUP_DIR/legacy.env" ] && cp -p "$BACKUP_DIR/legacy.env" "$LEGACY_ENV" 2>/dev/null || true
        [ -f "$BACKUP_DIR/legacy.manifest" ] && cp -p "$BACKUP_DIR/legacy.manifest" "$LEGACY_MANIFEST" 2>/dev/null || true
        [ -f "$BACKUP_DIR/legacy.selector" ] && cp -p "$BACKUP_DIR/legacy.selector" "$LEGACY_SELECTOR" 2>/dev/null || true
    fi
    cleanup_all
    if [ "$restore_failed" -ne 0 ]; then
        echo "  FAIL: rollback incomplete — could not restore all files." >&2
        echo "  Paths: $ENV_FILE $BIN_DIR/claude-litellm $BIN_DIR/claude-select $MANIFEST" >&2
        exit 1
    fi
    exit 1
}

# ── COMMITTED: atomically replace with new files (R10 §4) ────────────────────
mv "$STAGE_ENV" "$ENV_FILE" || { echo "  FAIL: cannot write profile." >&2; rollback; }
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "profile" ] && { echo "  FAIL(injected): after profile." >&2; rollback; }
mv "$STAGE_LAUNCHER" "$BIN_DIR/claude-litellm" || { echo "  FAIL: cannot write launcher." >&2; rollback; }
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "launcher" ] && { echo "  FAIL(injected): after launcher." >&2; rollback; }
if [ -n "$STAGE_SELECTOR" ]; then
    mv "$STAGE_SELECTOR" "$BIN_DIR/claude-select" || { echo "  FAIL: cannot write selector." >&2; rollback; }
fi
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "selector" ] && { echo "  FAIL(injected): after selector." >&2; rollback; }
mv "$STAGE_MANIFEST" "$MANIFEST" || { echo "  FAIL: cannot write manifest." >&2; rollback; }
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "manifest" ] && { echo "  FAIL(injected): after manifest." >&2; rollback; }

# Post-commit revalidation (R10 §4).
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "post-commit" ] && { echo "  FAIL(injected): post-commit." >&2; rollback; }

# ── FINALIZED: remove legacy files + backups only after commit succeeds ──────
[ "${CLAUDE_LITELLM_INJECT_FAIL:-}" = "pre-finalize" ] && { echo "  FAIL(injected): pre-finalize." >&2; rollback; }
if [ "$LEGACY_PRESENT" -eq 1 ]; then
    rm -f "$LEGACY_LAUNCHER" 2>/dev/null || true
    rm -f "$LEGACY_ENV" 2>/dev/null || true
    rm -f "$LEGACY_MANIFEST" 2>/dev/null || true
    rmdir "$LEGACY_CONFIG_DIR" 2>/dev/null || true
    echo "  legacy claude-glm removed."
fi

echo "  wrote: $ENV_FILE (mode 0600)"
echo "  installed: $BIN_DIR/claude-litellm"
[ -n "$STAGE_SELECTOR" ] && echo "  installed: $BIN_DIR/claude-select"
echo "  wrote: $MANIFEST"

trap - EXIT INT TERM
cleanup_all

echo ""
echo "Setup complete."
echo "  Start a GLM session:  claude-litellm [args]"
echo "  Native Claude:        claude [args]  (unchanged)"
echo "  Verify:               client/claude-litellm-setup.sh --verify"
echo ""
echo "Ensure $BIN_DIR is on your PATH (add to ~/.bashrc if needed):"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
