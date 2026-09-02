#!/usr/bin/env bash
# ── configure-gateway-model.sh ──────────────────────────────────────
# The gateway's model-request knobs — today: the GLM reasoning stream.
#
# Why this is a script and not a note: config.yaml is hand-edited, so a
# "regenerate" clobbers it (the litellm side already paid that price).
# Same shape as install-opendesign.sh section 3: back up, edit, read the
# file BACK and assert structurally — written is not standing until read
# back.
#
# What it sets, and why it must be extra_body:
#   openjiuwen turns every model_config_obj key into a NAMED kwarg on the
#   OpenAI SDK's create() call (common/reasoning_injector.py →
#   _build_model_request_kwargs). A bare `thinking:` therefore raises
#     TypeError: AsyncCompletions.create() got an unexpected keyword
#     argument 'thinking'
#   — measured live 2026-09-02, the gateway returned it on the first probe.
#   extra_body is the only vehicle that reaches the request body, where
#   Huawei MaaS expects `thinking` as a TOP-LEVEL field beside model and
#   messages.
#
# Measured on api-ap-southeast-1.modelarts-maas.com, glm-5.2, same prompt:
#   default            reasoning_tokens 471   completion_tokens 511
#   thinking disabled  reasoning_tokens   0   completion_tokens  55
#
# CAUTION: GLM-5.3 removed the ability to turn thinking off — sending
# "disabled" there is an error, not a no-op. Re-run with --enable (or
# --check first) whenever MODEL_NAME moves off 5.2.
#
# Usage:
#   ./configure-gateway-model.sh --disable-thinking   # default
#   ./configure-gateway-model.sh --enable-thinking
#   ./configure-gateway-model.sh --check              # assert only, no write
set -euo pipefail

GW_CONFIG="${AI_DLC_GW_CONFIG:-${HOME}/.jiuwenswarm/config/config.yaml}"
GW_SERVICE="${AI_DLC_GW_SERVICE:-jiuwenswarm-gateway}"
PY="${AI_DLC_GW_PY:-${HOME}/.local/share/uv/tools/jiuwenswarm/bin/python}"
MODE="disable"

say()  { echo "configure-gateway-model: $1"; }
die()  { echo "configure-gateway-model: $1" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --disable-thinking) MODE="disable"; shift ;;
    --enable-thinking)  MODE="enable";  shift ;;
    --check)            MODE="check";   shift ;;
    --config)           GW_CONFIG="$2"; shift 2 ;;
    --help|-h) sed -n '2,32p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -f "$GW_CONFIG" ]] || die "no gateway config at $GW_CONFIG"
# yaml lives in the gateway's own venv, not the system python
[[ -x "$PY" ]] || PY="$(command -v python3.12 || command -v python3)"
"$PY" -c "import yaml" 2>/dev/null || die "no python with pyyaml (tried $PY)"

# ── the desired state ───────────────────────────────────────────────
if [[ "$MODE" == "enable" ]]; then WANT="enabled"; else WANT="disabled"; fi

# ── check: structural read-back, no write ───────────────────────────
assert_state() {
  local want="$1"
  GW_CONFIG="$GW_CONFIG" WANT="$want" "$PY" - <<'PYEOF'
import os, sys, yaml
cfg = yaml.safe_load(open(os.environ["GW_CONFIG"], encoding="utf-8"))
want = os.environ["WANT"]
try:
    mco = cfg["models"]["defaults"][0]["model_config_obj"]
except (KeyError, IndexError, TypeError):
    sys.exit("models.defaults[0].model_config_obj not found — "
             "the config shape moved; fix by hand")
# the bare key is the failure mode this script exists to prevent
if "thinking" in mco:
    sys.exit("a bare `thinking` key stands in model_config_obj — it becomes "
             "a named kwarg and the SDK rejects it; it must live under "
             "extra_body")
got = (mco.get("extra_body") or {}).get("thinking")
if got != {"type": want}:
    sys.exit(f"read-back mismatch: extra_body.thinking is {got!r}, "
             f"expected {{'type': '{want}'}}")
print(f"  model_config_obj = {mco}")
PYEOF
}

if [[ "$MODE" == "check" ]]; then
  say "checking $GW_CONFIG"
  assert_state "$WANT" || die "check failed"
  say "OK — extra_body.thinking is '$WANT'"
  exit 0
fi

# ── idempotence: already in the desired state? ──────────────────────
if assert_state "$WANT" >/dev/null 2>&1; then
  say "already set — extra_body.thinking is '$WANT', nothing to do"
  exit 0
fi

# ── back up, then edit ──────────────────────────────────────────────
BACKUP="$GW_CONFIG.bak.$(date +%s)"
cp "$GW_CONFIG" "$BACKUP"
say "backup: $BACKUP"

GW_CONFIG="$GW_CONFIG" WANT="$WANT" "$PY" - <<'PYEOF'
import os, pathlib, re, sys

cfg = pathlib.Path(os.environ["GW_CONFIG"])
want = os.environ["WANT"]
text = cfg.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

# Locate models.defaults[0].model_config_obj by structure, not by a fixed
# line number: the block is 6-space indented under the first defaults entry.
start = None
for i, line in enumerate(lines):
    if line.rstrip("\n") == "      model_config_obj:":
        start = i
        break
if start is None:
    sys.exit("models.defaults[0].model_config_obj block not found — "
             "the config shape moved; fix by hand")

# The block runs until a line indented 6 spaces or less that is not blank.
end = len(lines)
for j in range(start + 1, len(lines)):
    s = lines[j]
    if not s.strip():
        continue
    indent = len(s) - len(s.lstrip(" "))
    if indent <= 6:
        end = j
        break

body = lines[start + 1:end]
# drop any prior thinking/extra_body wiring and our own comment block, so
# re-running does not stack duplicates
cleaned, skip_until_indent = [], None
for s in body:
    if not s.strip():
        continue
    indent = len(s) - len(s.lstrip(" "))
    if skip_until_indent is not None:
        if indent > skip_until_indent:
            continue
        skip_until_indent = None
    key = s.strip()
    if key.startswith("#"):
        continue
    if re.match(r"^(extra_body|thinking):", key):
        skip_until_indent = indent
        continue
    cleaned.append(s)

block = [
    "        # GLM reasoning stream. model_config_obj keys become NAMED\n",
    "        # kwargs on the OpenAI SDK create() call, so a bare `thinking:`\n",
    "        # raises TypeError: unexpected keyword argument 'thinking'.\n",
    "        # extra_body is what reaches the request body, where Huawei\n",
    "        # MaaS expects thinking beside model/messages.\n",
    "        # Managed by scripts/configure-gateway-model.sh — edit there.\n",
    "        extra_body:\n",
    "          thinking:\n",
    f"            type: {want}\n",
]
lines[start + 1:end] = cleaned + block
cfg.write_text("".join(lines), encoding="utf-8")
print(f"  wrote extra_body.thinking.type = {want}")
PYEOF

# ── the read-back assert: written is not standing until read back ───
assert_state "$WANT" || {
  say "read-back FAILED — restoring $BACKUP"
  cp "$BACKUP" "$GW_CONFIG"
  die "the config did not survive the read-back; original restored"
}
say "read-back OK"

# ── restart: the gateway reads this at start, not per request ───────
# A restart kills in-flight streams, so refuse while a session is live
# unless the caller insists.
if systemctl is-active --quiet "$GW_SERVICE" 2>/dev/null; then
  live=$(find ${HOME}/.jiuwenswarm/agent/sessions -name history.jsonl \
           -newermt '-2 minutes' 2>/dev/null | wc -l)
  if [[ "${live:-0}" -gt 0 && "${AI_DLC_FORCE_RESTART:-0}" != "1" ]]; then
    say "WARNING: $live session(s) wrote frames in the last 2 minutes."
    say "         Not restarting — a restart kills in-flight streams."
    say "         Re-run with AI_DLC_FORCE_RESTART=1, or restart by hand:"
    say "           systemctl restart $GW_SERVICE"
    exit 0
  fi
  systemctl restart "$GW_SERVICE"
  for _ in $(seq 1 30); do
    systemctl is-active --quiet "$GW_SERVICE" && break
    sleep 1
  done
  systemctl is-active --quiet "$GW_SERVICE" \
    || die "gateway did not come back after restart"
  say "gateway restarted and active"
else
  say "gateway not running — start it to pick this up"
fi

say "done — thinking '$WANT'. Verify with: --check, then one live dispatch"
