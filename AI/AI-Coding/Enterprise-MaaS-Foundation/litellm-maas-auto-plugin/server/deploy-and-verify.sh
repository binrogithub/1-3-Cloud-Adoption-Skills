#!/usr/bin/env bash
# Artifact-only deploy + verify (R11 §4.8, PRD-r11-final-closeout.md §10).
#
# Usage:
#   bash server/deploy-and-verify.sh --artifact releases/r11/<sha>.tar.gz
#
# Prerequisites:
#   - The LiteLLM proxy is running (docker compose up)
#   - LITELLM_KEY env var is set (or KEY_FILE exists)
#   - SIDECAR_API_KEY env var is set
#
# This script does NOT require a git worktree. It extracts the artifact to a
# durable versioned release root, installs from that root, reconciles all
# hashes against the manifest, and runs the live matrix twice.
#
# Durable deployment (PRD §10): the extraction is promoted to a versioned
# directory keyed by the artifact SHA-256. Compose bind mounts point at this
# durable directory, NOT at a temp directory that is removed on exit. The
# previous release is retained until all gates pass. On failure, the previous
# release pointer is restored.

set -euo pipefail

DEPLOY_DIR="${LITELLM_DEPLOY_DIR:-}"
BASE_URL="http://127.0.0.1:4000"
CONTAINER="litellm_proxy"
ARTIFACT=""
EXTRACT_DIR=""
RELEASE_ROOT=""
RELEASES_BASE="${RELEASES_BASE:-/var/lib/litellm-releases}"
PREV_RELEASE_LINK=""
PREV_RELEASE=""
PREV_COMPOSE_HASH=""
PREV_CONFIG_HASH=""
SNAPSHOT_DIR=""
ROLLBACK_NEEDED=0

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ── Global rollback trap (PRD §9.2) ───────────────────────────────────────────
# On any failure, signal, or error, restore the previous compose, config, and
# release pointer. A symlink-only rollback without restoring compose mount
# sources is insufficient.
rollback_restore() {
    local exit_code=$?
    # Clean up temp extraction.
    if [ -n "$EXTRACT_DIR" ] && [ -d "$EXTRACT_DIR" ]; then
        rm -rf "$EXTRACT_DIR"
    fi
    # If we started mutating and failed, restore previous state.
    if [ "$ROLLBACK_NEEDED" = "1" ] && [ -n "$PREV_RELEASE" ] && [ -d "$PREV_RELEASE" ]; then
        echo "=== ROLLBACK: restoring previous release ===" >&2
        ln -sfn "$PREV_RELEASE" "$PREV_RELEASE_LINK.tmp"
        mv -Tf "$PREV_RELEASE_LINK.tmp" "$PREV_RELEASE_LINK"
        # Restore compose if we have a snapshot.
        if [ -n "$SNAPSHOT_DIR" ] && [ -d "$SNAPSHOT_DIR" ]; then
            if [ -f "$SNAPSHOT_DIR/docker-compose.yml" ]; then
                cp -a "$SNAPSHOT_DIR/docker-compose.yml" "$DEPLOY_DIR/docker-compose.yml"
            fi
            if [ -f "$SNAPSHOT_DIR/litellm_config.yaml" ]; then
                cp -a "$SNAPSHOT_DIR/litellm_config.yaml" "$DEPLOY_DIR/assets/config/litellm_config.yaml"
            fi
        fi
        # Restart with restored config.
        cd "$DEPLOY_DIR" && docker compose up -d litellm >/dev/null 2>&1 || true
        docker restart "$CONTAINER" >/dev/null 2>&1 || true
        echo "=== ROLLBACK: previous release restored ===" >&2
    fi
    exit $exit_code
}

cleanup() {
    rollback_restore
}

trap cleanup EXIT INT TERM HUP

while [ $# -gt 0 ]; do
    case "$1" in
        --artifact) ARTIFACT="$2"; shift 2 ;;
        --deploy-dir) DEPLOY_DIR="$2"; shift 2 ;;
        --releases-base) RELEASES_BASE="$2"; shift 2 ;;
        -h|--help) echo "Usage: $0 --artifact PATH [--deploy-dir DIR] [--releases-base DIR]"; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

[ -n "$ARTIFACT" ] || die "--artifact PATH is required"
[ -f "$ARTIFACT" ] || die "artifact not found: $ARTIFACT"
[ -n "$DEPLOY_DIR" ] || die "--deploy-dir is required (or set LITELLM_DEPLOY_DIR env var)."

# Verify checksum before extraction.
SUMS_FILE="$(dirname "$ARTIFACT")/SHA256SUMS"
[ -f "$SUMS_FILE" ] || die "SHA256SUMS not found: $SUMS_FILE"
ARTIFACT_BASE="$(basename "$ARTIFACT")"
EXPECTED_HASH=$(grep "  ${ARTIFACT_BASE}\$" "$SUMS_FILE" | cut -d' ' -f1)
[ -n "$EXPECTED_HASH" ] || die "artifact not in SHA256SUMS"
ACTUAL_HASH=$(sha256sum "$ARTIFACT" | cut -d' ' -f1)
[ "$ACTUAL_HASH" = "$EXPECTED_HASH" ] || die "artifact hash mismatch"
echo "=== Artifact verified: $ARTIFACT_BASE (sha256 $ACTUAL_HASH) ==="
echo ""

# ── Durable release root (PRD §10, §9.1) ──────────────────────────────────────
# The release root is a versioned directory keyed by the artifact SHA-256.
# It persists after this script exits — compose bind mounts point here.
RELEASE_ROOT="$RELEASES_BASE/$ACTUAL_HASH"
mkdir -p "$RELEASES_BASE"

# Record the previous release for rollback.
PREV_RELEASE_LINK="$RELEASES_BASE/current"
PREV_RELEASE=""
if [ -L "$PREV_RELEASE_LINK" ]; then
    PREV_RELEASE=$(readlink "$PREV_RELEASE_LINK")
fi

# Snapshot current compose + config for rollback (PRD §9.2).
SNAPSHOT_DIR="$(mktemp -d)"
if [ -f "$DEPLOY_DIR/docker-compose.yml" ]; then
    cp -a "$DEPLOY_DIR/docker-compose.yml" "$SNAPSHOT_DIR/"
fi
CONFIG_FILE=$(python3 -c "
import re, os, sys
compose = os.path.join('$DEPLOY_DIR', 'docker-compose.yml')
base = '$DEPLOY_DIR'
for line in open(compose):
    m = re.match(r'\s*-\s*(.+?):/app/config\.yaml', line)
    if m:
        p = m.group(1).strip()
        print(p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p)))
        break
else:
    print(os.path.join(base, 'assets/config/litellm_config.yaml'))
" 2>/dev/null || echo "$DEPLOY_DIR/assets/config/litellm_config.yaml")
if [ -f "$CONFIG_FILE" ]; then
    cp -a "$CONFIG_FILE" "$SNAPSHOT_DIR/litellm_config.yaml"
fi
PREV_COMPOSE_HASH=$(sha256sum "$DEPLOY_DIR/docker-compose.yml" 2>/dev/null | cut -d' ' -f1 || echo "")

echo "=== Release root: $RELEASE_ROOT ==="
if [ -n "$PREV_RELEASE" ]; then
    echo "=== Previous release: $PREV_RELEASE ==="
fi
echo ""

# Extract to a private temp staging directory.
EXTRACT_DIR="$(mktemp -d)"
tar xzf "$ARTIFACT" -C "$EXTRACT_DIR"
STAGED_ROOT="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -n "$STAGED_ROOT" ] || die "extraction produced no top-level directory"
echo "=== Staged in: $STAGED_ROOT ==="
echo ""

# Verify RELEASE-MANIFEST.json is inside the artifact.
MANIFEST="$STAGED_ROOT/RELEASE-MANIFEST.json"
[ -f "$MANIFEST" ] || die "RELEASE-MANIFEST.json not found in artifact"
echo "=== Manifest: $(python3 -c "import json; m=json.load(open('$MANIFEST')); print('commit', m['commit'], '|', len(m['files']), 'files')") ==="
echo ""

# ── Atomic promotion: staging -> durable release root (PRD §9.1) ─────────────
# If the release root already exists, verify it against the manifest and REUSE it.
# Never rm -rf and repopulate a directory currently used by Docker bind mounts.
if [ -d "$RELEASE_ROOT" ]; then
    echo "=== Release root already exists; verifying and reusing ==="
    # Verify the existing release root matches the manifest.
    VERIFY_FAIL=0
    for src in $(python3 -c "import json; m=json.load(open('$MANIFEST')); print(' '.join(m['files'].keys()))" 2>/dev/null); do
        if [ -f "$RELEASE_ROOT/$src" ]; then
            existing_hash=$(sha256sum "$RELEASE_ROOT/$src" | cut -d' ' -f1)
            manifest_hash=$(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['files'].get('$src',''))" 2>/dev/null)
            if [ "$existing_hash" != "$manifest_hash" ]; then
                echo "  MISMATCH in existing release: $src" >&2
                VERIFY_FAIL=1
            fi
        fi
    done
    if [ "$VERIFY_FAIL" = "1" ]; then
        die "existing release root does not match manifest — refusing to use it"
    fi
    echo "  existing release root verified OK, reusing"
else
    # New SHA: extract under the releases filesystem, verify, atomic rename.
    STAGING_FINAL="${RELEASE_ROOT}.staging.$$"
    mkdir -p "$STAGING_FINAL"
    cp -a "$STAGED_ROOT/." "$STAGING_FINAL/"
    # Atomic rename into the final SHA directory (same filesystem).
    mv "$STAGING_FINAL" "$RELEASE_ROOT"
    echo "=== Promoted to durable release root: $RELEASE_ROOT ==="
fi
echo ""

# Mark that we are about to mutate — rollback is needed if we fail after this.
ROLLBACK_NEEDED=1

# Update the 'current' symlink atomically.
ln -sfn "$RELEASE_ROOT" "$PREV_RELEASE_LINK.tmp"
mv -Tf "$PREV_RELEASE_LINK.tmp" "$PREV_RELEASE_LINK"
echo "=== current -> $RELEASE_ROOT ==="
echo ""

# ── Step 1: Install from durable release root ────────────────────────────────
echo "=== Step 1: Install from durable release root ==="
export SIDECAR_API_KEY="${SIDECAR_API_KEY:?SIDECAR_API_KEY must be set}"
bash "$RELEASE_ROOT/server/install-litellm-plugin.sh" \
    --litellm-dir "$DEPLOY_DIR" \
    --artifact "$ARTIFACT" \
    --source-root "$RELEASE_ROOT" 2>&1 | tail -5
echo ""

# ── Step 2: Restart container ────────────────────────────────────────────────
echo "=== Step 2: Restart container ==="
cd "$DEPLOY_DIR" && docker compose up -d litellm >/dev/null 2>&1
sleep 8
curl -s --max-time 10 "$BASE_URL/health/readiness" | python3 -c "import json,sys; print('health:', json.load(sys.stdin).get('status'))"
echo ""

# ── Step 3: Full hash reconciliation against manifest ────────────────────────
echo "=== Step 3: Hash reconciliation (all mounted files) ==="
HASH_FAIL=0
CONTAINER_FILES=(
    /app/smart_router.py
    /app/sidecar.py
    /app/anthropic_stream_guard.py
    /app/anthropic_reasoning_filter.py
    /app/glm_loop_breaker.py
    /app/tool_argument_guard.py
    /app/_request_context.py
    /app/_litellm_adapter.py
    /app/model_registry.json
    /app/smart_router_rules.json
)
for cf in "${CONTAINER_FILES[@]}"; do
    basename=$(basename "$cf")
    case "$basename" in
        smart_router.py) src="litellm_plugins/smart_router/callback.py" ;;
        sidecar.py) src="litellm_plugins/sidecar/callback.py" ;;
        anthropic_stream_guard.py) src="litellm_plugins/anthropic_stream_guard/callback.py" ;;
        anthropic_reasoning_filter.py) src="litellm_plugins/anthropic_reasoning_filter/callback.py" ;;
        glm_loop_breaker.py) src="litellm_plugins/glm_loop_breaker/callback.py" ;;
        tool_argument_guard.py) src="litellm_plugins/tool_argument_guard/callback.py" ;;
        _request_context.py) src="_request_context.py" ;;
        _litellm_adapter.py) src="_litellm_adapter.py" ;;
        model_registry.json) src="litellm_plugins/model_registry.json" ;;
        smart_router_rules.json) src="litellm_plugins/smart_router/smart_router_rules.json" ;;
        *) src="" ;;
    esac
    [ -z "$src" ] && continue
    manifest_hash=$(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['files'].get('$src',''))" 2>/dev/null)
    release_hash=$(sha256sum "$RELEASE_ROOT/$src" 2>/dev/null | cut -d' ' -f1)
    container_hash=$(docker exec "$CONTAINER" python3 -c "import hashlib; print(hashlib.sha256(open('$cf','rb').read()).hexdigest())" 2>/dev/null)
    if [ "$release_hash" = "$container_hash" ] && [ "$release_hash" = "$manifest_hash" ]; then
        echo "  MATCH: $basename"
    else
        echo "  MISMATCH: $basename (manifest=$manifest_hash release=$release_hash container=$container_hash)"
        HASH_FAIL=1
    fi
done

# Also verify client files (PRD §9.3: manifest -> durable release -> installed destination).
# The comparison between manifest and release copy alone does not prove what the
# user invokes. Check the installed destination too.
# Installed client destinations (PRD §10.3: check real install path, not
# assume /usr/local/bin). 217 installs to ~/.local/bin.
# Only launcher and selector are installed; setup/migrate/configure are
# run-once scripts not meant to be installed (PRD §10.3: "Setup/migrate
# scripts若产品合同本来不要求安装，不得伪装成 installed-client").
INSTALLED_CLIENT_DIRS=("${INSTALLED_CLIENT_DIR:-$HOME/.local/bin}" "/usr/local/bin")
INSTALLED_CLIENT_FILES=("client/claude-litellm" "client/claude-select")
MEMBERSHIP_ONLY_FILES=("client/claude-litellm-setup.sh" "client/claude-litellm-migrate.sh" "client/configure-claude-code.sh")

for cf in "${INSTALLED_CLIENT_FILES[@]}"; do
    basename=$(basename "$cf")
    manifest_hash=$(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['files'].get('$cf',''))" 2>/dev/null)
    release_hash=$(sha256sum "$RELEASE_ROOT/$cf" 2>/dev/null | cut -d' ' -f1)
    # Find the actual installed location (PRD §10.3: must check real path)
    installed_path=""
    installed_hash=""
    for dir in "${INSTALLED_CLIENT_DIRS[@]}"; do
        if [ -f "$dir/$basename" ]; then
            installed_path="$dir/$basename"
            installed_hash=$(sha256sum "$installed_path" 2>/dev/null | cut -d' ' -f1)
            break
        fi
    done
    if [ -n "$manifest_hash" ] && [ "$release_hash" = "$manifest_hash" ]; then
        if [ -n "$installed_hash" ]; then
            if [ "$installed_hash" = "$manifest_hash" ]; then
                echo "  MATCH: $cf (manifest=release=installed at $installed_path)"
            else
                echo "  MISMATCH: $cf installed=$installed_hash != manifest=$manifest_hash"
                HASH_FAIL=1
            fi
        else
            # PRD §10.3: missing installed file must FAIL, not silently pass
            echo "  MISSING: $cf not installed in ${INSTALLED_CLIENT_DIRS[*]}"
            HASH_FAIL=1
        fi
    elif [ -n "$manifest_hash" ]; then
        echo "  MISMATCH: $cf (manifest=$manifest_hash release=$release_hash)"
        HASH_FAIL=1
    fi
done

# Setup/migrate/configure scripts: verify artifact membership only (PRD §10.3)
for cf in "${MEMBERSHIP_ONLY_FILES[@]}"; do
    manifest_hash=$(python3 -c "import json; m=json.load(open('$MANIFEST')); print(m['files'].get('$cf',''))" 2>/dev/null)
    release_hash=$(sha256sum "$RELEASE_ROOT/$cf" 2>/dev/null | cut -d' ' -f1)
    if [ -n "$manifest_hash" ] && [ "$release_hash" = "$manifest_hash" ]; then
        echo "  MATCH: $cf (manifest=release; membership only)"
    elif [ -n "$manifest_hash" ]; then
        echo "  MISMATCH: $cf (manifest=$manifest_hash release=$release_hash)"
        HASH_FAIL=1
    fi
done

if [ "$HASH_FAIL" -ne 0 ]; then
    echo "FAIL: hash reconciliation failed." >&2
    exit 1  # global trap will rollback
fi
echo ""

# ── Step 4: ACL verification ─────────────────────────────────────────────────
echo "=== Step 4: ACL verification ==="
KEY="${LITELLM_KEY:-$(python3 -c "import json; print(json.load(open('${KEY_FILE:-$DEPLOY_DIR/.claude-code-key.json}'))['key'])" 2>/dev/null || echo '')}"
[ -n "$KEY" ] || die "no LITELLM_KEY or KEY_FILE"
MODELS=$(curl -s --max-time 10 -H "Authorization: Bearer $KEY" "$BASE_URL/v1/models" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print([m['id'] for m in d.get('data',[])])")
[ "$MODELS" = "['claude-glm-5.2']" ] || die "ACL not exact: $MODELS"
echo "  /v1/models: $MODELS ✓"
for m in vision-openrouter vision-openrouter-secondary premium-openrouter glm-5.1-fallback "claude-glm-5.2[1m]"; do
    code=$(curl -s --max-time 30 -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" "$BASE_URL/v1/chat/completions" 2>/dev/null)
    { [ "$code" = "401" ] || [ "$code" = "403" ]; } && echo "  $m: $code ✓" || { echo "  $m: $code ✗"; HASH_FAIL=1; }
done
echo ""

# ── Step 5: TOOL_ARG_GUARD_MODE verification ─────────────────────────────────
echo "=== Step 5: TOOL_ARG_GUARD_MODE ==="
MODE=$(docker exec "$CONTAINER" env 2>/dev/null | grep TOOL_ARG_GUARD_MODE | cut -d= -f2)
[ "$MODE" = "enforce" ] && echo "  TOOL_ARG_GUARD_MODE=enforce ✓" || { echo "  TOOL_ARG_GUARD_MODE=$MODE ✗ (expected enforce)"; HASH_FAIL=1; }
echo ""

# ── Step 6: Live smoke matrix (run twice) ────────────────────────────────────
echo "=== Step 6: Live smoke matrix (run twice) ==="
SIDECAR="${SIDECAR_API_KEY:?}"
RUN_FAIL=0
for run in 1 2; do
    echo "--- Run $run ---"
    cd "$RELEASE_ROOT"
    # Write smoke results to a temp dir, NOT the immutable release root (PRD §10.1)
    SMOKE_OUT="$(mktemp -d)/results-healthy-run${run}.json"
    LITELLM_KEY="$KEY" SIDECAR_API_KEY="$SIDECAR" \
        CANDIDATE_COMMIT="$(python3 -c "import json; print(json.load(open('$MANIFEST'))['commit'][:12])")" \
        ARTIFACT_SHA256="$ACTUAL_HASH" \
        DEPLOY_ROOT="$RELEASE_ROOT" \
        CAPTION_CACHE_DIR="$DEPLOY_DIR/assets/cache/captions/v1" \
        python3 tests/live_smoke.py --profile healthy --json-output "$SMOKE_OUT" 2>&1 | grep -E "^(message|stream|tools|reasoning|image|nested|tool_args|image_limit|502):|summary:"
    echo ""
done
echo ""

# ── Step 7: Adapter 413 test ─────────────────────────────────────────────────
echo "=== Step 7: Adapter 413 test (5 valid images) ==="
cd "$RELEASE_ROOT"
python3 -c "
import base64, struct, zlib, json, urllib.request, urllib.error
def make_png(r, g, b):
    w, h = 2, 2
    raw = b''
    for _ in range(h): raw += b'\x00' + bytes([r, g, b]) * w
    comp = zlib.compress(raw)
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', comp)
    iend = chunk(b'IEND', b'')
    return base64.b64encode(sig + ihdr + idat + iend).decode()
colors = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255)]
images = [{'type':'image','source':{'type':'base64','media_type':'image/png','data':make_png(r,g,b)}} for r,g,b in colors]
body = json.dumps({'model':'claude-glm-5.2','max_tokens':64,'messages':[{'role':'user','content':[{'type':'text','text':'Describe.'}] + images}]}).encode()
req = urllib.request.Request('$BASE_URL/v1/messages', data=body, headers={'content-type':'application/json','x-api-key':'$KEY','anthropic-version':'2023-06-01'}, method='POST')
try:
    urllib.request.urlopen(req, timeout=30)
    print('  HTTP 200 (expected 413) ✗')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    has_limit = 'IMAGE_LIMIT' in body.upper()
    print(f'  HTTP {e.code} IMAGE_LIMIT={has_limit} {\"✓\" if e.code == 413 and has_limit else \"✗\"}')
"
echo ""

# ── Immutable release root scan (PRD §10.1: no undeclared files) ─────────────
echo "=== Step 8: Immutable release root scan ==="
UNDECLARED=$(python3 -c "
import json, os
m = json.load(open('$MANIFEST'))
declared = set(m['files'].keys())
declared.add('RELEASE-MANIFEST.json')
root = '$RELEASE_ROOT'
found = set()
for dirpath, dirnames, filenames in os.walk(root):
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, root)
        found.add(rel)
extra = found - declared
if extra:
    print('\n'.join(sorted(extra)))
" 2>/dev/null)
if [ -n "$UNDECLARED" ]; then
    echo "  FAIL: undeclared files in release root:"
    echo "$UNDECLARED" | head -10
    HASH_FAIL=1
else
    echo "  PASS: no undeclared files"
fi
echo ""

# ── Deployment report ────────────────────────────────────────────────────────
echo "=== Deployment report ==="
echo "  artifact: $ARTIFACT_BASE"
echo "  sha256: $ACTUAL_HASH"
echo "  release_root: $RELEASE_ROOT"
echo "  current_symlink: $PREV_RELEASE_LINK -> $(readlink "$PREV_RELEASE_LINK")"
echo "  previous_release: ${PREV_RELEASE:-none}"
echo "  manifest_commit: $(python3 -c "import json; print(json.load(open('$MANIFEST'))['commit'])")"
echo "  manifest_files: $(python3 -c "import json; print(len(json.load(open('$MANIFEST'))['files']))")"
echo "  compose_hash_before: $PREV_COMPOSE_HASH"
echo "  compose_hash_after: $(sha256sum "$DEPLOY_DIR/docker-compose.yml" 2>/dev/null | cut -d' ' -f1)"
echo ""

# ── Success: check hash failure BEFORE clearing rollback flag (PRD §10.2).
#    The order must be: if HASH_FAIL -> exit 1 (trap rolls back);
#    only then clear ROLLBACK_NEEDED=0 and exit 0.
echo "=== Deploy + verify complete ==="
if [ "$HASH_FAIL" -ne 0 ]; then
    echo "FAIL: verification failed." >&2
    exit 1  # global trap handles rollback
fi
ROLLBACK_NEEDED=0
