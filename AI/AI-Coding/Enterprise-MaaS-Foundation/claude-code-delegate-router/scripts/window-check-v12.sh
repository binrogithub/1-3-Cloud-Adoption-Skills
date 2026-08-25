#!/usr/bin/env bash
# window-check-v12.sh — PRD RELEASE_V12 §3 gate checker (N1-G / N2-G / N4-G / N5-G).
#
# Usage:
#   scripts/window-check-v12.sh            # evaluate all gates now
#   scripts/window-check-v12.sh --record   # ALSO stamp window-open evidence
#                                         # (timestamp + commit + counters) to
#                                         # /etc/claude-code-proxy/window-v12.json
#
# Gates (PRD RELEASE_V12 §3, N1-G per PRD_UPSTREAM_PROFILE_V1 D10):
#   N1-G (option B) — every project-derived listener is compliant: build
#                     matches the repo, anonymous requests get 401, the
#                     systemd unit carries the hardening directives.
#   N2-G            — :3001 not listening; no argrepro/capture autostart.
#   N4-G            — accounting identity: stop_reasons counts only
#                     completed requests, request_end counts every request.
#                     sum(stop_reasons) + request_end-with-null-stop_reason
#                     == request_end total (failures are the difference by
#                     design — server.js sets failed stop_reason to null).
#   N5-G            --record only: stamps the window start; a later plain run
#                     additionally reports elapsed time and request volume.
#
# Exit codes: 0 = all gates PASS (v1.2 may be tagged if N5 has also elapsed),
# 1 = at least one gate FAILED, 2 = usage error.
set -euo pipefail

SERVICE="${V12_SERVICE:-claude-code-maas-proxy.service}"
PORT="${V12_PORT:-3000}"
WINDOW_FILE="${V12_WINDOW_FILE:-/etc/claude-code-proxy/window-v12.json}"
MIN_REQUESTS="${V12_MIN_REQUESTS:-200}"
MIN_HOURS="${V12_MIN_HOURS:-24}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RECORD="no"
[[ "${1:-}" == "--record" ]] && RECORD="yes"
[[ $# -eq 0 ]] || [[ "$RECORD" == "yes" ]] || { echo "usage: $0 [--record]" >&2; exit 2; }

fail() { echo "  FAIL: $*" >&2; OVERALL=1; }

OVERALL=0

###############################################################################
# N1-G (option B): every project-derived listener must be COMPLIANT
#
# PRD UPSTREAM_PROFILE_V1 D10: the maintainer decision moved from
# "single listener" (A) to "multiple profiles allowed, each compliant" (B).
# The gate keeps what the original wanted to prevent — unmanaged, unhardened,
# unauthenticated clones like the :3001 capture process — while allowing
# per-profile instances. Each listener must satisfy:
#   (a) sha256(server.js) matches the repo build;
#   (b) enforced client auth (anonymous 401);
#   (c) the systemd unit carries the hardening directives.
###############################################################################

echo "[N1-G] every project-derived listener is compliant (option B)"

_repo_server_sha=""
for _cand in "$PROJECT_ROOT/adapter/server.js"; do
    if [[ -f "$_cand" ]]; then
        _repo_server_sha="$(sha256sum "$_cand" | awk '{print $1}')"
    fi
done

_count_checked=0
_count_bad=0
while read -r line; do
    # lines look like: LISTEN 0 511 127.0.0.1:3100 0.0.0.0:* users:(("node",pid=1,fd=2))
    port=$(printf '%s' "$line" | awk '{print $4}' | sed 's/.*://')
    [[ "$port" =~ ^[0-9]+$ ]] || continue
    printf '%s' "$line" | grep -q '"node"' || continue
    pid=$(printf '%s' "$line" | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
    [[ -n "$pid" ]] || continue
    cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
    case "$cmdline" in
        *server.js*|*claude-glm-proxy*|*claude-code-maas-proxy*|*server_capture*)
            ;;
        *)
            continue
            ;;
    esac
    _count_checked=$((_count_checked + 1))

    # (a) build matches repo
    _srv=""
    for tok in $cmdline; do
        case "$tok" in
            */server.js) _srv="$tok" ;;
        esac
    done
    _sha=""
    [[ -n "$_srv" && -f "$_srv" ]] && _sha="$(sha256sum "$_srv" | awk '{print $1}')"
    if [[ -z "$_repo_server_sha" || "$_sha" != "$_repo_server_sha" ]]; then
        fail "listener :$port build mismatch (want ${_repo_server_sha:0:12}, got ${_sha:0:12:-none})"
        _count_bad=$((_count_bad + 1))
        continue
    fi

    # (b) enforced auth: anonymous request must be 401
    _code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
        -X POST "http://127.0.0.1:$port/v1/messages" \
        -H 'content-type: application/json' \
        -d '{"model":"probe","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}' \
        2>/dev/null || echo 000)"
    if [[ "$_code" != "401" ]]; then
        fail "listener :$port auth not enforced (anonymous got HTTP $_code, want 401)"
        _count_bad=$((_count_bad + 1))
        continue
    fi

    # (c) systemd unit hardening
    _unit=""
    for _u in $(ls /etc/systemd/system/*.service 2>/dev/null); do
        if grep -q "ExecStart=.*$(basename "${_srv:-x}")" "$_u" 2>/dev/null; then
            _unit="$_u"; break
        fi
    done
    _hard_ok="yes"
    if [[ -n "$_unit" ]]; then
        for _dir in NoNewPrivileges=yes ProtectSystem=strict ProtectHome=yes; do
            grep -q "^${_dir}" "$_unit" 2>/dev/null || _hard_ok="no"
        done
    else
        _hard_ok="no"  # no unit at all = unmanaged
    fi
    if [[ "$_hard_ok" != "yes" ]]; then
        fail "listener :$port systemd hardening incomplete or missing unit"
        _count_bad=$((_count_bad + 1))
        continue
    fi

    echo "  ok: :$port (build ✓ auth ✓ hardened ✓)"
done < <(ss -tlnp 2>/dev/null | tail -n +2)

if [[ "$_count_bad" -eq 0 ]]; then
    echo "  PASS: ${_count_checked} project-derived listener(s), all compliant"
fi

###############################################################################
# N2-G: :3001 gone, no autostart for the capture clone
###############################################################################

echo "[N2-G] capture service (:3001) offline"
if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE ':3001$'; then
    fail "port 3001 is still listening"
else
    echo "  PASS: :3001 not listening"
fi
if pgrep -af "server_capture" >/dev/null 2>&1; then
    fail "server_capture process is running"
else
    echo "  PASS: no server_capture process"
fi
AUTOSTART=$( { crontab -l 2>/dev/null || true; } | grep -ci "argrepro\|server_capture" || true)
if [[ "$AUTOSTART" -eq 0 ]] && ! ls /etc/systemd/system/*.service 2>/dev/null | grep -qi "argrepro\|capture-proxy"; then
    echo "  PASS: no autostart entries"
else
    fail "autostart entries found for the capture clone"
fi

###############################################################################
# N4-G: request accounting identity (PRD RELEASE_V13 S1)
#
# The OLD assertion (sum(stop_reasons) == request_end) rests on a false
# premise: it assumed both counters reset together and counted the same
# events. They do not — failed requests emit request_end with
# stop_reason:null (by design, server.js streaming/nonstream finally) and
# are excluded from /status stop_reasons. The gate was permanently red in
# production (measured 124 vs 125 with exactly 1 failed request) and a
# permanently-red gate trains people to ignore it, masking real regressions.
#
# Correct identity:
#   sum(stop_reasons) + count(request_end with stop_reason null)
#     == count(request_end)
# Holds with zero failures (0 + N == N) and with any number of them.
###############################################################################

echo "[N4-G] request accounting identity (stop_reasons + null-stop == request_end)"
BOOT_TS=$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value)
if [[ -z "$BOOT_TS" ]]; then
    fail "cannot read service boot time for $SERVICE"
else
    # Test hooks (same pattern as VERIFY_TEST_HELPERS_DIR): a file-based
    # /status and journal source let the contract tests drive this gate with
    # synthetic failures. Production defaults remain curl + journalctl.
    if [[ -n "${V12_STATUS_FILE:-}" && -f "${V12_STATUS_FILE:-}" ]]; then
        STATUS_JSON_SRC="cat \"$V12_STATUS_FILE\""
    else
        STATUS_JSON_SRC="curl -sf --max-time 5 \"http://127.0.0.1:$PORT/status\""
    fi
    STATUS_SUM=$(eval "$STATUS_JSON_SRC" \
        | python3 -c 'import json,sys; print(sum(json.load(sys.stdin)["stop_reasons"].values()))' 2>/dev/null || echo "")
    if [[ -n "${V12_JOURNAL_FILE:-}" && -f "${V12_JOURNAL_FILE:-}" ]]; then
        JOURNAL_SRC="cat \"$V12_JOURNAL_FILE\""
    else
        JOURNAL_SRC="journalctl -u \"$SERVICE\" --since \"$BOOT_TS\" --no-pager 2>/dev/null"
    fi
    read -r JOURNAL_N NULL_N <<<"$(eval "$JOURNAL_SRC" \
        | python3 -c '
import json, sys
total = nulls = 0
for line in sys.stdin:
    i = line.find("{")
    if i < 0:
        continue
    try:
        obj = json.loads(line[i:])
    except Exception:
        continue
    if obj.get("type") == "request_end":
        total += 1
        if obj.get("stop_reason") is None:
            nulls += 1
print(total, nulls)
' 2>/dev/null || echo "0 0")"
    if [[ -z "$STATUS_SUM" ]]; then
        fail "cannot read /status from 127.0.0.1:$PORT"
    elif [[ "$((STATUS_SUM + NULL_N))" == "$JOURNAL_N" ]]; then
        echo "  PASS: stop_reasons ($STATUS_SUM) + null-stop ($NULL_N) == request_end ($JOURNAL_N)"
    else
        fail "accounting drift: stop_reasons ($STATUS_SUM) + null-stop ($NULL_N) != request_end ($JOURNAL_N) — a request path is unlogged or double-counted"
    fi
fi

###############################################################################
# N5-G: soak window bookkeeping
###############################################################################

echo "[N5-G] soak window"
if [[ "$RECORD" == "yes" ]]; then
    BOOT_EPOCH=$(date -d "$BOOT_TS" +%s 2>/dev/null || date +%s)
    STATUS_SUM_NOW=$(curl -sf --max-time 5 "http://127.0.0.1:$PORT/status" \
        | python3 -c 'import json,sys; print(sum(json.load(sys.stdin)["stop_reasons"].values()))' 2>/dev/null || echo 0)
    COMMIT=$(git -C "$(dirname "$0")/.." rev-parse HEAD 2>/dev/null || echo unknown)
    python3 - "$WINDOW_FILE" "$BOOT_EPOCH" "$STATUS_SUM_NOW" "$COMMIT" <<'PYEOF'
import json, sys, os
path, boot, base, commit = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
window = {"window_open_epoch": boot, "baseline_requests": base, "commit": commit}
tmp = path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(window, fh, indent=2)
    fh.write("\n")
os.chmod(tmp, 0o644)
os.replace(tmp, path)
print(f"  recorded: window open @ epoch {boot}, baseline {base} requests, commit {commit[:12]}")
PYEOF
    echo "  (N5 is a time gate — re-run without --record after $MIN_HOURS h)"
else
    if [[ ! -f "$WINDOW_FILE" ]]; then
        echo "  NOTE: no window recorded yet — run with --record to open one"
    else
        OPEN_EPOCH=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["window_open_epoch"])' "$WINDOW_FILE")
        BASELINE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["baseline_requests"])' "$WINDOW_FILE")
        ELAPSED_H=$(python3 -c "import time; print(round((time.time() - $OPEN_EPOCH) / 3600, 2))")
        # Count request_end since the recorded window open (not boot).
        WIN_REQ=$(journalctl -u "$SERVICE" --since "@$OPEN_EPOCH" --no-pager 2>/dev/null \
            | grep -c '"type":"request_end"' || true)
        echo "  elapsed: ${ELAPSED_H}h / ${MIN_HOURS}h required"
        echo "  request_end in window: $WIN_REQ / $MIN_REQUESTS required"
        AUTH_REJ=$(journalctl -u "$SERVICE" --since "@$OPEN_EPOCH" --no-pager 2>/dev/null \
            | grep -c '"code":"MAAS_AUTH_REJECTED"' || true)
        echo "  MASS_AUTH_REJECTED events: $AUTH_REJ (each must be explainable)"
        OK_AGE=$(python3 -c "import time; print('yes' if (time.time() - $OPEN_EPOCH) >= $MIN_HOURS * 3600 else 'no')")
        if [[ "$OK_AGE" == "yes" && "${WIN_REQ:-0}" -ge "$MIN_REQUESTS" ]]; then
            echo "  PASS: window satisfied — v1.2 may be tagged"
        else
            echo "  PENDING: window not yet satisfied (not a failure — time gate)"
        fi
    fi
fi

echo ""
if [[ "$OVERALL" -eq 0 ]]; then
    echo "window-check: N1-G/N2-G/N4-G PASS${N5_NOTE:+, $N5_NOTE}"
    exit 0
fi
echo "window-check: one or more gates FAILED" >&2
exit 1
