#!/usr/bin/env bash
# ── AI-DLC installer (v0.10 — install-targets) ──
# Idempotent. Does NOT fork, vendor, or modify any upstream source.
#
# The layout after landing:
#   supervisor/skills/claude/     → CC skills (ai-dlc, ai-dlc-doctor)
#                                   installed into each target's <config_dir>/skills/
#   supervisor/skills/workspace/  → workspace skills (ui-designer)
#                                   installed into the gateway workspace + registered
#   bin/                → report.py (human surface, G-DELIVER-1,
#                         MERGE_GATE) + plan.py (planning dispatch, close)
#   config/             → collapsed.config.yaml
#
# Retired earlier: the delegated plane (tag v0.5.1-delegated-final), the
# oracle plane (tag v0.8.0), the budget capability (landing L1 — no
# budget gate exists).
#
# Usage:
#   ./install.sh                          # full install (default CC target + workspace)
#   ./install.sh --target claude-glm      # specific registered target
#   ./install.sh --target-dir ~/.claude-x  # any CLAUDE_CONFIG_DIR, no JSON needed
#   ./install.sh --all-targets            # every target in targets/*.json
#   ./install.sh --uninstall --target <n> # remove what we installed (manifest-based)
#   ./install.sh --opendesign             # deploy the OpenDesign tree (host step)
#   ./install.sh --understand-anything    # deploy the Understand-Anything skill tree (host step)
#   ./install.sh --browser-verify         # deploy the Playwright MCP tree (host step)
#   ./install.sh --agent-bench            # deploy the Harbor/Terminal-Bench venv (host step)
#   ./install.sh --doctor                 # health check + sha256 consistency
#   ./install.sh --provision-plane        # open the plane runtime. Idempotent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS_DIR="${SCRIPT_DIR}/targets"
SUPERVISOR_DIR="${SCRIPT_DIR}/supervisor/skills"
CC_SKILLS_DIR="${SUPERVISOR_DIR}/claude"
WS_SKILLS_DIR="${SUPERVISOR_DIR}/workspace"
BIN_DIR="${SCRIPT_DIR}/bin"
PY=python3.12
OPENSPEC_VERSION="1.10.0"
MANIFEST_FILE="${AI_DLC_MANIFEST_FILE:-${SCRIPT_DIR}/.ai-dlc/install-manifest.json}"
WORKSPACE_SKILLS_DIR="${AI_DLC_SKILLS_DIR:-${HOME}/.jiuwenswarm/agent/workspace/skills}"

# the plane runtime (docs/plane-runtime.md is the living record). The
# AI_DLC_GW_* overrides exist for the test suite — they point the same
# code at fixture paths and a dead service so the edit paths and the
# did-not-come-back contract are provable without touching the live
# gateway; AI_DLC_SKIP_RESTART=1 skips the restart+wait (edit-path tests)
GW_CONFIG="${AI_DLC_GW_CONFIG:-${HOME}/.jiuwenswarm/config/config.yaml}"
GW_UNIT="${AI_DLC_GW_UNIT:-/etc/systemd/system/jiuwenswarm-gateway.service}"
GW_DROPIN_DIR="${GW_UNIT}.d"
GW_SERVICE="${AI_DLC_GW_SERVICE:-jiuwenswarm-gateway}"
RUNTIME_DIR=${HOME}/.jiuwenswarm

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
info() { echo -e "  $1"; }

# ── Doctor ────────────────────────────────────────────────────
run_doctor() {
  echo "AI-DLC Doctor — health check (v0.9 landing L4)"
  echo "══════════════════════════════════════════════════"
  local all_ok=true

  command -v git &>/dev/null && ok "git: $(git --version | head -1)" \
    || { fail "git not found"; all_ok=false; }
  command -v openspec &>/dev/null && ok "openspec CLI (the plane's validator)" \
    || warn "openspec not installed — spec skills unavailable until: npm i -g @fission-ai/openspec@${OPENSPEC_VERSION}"
  [[ -x "$PY" || -x "$(command -v python3.12 || true)" ]] && ok "python3.12" \
    || { fail "python3.12 not found"; all_ok=false; }

  # The executables we own: the human surface and the planning dispatch
  for f in bin/report.py bin/plan.py; do
    [[ -f "${SCRIPT_DIR}/${f}" ]] && ok "executable present: ${f}" \
      || { fail "missing: ${f}"; all_ok=false; }
  done
  [[ -f "${SCRIPT_DIR}/config/collapsed.config.yaml" ]] \
    && ok "config: collapsed.config.yaml" || { fail "missing collapsed config"; all_ok=false; }

  # Spec-validation smoke: the plan criterion must discriminate — a valid
  # change passes `openspec validate --strict`, a scenario-less
  # requirement is rejected. This validates STRUCTURE, not the artifact;
  # no machine check of correctness exists or is claimed. It runs in the
  # installer's shell (where the plane's tooling lives); a run's caller
  # never executes this — it reads signed verdict records instead.
  if command -v openspec &>/dev/null; then
    local t
    t=$(mktemp -d)
    (cd "${t}" && git init -q && git -c user.name=d -c user.email=d@d \
       commit -q --allow-empty -m s) >/dev/null 2>&1
    (cd "${t}" && openspec init --tools none --language en) >/dev/null 2>&1
    local c="${t}/openspec/changes/smoke"
    mkdir -p "${c}/specs/cap"
    printf '## Why\n\nSmoke.\n\n## What Changes\n\n- One requirement.\n' > "${c}/proposal.md"
    printf '## ADDED Requirements\n\n### Requirement: Smoke\n\nThe system SHALL smoke.\n\n#### Scenario: It runs\n\n- **WHEN** it runs\n- **THEN** it smokes\n' > "${c}/specs/cap/spec.md"
    local out
    out=$(cd "${t}" && openspec validate smoke --strict 2>&1 || true)
    if grep -q "valid" <<<"$out" && ! grep -q "has issues" <<<"$out"; then
      ok "validate smoke: well-formed change passes --strict"
    else
      fail "validate smoke: a valid change failed --strict: ${out}"
      all_ok=false
    fi
    printf '## ADDED Requirements\n\n### Requirement: Smoke\n\nThe system SHALL smoke.\n' > "${c}/specs/cap/spec.md"
    out=$(cd "${t}" && openspec validate smoke --strict 2>&1 || true)
    if grep -q "has issues" <<<"$out"; then
      ok "validate smoke: scenario-less requirement rejected (discriminates)"
    else
      fail "validate smoke: --strict accepted a requirement with no scenario"
      all_ok=false
    fi
    rm -rf "${t}"
  else
    warn "skipping validate smoke: openspec CLI not found"
  fi

  # Gateway reachability from the planning dispatch: the client it
  # invokes (same resolution plan.py uses), the service that client
  # talks to, and the config that service reads. A planning dispatch
  # fails without all three, so the doctor names the missing one.
  local client="${AI_DLC_CLIENT:-${HOME}/.local/bin/jiuwenswarm}"
  [[ -x "${client}" ]] && ok "planning client: ${client}" \
    || { fail "planning client missing: ${client} — the dispatch cannot invoke it"; all_ok=false; }
  local gw
  gw=$(systemctl is-active jiuwenswarm-gateway 2>/dev/null || true)
  if [[ "${gw}" == "active" ]]; then
    ok "gateway service: jiuwenswarm-gateway active"
  else
    fail "gateway service jiuwenswarm-gateway is ${gw:-unknown} — start it: systemctl start jiuwenswarm-gateway"
    all_ok=false
  fi
  local gwconf=${HOME}/.jiuwenswarm/config/config.yaml
  [[ -r "${gwconf}" ]] && ok "gateway config readable: ${gwconf}" \
    || { fail "gateway config not readable: ${gwconf} — the service cannot be configured"; all_ok=false; }

  # The plane runtime state (open-plane O1): whether the permission
  # engine is off, what the sandbox still grants, and what being open
  # removes — stated plainly, never as verification
  local audit engine p
  audit="$(plane_audit)"
  engine="$(plane_audit_field "$audit" engine)"
  if [[ "${engine}" == "false" ]]; then
    ok "permission engine: disabled — the plane is OPEN"
    info "what being open removes: inside the writable paths no tool call is"
    info "refused; the built-in high-severity shell rules (rm -rf, mkfs,"
    info "reverse shells) no longer ask — the systemd sandbox is the"
    info "only remaining boundary"
  elif [[ "${engine}" == "true" ]]; then
    warn "permission engine: enabled — the plane is CLOSED (a compound shell shape asks headless and fails the dispatch); './install.sh --provision-plane' opens it"
  else
    warn "permission engine state unreadable (${engine})"
  fi
  python3.12 -c 'import json,sys
for w in json.loads(sys.argv[1])["writable"]:
    print("writable: {}  (from {})".format(w["path"], w["source"]))' "$audit" \
    | while IFS= read -r p; do info "${p}"; done
  python3.12 -c 'import json,sys
print("\n".join(json.loads(sys.argv[1])["writable_extras"]))' "$audit" \
    | while IFS= read -r p; do
        if [[ -n "${p}" ]]; then
          warn "finding: writable path beyond the project root — ${p}"
        fi
      done

  # MaaS gateway credentials: warn (not fail) if API_KEY is empty in the
  # gateway .env — the gateway can still run for non-MaaS models, but the
  # planning dispatch to GLM-5.2 will fail without it.
  local env_file="${AI_DLC_ENV_FILE:-$HOME/.jiuwenswarm/config/.env}"
  if [[ -f "${env_file}" ]]; then
    local maas_key=""
    maas_key="$(grep '^API_KEY=' "${env_file}" 2>/dev/null | head -1 | cut -d= -f2- || true)"
    if [[ -n "${maas_key}" ]]; then
      ok "MaaS API_KEY present in ${env_file}"
    else
      warn "MaaS API_KEY empty or missing in ${env_file} — gateway dispatch to GLM-5.2 will fail. Run: ./install.sh --setup-maas-key"
    fi
  else
    warn "gateway .env not found at ${env_file} — run: ./install.sh --setup-maas-key"
  fi

  # OpenDesign tree: warn (not fail) if absent — only needed for design flow
  local od_root="${AI_DLC_OPENDESIGN_ROOT:-/opt/open-design}"
  if [[ -d "${od_root}" ]]; then
    ok "OpenDesign tree present: ${od_root}"
  else
    warn "OpenDesign tree missing — plan.py design will fail at D1. Run: ./install.sh --opendesign"
  fi

  # Understand-Anything tree: warn (not fail) if absent — only needed for codegraph
  local ua_root="${AI_DLC_UNDERSTAND_ANYTHING_ROOT:-/opt/understand-anything}"
  if [[ -d "${ua_root}" ]]; then
    ok "Understand-Anything tree present: ${ua_root}"
  else
    warn "Understand-Anything tree missing — plan.py codegraph will report unavailable. Run: ./install.sh --understand-anything"
  fi

  # Playwright MCP tree: warn (not fail) if absent — only needed for browser-verify
  local bv_root="${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}"
  if [[ -d "${bv_root}" ]]; then
    ok "Playwright MCP tree present: ${bv_root}"
  else
    warn "Playwright MCP tree missing — plan.py browser-verify will fail to dispatch. Run: ./install.sh --browser-verify"
  fi

  # Harbor/Terminal-Bench venv: warn (not fail) if absent — only needed for bench
  local ab_root="${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}"
  if [[ -d "${ab_root}" ]]; then
    ok "Harbor/Terminal-Bench venv present: ${ab_root}"
  else
    warn "Harbor/Terminal-Bench venv missing — plan.py bench will report unavailable. Run: ./install.sh --agent-bench"
  fi

  # Skills — three segments (N7):
  #   ① source completeness (claude/ + workspace/)
  #   ② manifest sha256 consistency (K5)
  #   ③ workspace registration count
  # ① source completeness
  for kind_dir in "${CC_SKILLS_DIR}" "${WS_SKILLS_DIR}"; do
    [[ -d "${kind_dir}" ]] || { fail "skill source dir missing: ${kind_dir}"; all_ok=false; continue; }
    for skill_dir in "${kind_dir}"/*/; do
      [[ -d "${skill_dir}" ]] || continue
      local sname; sname=$(basename "${skill_dir}")
      [[ -f "${skill_dir}/SKILL.md" ]] && ok "skill source: ${sname} ($(basename "${kind_dir}"))" \
        || { fail "skill source missing SKILL.md: ${sname}"; all_ok=false; }
    done
  done

  # ② manifest consistency (K5): each installed copy's sha256 must match
  if [[ -f "${MANIFEST_FILE}" ]]; then
    "$PY" - "${MANIFEST_FILE}" <<'MEOF'
import hashlib, json, sys, os
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
ok, fail = [], []
for entry in manifest.get("installs", []):
    path = entry.get("path", "")
    skill = entry.get("skill", "?")
    target = entry.get("target", "?")
    want = entry.get("sha256", "")
    if not os.path.isfile(path):
        fail.append(f"{target}/{skill}: installed file missing at {path}")
        continue
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h == want:
        ok.append(f"{target}/{skill}")
    else:
        fail.append(f"{target}/{skill}: sha256 mismatch (disk {h[:8]}… vs manifest {want[:8]}…)")
for o in ok:
    print(f"OK {o}")
for f in fail:
    print(f"FAIL {f}")
MEOF
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      if [[ "$line" == OK* ]]; then ok "manifest: ${line#OK }"
      else fail "manifest: ${line#FAIL }"; all_ok=false; fi
    done < <("$PY" - "${MANIFEST_FILE}" <<'MEOF2'
import hashlib, json, sys, os
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
for entry in manifest.get("installs", []):
    path = entry.get("path", ""); skill = entry.get("skill", "?"); target = entry.get("target", "?")
    want = entry.get("sha256", "")
    if not os.path.isfile(path):
        print(f"FAIL {target}/{skill}: installed file missing at {path}"); continue
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h == want: print(f"OK {target}/{skill}")
    else: print(f"FAIL {target}/{skill}: sha256 mismatch (disk {h[:8]}… vs manifest {want[:8]}…)")
MEOF2
)
  else
    warn "no manifest — run an install first (K4: no manifest = no verifiable install)"
  fi

  # ③ workspace registration: every shipped workspace skill is installed
  # and registered exactly once. The list of skills to verify is taken
  # from the shipped source (supervisor/skills/workspace/*/), not a hard-
  # coded subset, so a newly added skill can never again go uncovered the
  # way openspec-author did (INV-28). A missing SKILL.md at the installed
  # destination or a registration count other than 1 fails --doctor
  # (INV-29/30); a missing skills_state.json entirely stays a warn — an
  # uninitialized gateway workspace is a different condition from a
  # missing registration.
  local ws_state="${WORKSPACE_SKILLS_DIR}/skills_state.json"
  if [[ ! -f "${ws_state}" ]]; then
    warn "workspace skills_state.json not found at ${ws_state}"
  else
    for skill_dir in "${WS_SKILLS_DIR}"/*/; do
      [[ -d "${skill_dir}" ]] || continue
      local skill_name; skill_name=$(basename "${skill_dir}")
      local installed_skill_md="${WORKSPACE_SKILLS_DIR}/${skill_name}/SKILL.md"
      if [[ ! -f "${installed_skill_md}" ]]; then
        fail "workspace skill '${skill_name}' not installed: SKILL.md missing at ${installed_skill_md} (expected present, found absent)"
        all_ok=false
        continue
      fi
      local ws_count
      ws_count=$("$PY" -c "import json; st=json.load(open('${ws_state}')); print(sum(1 for x in st.get('installed_plugins',[]) if x.get('name')=='${skill_name}'))" 2>/dev/null || echo 0)
      if [[ "${ws_count}" == "1" ]]; then
        ok "workspace: ${skill_name} registered (1 entry, SKILL.md present)"
      else
        fail "workspace skill '${skill_name}' registration count is ${ws_count}, want 1 (in ${ws_state})"
        all_ok=false
      fi
    done
  fi

  echo "══════════════════════════════════════════════════"
  if [[ "${all_ok}" == "true" ]]; then ok "All checks passed"; return 0
  else fail "Some checks failed"; return 1; fi
}

# ── G4: install version sync check ─────────────────────────────
# Read-only: compare the repo's own VERSION against each installed
# target's VERSION. A mismatch (different content or a missing target
# VERSION file) is named on stdout; a registered target whose install
# dir no longer exists locally is skipped without error (the machine
# may be offline). Never modifies a target, never changes --doctor's
# exit code (advisory, not a gate — INV-25).
run_check_sync() {
  local repo_version=""
  if [[ -f "${SCRIPT_DIR}/VERSION" ]]; then
    repo_version="$(cat "${SCRIPT_DIR}/VERSION" 2>/dev/null || true)"
  fi
  local tfile name kind config_dir dest tv
  for tfile in "${SCRIPT_DIR}"/targets/*.json; do
    [[ -f "${tfile}" ]] || continue
    name=$("$PY" -c "import json;print(json.load(open('${tfile}')).get('name',''))" 2>/dev/null || echo "")
    kind=$("$PY" -c "import json;print(json.load(open('${tfile}')).get('kind',''))" 2>/dev/null || echo "")
    config_dir=$("$PY" -c "import json;print(json.load(open('${tfile}')).get('config_dir',''))" 2>/dev/null || echo "")
    config_dir="$(expand_tilde "${config_dir}")"
    # Only full-toolkit kinds carry VERSION (the same install path that
    # copies SKILL.md/config/). Other kinds install a single prose file
    # and have no version stamp to compare.
    case "${kind}" in
      codex-native-skill)   dest="${config_dir}/ai-dlc" ;;
      claude-native-skill)  dest="${config_dir}/skills/ai-dlc" ;;
      *) continue ;;
    esac
    # Registered target no longer present locally → skip (spec).
    [[ -d "${dest}" ]] || continue
    tv=""
    if [[ -f "${dest}/VERSION" ]]; then
      tv="$(cat "${dest}/VERSION" 2>/dev/null || true)"
    fi
    if [[ "${tv}" != "${repo_version}" ]]; then
      warn "version drift: ${name} (${dest}/VERSION) — repo='${repo_version}' target='${tv}'"
    fi
  done
  return 0
}

# ── The plane runtime: audit, provision, probe ────────────────

# The state the planning plane needs, read from where it lives: the
# permission-engine flag inside the permissions: block of the gateway
# config (the only lever that clears the shell structure floor — it
# short-circuits a layer above the tiered policy), and the writable
# grant the service unit carries (the sandbox is the only boundary the
# open runtime keeps). One JSON, read by both doctor and provisioning.
plane_audit() {
  "$PY" - "$GW_CONFIG" "$GW_UNIT" "$GW_DROPIN_DIR" "${HOME}/.jiuwenswarm" "${SCRIPT_DIR}" <<'EOF'
import glob, json, os, re, sys
cfg, unit, dropdir, gw_home, project_root = sys.argv[1:6]

def engine_state(path):
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return "unknown"
    inperm = False
    for ln in lines:
        if ln.startswith("permissions:"):
            inperm = True
        elif ln and not ln[0].isspace():
            inperm = False          # left the permissions: block
        if inperm:
            m = re.match(r"\s*enabled:\s*(\w+)", ln)
            if m:
                return m.group(1)
    return "absent"

writable = []
try:
    for ln in open(unit, encoding="utf-8").read().splitlines():
        if ln.startswith("ReadWritePaths="):
            writable.append({"path": ln.split("=", 1)[1].strip(),
                             "source": os.path.basename(unit)})
except OSError:
    pass
for conf in sorted(glob.glob(dropdir + "/*.conf")):
    try:
        for ln in open(conf, encoding="utf-8").read().splitlines():
            if ln.startswith("ReadWritePaths="):
                writable.append({"path": ln.split("=", 1)[1].strip(),
                                 "source": os.path.basename(conf)})
    except OSError:
        pass

allowed = {gw_home, project_root}
paths = {w["path"] for w in writable}
print(json.dumps({
    "engine": engine_state(cfg),
    "writable": writable,
    "writable_extras": sorted(paths - allowed),
    "writable_missing": sorted(allowed - paths),
    "config_edit_needed": engine_state(cfg) != "false",
    "unit_edit_needed": bool(allowed - paths) or bool(paths - allowed),
    "dropin_files": [os.path.basename(c)
                     for c in sorted(glob.glob(dropdir + "/*.conf"))],
}))
EOF
}

plane_audit_field() { # plane_audit_field <json> <key>
  "$PY" -c 'import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])' "$1" "$2"
}

# Disable the engine by editing the one enabled: line that sits inside
# the permissions: block — every other line passes through verbatim.
plane_set_engine_disabled() {
  "$PY" - "$GW_CONFIG" <<'EOF'
import re, sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines()
out, inperm, done = [], False, False
for ln in lines:
    if ln.startswith("permissions:"):
        inperm = True
    elif ln and not ln[0].isspace():
        inperm = False
    if inperm and not done and re.match(r"\s*enabled:", ln):
        out.append(re.sub(r"enabled:\s*\w+", "enabled: false", ln))
        done = True
        continue
    out.append(ln)
if not done:
    out2, inserted = [], False
    for ln in out:
        out2.append(ln)
        if ln.startswith("permissions:") and not inserted:
            out2.append("  enabled: false")
            inserted = True
    out, done = out2, inserted
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("edited" if done else "failed: no permissions: block")
EOF
}

# Rewrite the unit's writable grant to exactly the runtime directory and
# the project root, inside the [Service] section; every other line
# passes through verbatim.
plane_set_unit_paths() {
  "$PY" - "$GW_UNIT" "${HOME}/.jiuwenswarm" "${SCRIPT_DIR}" <<'EOF'
import sys
path, gw_home, project_root = sys.argv[1:4]
lines = open(path, encoding="utf-8").read().splitlines()
out = [ln for ln in lines if not ln.startswith("ReadWritePaths=")]
want = [f"ReadWritePaths={gw_home}", f"ReadWritePaths={project_root}"]
idx = len(out)
in_service = False
for i, ln in enumerate(out):
    if ln.strip() == "[Service]":
        in_service = True
    elif ln.startswith("[") and in_service:
        idx = i            # the first line after [Service] ends it
        break
out[idx:idx] = want
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("unit written")
EOF
}

plane_wait_gateway() {
  local port deadline
  port="$("$PY" -c "import re; m=re.search(r'GATEWAY_PORT=(\d+)', open('$GW_UNIT').read()); print(m.group(1) if m else '19001')" 2>/dev/null || echo 19001)"
  deadline=$((SECONDS + 90))
  while (( SECONDS < deadline )); do
    [[ "$(systemctl is-active "$GW_SERVICE" 2>/dev/null || true)" == "active" ]] \
      || { sleep 2; continue; }
    if "$PY" -c "import socket,sys; s=socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=2); s.close()" "$port" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# A configuration edit is not success on its own: prove the opening end
# to end with one command the closed state refuses — a redirection, a
# substitution and a pipe together — carrying a value generated at probe
# time, so a fabricated answer cannot pass. Dispatched through the
# shipped client; a missing value or an interrupt frame fails it.
plane_live_probe() {
  local client="${AI_DLC_CLIENT:-${HOME}/.local/bin/jiuwenswarm}"
  [[ -x "$client" ]] || { fail "planning client missing: $client — the probe cannot run"; return 1; }
  local epoch token upper probe_dir frames verdict
  epoch="$(date +%s)"
  token="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  upper="$(printf '%s' "$token" | tr 'a-z' 'A-Z')"
  probe_dir="$RUNTIME_DIR/plane-probe"
  mkdir -p "$probe_dir"
  frames="$probe_dir/probe-$epoch.jsonl"
  local cmd="echo $token > V.txt 2>/dev/null; cat \$(echo V.txt) | tr a-z A-Z"
  info "live probe (redirection + substitution + pipe, token generated now): $cmd"
  "$client" chat \
    "Run this exact shell command with the bash tool and reply with only its raw output, nothing else: $cmd" \
    --jsonl --cwd "$probe_dir" --mode code.normal --timeout 240 \
    --session "plane-probe-$epoch" > "$frames" 2>"$frames.stderr" || true
  verdict="$("$PY" - "$frames" "$upper" <<'EOF'
import json, sys
frames, want = sys.argv[1], sys.argv[2]
interrupted, text = False, []
try:
    lines = open(frames, encoding="utf-8", errors="replace").read().splitlines()
except OSError:
    lines = []
for line in lines:
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    p = d.get("payload") or {}
    ev = d.get("event") or d.get("type") or ""
    if ev in ("chat.ask_user_question", "plan.approval_required"):
        interrupted = True
    if ev == "chat.final" and isinstance(p.get("content"), str):
        text.append(p["content"])
    elif ev == "chat.delta" and isinstance(p.get("content"), str):
        text.append(p["content"])
joined = "".join(text)
print("token_returned={} interrupted={}".format(
    str(want in joined).lower(), str(interrupted).lower()))
EOF
)"
  rm -f "$probe_dir/V.txt"
  info "probe verdict: $verdict (frames: $frames)"
  [[ "$verdict" == "token_returned=true interrupted=false" ]]
}

provision_plane() {
  echo "AI-DLC Installer — plane provisioning (open-plane)"
  echo "══════════════════════════════════════════════════"
  [[ -r "$GW_CONFIG" ]] || { fail "gateway config not readable: $GW_CONFIG"; exit 1; }
  [[ -r "$GW_UNIT" ]] || { fail "service unit not readable: $GW_UNIT"; exit 1; }

  local audit epoch backups=() changed=false r
  audit="$(plane_audit)"
  epoch="$(date +%s)"

  if [[ "$(plane_audit_field "$audit" config_edit_needed)" == "True" ]]; then
    local cb="$GW_CONFIG.bak.pre-open-plane.$epoch"
    cp -a "$GW_CONFIG" "$cb"; backups+=("$cb")
    r="$(plane_set_engine_disabled)"
    [[ "$r" == "edited"* ]] || { fail "engine edit failed: $r"; exit 1; }
    ok "permission engine disabled — the only setting that clears the shell structure floor (backup: $cb)"
    changed=true
  else
    ok "permission engine already disabled"
  fi

  if [[ "$(plane_audit_field "$audit" unit_edit_needed)" == "True" ]]; then
    local ub="$GW_UNIT.bak.pre-open-plane.$epoch"
    cp -a "$GW_UNIT" "$ub"; backups+=("$ub")
    plane_set_unit_paths >/dev/null
    ok "service unit writable grant set to the runtime dir and the project root only (backup: $ub)"
    changed=true
  else
    ok "service unit already writable at exactly the runtime dir and the project root"
  fi

  # a drop-in can widen the grant behind the unit's back; provisioning
  # carries the writable-set contract, so one that names paths moves
  # aside (kept, never deleted)
  local dcount=0
  if [[ -d "$GW_DROPIN_DIR" ]]; then
    local conf keep="$GW_UNIT.bak.d.$epoch"
    for conf in "$GW_DROPIN_DIR"/*.conf; do
      [[ -f "$conf" ]] || continue
      if grep -q '^ReadWritePaths=' "$conf"; then
        mkdir -p "$keep"; mv "$conf" "$keep/"; dcount=$((dcount + 1)); changed=true
      fi
    done
    (( dcount > 0 )) && warn "$dcount drop-in(s) naming ReadWritePaths moved to $keep (kept, not deleted)"
  fi

  if [[ "$changed" == "false" ]]; then
    if [[ "$(systemctl is-active "$GW_SERVICE" 2>/dev/null || true)" == "active" ]]; then
      ok "already provisioned — no change, no restart"
    else
      warn "no config change, but the service is not active — restarting"
      systemctl restart "$GW_SERVICE" || true
      plane_wait_gateway || { fail "$GW_SERVICE did not accept connections; inspect: systemctl status $GW_SERVICE"; exit 1; }
    fi
  elif [[ "${AI_DLC_SKIP_RESTART:-0}" == "1" ]]; then
    warn "restart skipped (AI_DLC_SKIP_RESTART=1 — edit-path test; the probe still runs)"
  else
    info "daemon-reload + restart $GW_SERVICE"
    systemctl daemon-reload || true
    # the restart failing is the wait's to report: a dead unit must still
    # reach the backup-naming exit below, never die inside systemctl
    systemctl restart "$GW_SERVICE" || true
    if ! plane_wait_gateway; then
      fail "the gateway did not accept connections within the wait"
      if (( ${#backups[@]} )); then
        fail "restore from: ${backups[*]}"
        [[ -d "$GW_UNIT.bak.d.$epoch" ]] && fail "drop-ins kept at: $GW_UNIT.bak.d.$epoch"
      fi
      exit 1
    fi
    ok "gateway back and accepting connections"
  fi

  if plane_live_probe; then
    ok "live probe passed — the plane is open"
  else
    fail "the live probe did not prove the opening (token missing or an interrupt in the frames)"
    if (( ${#backups[@]} )); then fail "restore from: ${backups[*]}"; fi
    exit 1
  fi
  echo "══════════════════════════════════════════════════"
  ok "Plane provisioned. './install.sh --doctor' reports its state and cost."
}

# ── sha256 helper ─────────────────────────────────────────────
sha256_file() { "$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

# ── Manifest (K4, K8) ─────────────────────────────────────────
# Each install records target, kind, config_dir, skill, path, sha256,
# source, installed_at. Re-running with the same source is idempotent
# (only installed_at changes).
manifest_update() {
  # manifest_update <target> <kind> <config_dir> <skill> <path> <sha256> <source>
  local target="$1" kind="$2" config_dir="$3" skill="$4" path="$5" sha="$6" source="$7"
  local now; now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  mkdir -p "$(dirname "${MANIFEST_FILE}")"
  "$PY" - "${MANIFEST_FILE}" "$target" "$kind" "$config_dir" "$skill" "$path" "$sha" "$source" "$now" <<'MFEOF'
import json, os, sys
mfile, target, kind, config_dir, skill, path, sha, source, now = sys.argv[1:10]
try:
    manifest = json.load(open(mfile, encoding="utf-8"))
except (FileNotFoundError, json.JSONDecodeError):
    manifest = {"version": 1, "installs": []}
installs = manifest.get("installs", [])
# remove any prior entry for the same (target, skill) pair
installs = [e for e in installs
            if not (e.get("target") == target and e.get("skill") == skill)]
installs.append({"target": target, "kind": kind, "config_dir": config_dir,
                 "skill": skill, "path": path, "sha256": sha,
                 "source": source, "installed_at": now})
manifest["installs"] = installs
with open(mfile, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")
MFEOF
}

# ── Expand a leading ~ or ~/ in a path read from JSON ──────────
# targets/*.json config_dir values use `~` for portability (no
# machine-specific absolute paths in the shipped config). But a JSON
# string read via `python -c ... | var=$(...)` never passes through
# bash's own tilde expansion — that only happens for a literal
# unquoted tilde in shell source text, never for a variable's stored
# value — so config_dir would otherwise stay the literal 2-byte
# string "~/..." and every path built from it would be wrong. Expand
# it explicitly wherever a target's config_dir is read.
expand_tilde() {
  local p="$1"
  if [[ "${p}" == "~" ]]; then
    printf '%s' "${HOME}"
  elif [[ "${p}" == "~/"* ]]; then
    printf '%s/%s' "${HOME}" "${p#\~/}"
  else
    printf '%s' "${p}"
  fi
}

# ── Validate a config dir (K7) ────────────────────────────────
# Rejects nonexistent or unwritable dirs. Per R4, a legitimate but
# unrelated dir will be accepted — that is the cost of "any client".
validate_config_dir() {
  local config_dir="$1"
  [[ -d "${config_dir}" ]] || { fail "config dir does not exist: ${config_dir}"; return 1; }
  [[ -w "${config_dir}" ]] || { fail "config dir not writable: ${config_dir}"; return 1; }
  return 0
}

# ── Strip YAML frontmatter from a markdown file ───────────────
# Outputs the body (everything after the closing --- of the frontmatter)
# to stdout. If no frontmatter is present, outputs the full file.
strip_frontmatter() {
  "$PY" - "$1" <<'SFMEOF'
import sys
text = open(sys.argv[1], encoding="utf-8").read()
lines = text.splitlines(keepends=True)
if lines and lines[0].strip() == "---":
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            sys.stdout.write("".join(lines[i + 1:]))
            sys.exit(0)
sys.stdout.write(text)
SFMEOF
}

# ── Write content to a file with BEGIN/END markers (idempotent) ─
# If the file doesn't exist: create with markers.
# If the file exists and has markers: replace between markers.
# If the file exists without markers: append a marked section.
# Content is read from stdin; file path is $1.
write_with_markers() {
  local file="$1"
  # Save stdin content to a temp file (the Python heredoc consumes stdin
  # for the script itself, so we can't pipe content to Python directly).
  local content_tmp; content_tmp=$(mktemp)
  trap 'rm -f "${content_tmp}"' RETURN
  cat > "${content_tmp}"
  "$PY" - "$file" "${content_tmp}" <<'WMEOF'
import os, re, sys, tempfile
file_path = sys.argv[1]
content = open(sys.argv[2], encoding="utf-8").read()
begin = "<!-- BEGIN ai-dlc -->"
end = "<!-- END ai-dlc -->"
block = begin + "\n" + content + "\n" + end
try:
    existing = open(file_path, encoding="utf-8").read()
except FileNotFoundError:
    existing = ""
if begin in existing:
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    result = pattern.sub(block, existing)
else:
    if existing:
        if not existing.endswith("\n"):
            existing += "\n"
        result = existing + "\n" + block + "\n"
    else:
        result = block + "\n"
d = os.path.dirname(file_path) or "."
os.makedirs(d, exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=d)
os.write(fd, result.encode("utf-8"))
os.close(fd)
os.rename(tmp, file_path)
WMEOF
  rm -f "${content_tmp}"
}

# ── Install CC skills to a target (K1, K3, K6) ────────────────
# ── Build combined skill body (frontmatter-stripped, all CC skills) ──
# Sets the COMBINED_SKILL_BODY global to the concatenation of every
# supervisor/skills/claude/*/SKILL.md body (frontmatter stripped, blank-line
# separated). Returns 0 on success, 1 if any skill source is missing its
# SKILL.md. Shared by install_skills_to_target() (agents-md / cursor-rules /
# copilot-instructions) and gen_root_skill() so the two can never drift apart.
build_combined_skill_body() {
  COMBINED_SKILL_BODY=""
  local rc=0
  for skill_dir in "${CC_SKILLS_DIR}"/*/; do
    [[ -d "${skill_dir}" ]] || continue
    local skill_name; skill_name=$(basename "${skill_dir}")
    [[ -f "${skill_dir}/SKILL.md" ]] || { fail "skill source missing SKILL.md: ${skill_name}"; rc=1; continue; }
    local body
    body="$(strip_frontmatter "${skill_dir}/SKILL.md")"
    if [[ -n "${COMBINED_SKILL_BODY}" ]]; then
      COMBINED_SKILL_BODY="${COMBINED_SKILL_BODY}
${body}"
    else
      COMBINED_SKILL_BODY="${body}"
    fi
  done
  return "${rc}"
}

# ── Generate root SKILL.md for Codex native skill discovery ──────────
# Codex's built-in skill-installer downloads the entire repo directory to
# ~/.codex/skills/<name>/ and looks for a SKILL.md at that directory root.
# This writes such a file from the same combined body the other kinds use,
# with a frontmatter (name + description) and a note that the skill's own
# directory carries the full toolkit (bin/plan.py etc.) — run from there
# with --repo pointing at the project under development.
# Args: [out_file] — defaults to ${SCRIPT_DIR}/SKILL.md (repo root).
gen_root_skill() {
  local out_file="${1:-${SCRIPT_DIR}/SKILL.md}"
  build_combined_skill_body || { fail "could not build combined skill body"; return 1; }
  local combined_body="${COMBINED_SKILL_BODY}"
  [[ -n "${combined_body}" ]] || { fail "combined skill body is empty"; return 1; }
  {
    printf -- '---\n'
    printf 'name: ai-dlc\n'
    printf 'description: Spec-driven coding lifecycle for AI coding agents — executes a task through ROUTE→WORK→[DESIGN]→CHECK→REPORT→MERGE_GATE with a spec validator and a human-held merge gate. Use for multi-step or planned software engineering work in a git repo that wants a structured, auditable delivery flow with a signed spec verdict and an approved merge. Not for one-off quick answers, pure Q&A, or non-coding chat.\n'
    printf -- '---\n\n'
    cat <<'GINTRO'
This skill's own directory (wherever it was installed — e.g.
`~/.codex/skills/ai-dlc/`) also contains the full toolkit: `bin/plan.py`,
`bin/report.py`, `config/`, `openspec/`. Run those from this skill's own
directory, targeting whatever project you're actually developing with
`--repo <path-to-that-project>` — this skill's directory itself is the
tool, not the thing being worked on.

GINTRO
    printf '%s\n' "${combined_body}"
  } > "${out_file}"
  ok "Root SKILL.md generated → ${out_file}"
  return 0
}

# ── Copy the whole toolkit + generate SKILL.md at an exact destination ──
# (K1, K3, K6). Shared by codex-native-skill and claude-native-skill so
# a self-contained install (SKILL.md alongside bin/plan.py, config/,
# openspec/ — everything a `/ai-dlc` or Codex-skill invocation needs to
# actually run, not just read) never drifts between the two targets.
# Args: target_name kind config_dir dest (absolute path — caller decides
# whether that's <config_dir>/ai-dlc or <config_dir>/skills/ai-dlc).
install_full_toolkit() {
  local target_name="$1" kind="$2" config_dir="$3" dest="$4"
  info "Installing full toolkit to ${target_name} → ${dest}/"
  rm -rf "${dest}"
  mkdir -p "${dest}"
  cp -r "${SCRIPT_DIR}"/. "${dest}/"
  rm -rf "${dest}/.git" "${dest}/.ai-dlc" "${dest}/.pytest_cache" "${dest}/PUBLISH_NOTES.md"
  find "${dest}" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  gen_root_skill "${dest}/SKILL.md" || { fail "could not generate SKILL.md at ${dest}"; return 1; }
  # K6: read-back assert — the toolkit travelled, not just the SKILL.md
  if [[ ! -f "${dest}/SKILL.md" || ! -f "${dest}/bin/plan.py" ]]; then
    fail "read-back failed: ${dest}/SKILL.md or bin/plan.py missing after install"
    return 1
  fi
  # G4: VERSION travels with the toolkit (cp -r already carried it);
  # an explicit copy + read-back so a future copy-mode change can't
  # silently drop the version stamp --check-sync compares against.
  if [[ -f "${SCRIPT_DIR}/VERSION" ]]; then
    cp -f "${SCRIPT_DIR}/VERSION" "${dest}/VERSION"
    if [[ ! -f "${dest}/VERSION" ]]; then
      fail "read-back failed: ${dest}/VERSION missing after install"
      return 1
    fi
  fi
  local dst_sha; dst_sha=$(sha256_file "${dest}/SKILL.md")
  manifest_update "${target_name}" "${kind}" "${config_dir}" "ai-dlc" \
    "${dest}/SKILL.md" "${dst_sha}" "."
  ok "Full toolkit installed for ${target_name} (sha ${dst_sha:0:8}…)"
  return 0
}

# Dispatches by the target's `kind` field:
#   claude-skill         — copy SKILL.md into <config_dir>/skills/<name>/ (existing)
#   agents-md            — write AGENTS.md with BEGIN/END markers (idempotent)
#   cursor-rules         — write ai-dlc.mdc with Cursor frontmatter
#   copilot-instructions — write copilot-instructions.md with markers (idempotent)
#   codex-native-skill    — copy the whole toolkit into <config_dir>/ai-dlc/
#                          and generate SKILL.md there (Codex's own native
#                          skill-directory discovery, done locally)
#   claude-native-skill   — copy the whole toolkit into
#                          <config_dir>/skills/ai-dlc/ (config_dir is the
#                          agent's home, e.g. ~/.claude, matching the
#                          claude-skill convention) so /ai-dlc is
#                          self-contained instead of prose with no tools
install_skills_to_target() {
  local target_name="$1" config_dir="$2" kind="${3:-claude-skill}"

  # Targets whose config_dir is the literal <project-root> placeholder need
  # a real path at install time — skip them in --all-targets sweeps.
  if [[ "${config_dir}" == *"<project-root>"* ]]; then
    warn "skipping ${target_name}: config_dir has <project-root> placeholder — pass a real project path to install"
    return 0
  fi

  validate_config_dir "${config_dir}" || return 1

  # ── claude-skill: existing behaviour, unchanged (K1, K3, K6) ──
  if [[ "${kind}" == "claude-skill" ]]; then
    local skills_dir="${config_dir}/skills"
    mkdir -p "${skills_dir}"
    info "Installing CC skills to ${target_name} → ${skills_dir}/"
    local rc=0
    for skill_dir in "${CC_SKILLS_DIR}"/*/; do
      [[ -d "${skill_dir}" ]] || continue
      local skill_name; skill_name=$(basename "${skill_dir}")
      local dest="${skills_dir}/${skill_name}"
      rm -rf "${dest}"
      mkdir -p "${dest}"
      cp -r "${skill_dir}"* "${dest}/" 2>/dev/null || true
      # K6: read-back assert — the SKILL.md must exist and match source
      if [[ ! -f "${dest}/SKILL.md" ]]; then
        fail "read-back failed: ${dest}/SKILL.md not present after copy"
        rc=1; continue
      fi
      local src_sha dst_sha
      src_sha=$(sha256_file "${skill_dir}/SKILL.md")
      dst_sha=$(sha256_file "${dest}/SKILL.md")
      if [[ "${src_sha}" != "${dst_sha}" ]]; then
        fail "read-back sha mismatch for ${skill_name}: ${src_sha:0:8}… vs ${dst_sha:0:8}…"
        rc=1; continue
      fi
      manifest_update "${target_name}" "claude" "${config_dir}" "${skill_name}" \
        "${dest}/SKILL.md" "${dst_sha}" "supervisor/skills/claude/${skill_name}"
      info "  installed skill ${skill_name} (sha ${dst_sha:0:8}…)"
    done
    if [[ "${rc}" == "0" ]]; then ok "Skills installed for ${target_name}"; fi
    return "${rc}"
  fi

  # ── codex-native-skill: copy the whole toolkit + generate SKILL.md ──
  # (K1, K3, K6). Codex CLI's own remote skill-installer, when pointed at
  # this repo's GitHub tree, clones the whole directory into
  # $CODEX_HOME/skills/<name>/ — this does the same thing locally, for a
  # checkout you already have, without depending on Codex's own network
  # fetch path (which has its own separate reliability issues). config_dir
  # is the skills ROOT (e.g. ~/.codex/skills), matching the claude-skill
  # convention where config_dir is the agent's home and the function
  # appends the per-skill subdirectory itself.
  if [[ "${kind}" == "codex-native-skill" ]]; then
    install_full_toolkit "${target_name}" "${kind}" "${config_dir}" "${config_dir}/ai-dlc"
    return $?
  fi

  # ── claude-native-skill: same idea, Claude Code's own directory layout ──
  if [[ "${kind}" == "claude-native-skill" ]]; then
    install_full_toolkit "${target_name}" "${kind}" "${config_dir}" "${config_dir}/skills/ai-dlc"
    return $?
  fi

  # ── Non-claude-skill kinds: collect SKILL.md bodies (frontmatter stripped) ──
  info "Installing skills to ${target_name} (kind=${kind}) → ${config_dir}"
  local rc=0
  build_combined_skill_body || rc=$?
  local combined_body="${COMBINED_SKILL_BODY}"
  [[ "${rc}" != "0" ]] && return "${rc}"

  local dest_file=""
  case "${kind}" in
    agents-md)
      dest_file="${config_dir}/AGENTS.md"
      ;;
    cursor-rules)
      mkdir -p "${config_dir}"
      dest_file="${config_dir}/ai-dlc.mdc"
      ;;
    copilot-instructions)
      mkdir -p "${config_dir}"
      dest_file="${config_dir}/copilot-instructions.md"
      ;;
    *)
      fail "unknown kind: ${kind}"
      return 1
      ;;
  esac

  if [[ "${kind}" == "cursor-rules" ]]; then
    # Cursor .mdc: frontmatter + body, written directly (our file)
    {
      printf -- '---\n'
      printf 'description: AI-DLC spec-driven coding flow\n'
      printf 'alwaysApply: false\n'
      printf -- '---\n'
      printf '%s\n' "${combined_body}"
    } > "${dest_file}"
  else
    # agents-md and copilot-instructions: marker-based append/replace
    printf '%s' "${combined_body}" | write_with_markers "${dest_file}"
  fi

  # K6: read-back assert
  if [[ ! -f "${dest_file}" ]]; then
    fail "read-back failed: ${dest_file} not present after write"
    return 1
  fi
  local dst_sha; dst_sha=$(sha256_file "${dest_file}")
  manifest_update "${target_name}" "${kind}" "${config_dir}" "ai-dlc" \
    "${dest_file}" "${dst_sha}" "supervisor/skills/claude"
  info "  installed ${kind} content → ${dest_file} (sha ${dst_sha:0:8}…)"
  ok "Skills installed for ${target_name}"
  return 0
}

# ── Install workspace skills (N5, K6) ─────────────────────────
# Copies workspace/ skills into the gateway workspace and registers
# them in skills_state.json. Read-back assert per E6.
install_workspace_skills() {
  local ws_dir="${WORKSPACE_SKILLS_DIR}"
  mkdir -p "${ws_dir}"
  info "Installing workspace skills → ${ws_dir}/"
  local rc=0
  for skill_dir in "${WS_SKILLS_DIR}"/*/; do
    [[ -d "${skill_dir}" ]] || continue
    local skill_name; skill_name=$(basename "${skill_dir}")
    local dest="${ws_dir}/${skill_name}"
    rm -rf "${dest}"
    mkdir -p "${dest}"
    cp -r "${skill_dir}"* "${dest}/" 2>/dev/null || true
    # K6: read-back assert
    if [[ ! -f "${dest}/SKILL.md" ]]; then
      fail "read-back failed: ${dest}/SKILL.md not present after copy"
      rc=1; continue
    fi
    local dst_sha; dst_sha=$(sha256_file "${dest}/SKILL.md")
    # register in skills_state.json (E5 shape)
    local ws_state="${ws_dir}/skills_state.json"
    "$PY" - "${ws_state}" "${skill_name}" <<'WSEOF'
import datetime, json, os, sys
p, skill = sys.argv[1], sys.argv[2]
try:
    st = json.loads(open(p, encoding="utf-8").read())
except (FileNotFoundError, json.JSONDecodeError):
    st = {}
plug = st.setdefault("installed_plugins", [])
# remove prior entry for this skill, then re-add
plug[:] = [x for x in plug if x.get("name") != skill]
plug.append({"name": skill, "marketplace": "builtin", "version": "", "commit": "",
             "source": f"ai-dlc supervisor/skills/workspace/{skill}",
             "installed_at": datetime.datetime.now(
                 datetime.timezone.utc).isoformat()})
with open(p, "w", encoding="utf-8") as f:
    json.dump(st, f, indent=2, ensure_ascii=False)
    f.write("\n")
WSEOF
    # K6: read-back assert — count entries for this skill, must be exactly 1
    local read_back
    read_back=$("$PY" -c "import json; st=json.load(open('${ws_state}')); print(sum(1 for x in st.get('installed_plugins',[]) if x.get('name')=='${skill_name}'))" 2>/dev/null || echo 0)
    if [[ "${read_back}" != "1" ]]; then
      fail "registration read-back found '${read_back}' entries for ${skill_name} — refusing"
      rc=1; continue
    fi
    manifest_update "workspace" "workspace" "${ws_dir}" "${skill_name}" \
      "${dest}/SKILL.md" "${dst_sha}" "supervisor/skills/workspace/${skill_name}"
    info "  installed workspace skill ${skill_name} (sha ${dst_sha:0:8}…, registered)"
  done
  if [[ "${rc}" == "0" ]]; then ok "Workspace skills installed"; fi
  return "${rc}"
}

# ── Uninstall a target (N8, K2) ───────────────────────────────
# Only removes exact paths recorded in the manifest. Never globs,
# never mirror-syncs. feature-development is not in the manifest →
# never touched.
uninstall_target() {
  local target_name="$1"
  [[ -f "${MANIFEST_FILE}" ]] || { fail "no manifest at ${MANIFEST_FILE} — cannot determine what to remove (K2)"; exit 1; }
  info "Uninstalling target: ${target_name}"
  # extract entries for this target
  local entries
  entries=$("$PY" - "${MANIFEST_FILE}" "${target_name}" <<'UEOF'
import json, sys
mfile, target = sys.argv[1], sys.argv[2]
manifest = json.load(open(mfile, encoding="utf-8"))
for e in manifest.get("installs", []):
    if e.get("target") == target:
        print(f"{e.get('kind','?')}\t{e.get('skill','?')}\t{e.get('path','')}")
UEOF
)
  if [[ -z "${entries}" ]]; then
    warn "no manifest entries for target '${target_name}' — nothing to remove"
    return 0
  fi
  local rc=0
  while IFS=$'\t' read -r kind skill path; do
    [[ -n "${path}" ]] || continue
    if [[ "${kind}" == "codex-native-skill" ]]; then
      # this kind copies the whole toolkit, not just one file — remove
      # the entire skill directory (SKILL.md's own parent), not just
      # the recorded SKILL.md path
      local skill_root; skill_root="$(dirname "${path}")"
      if [[ -d "${skill_root}" ]]; then
        rm -rf "${skill_root}"
        ok "removed: ${target_name}/${skill} (${skill_root}/)"
      else
        warn "already absent: ${target_name}/${skill} (${skill_root}/)"
      fi
      continue
    fi
    if [[ -f "${path}" ]]; then
      rm -f "${path}"
      # remove the skill dir if empty
      local sdir; sdir="$(dirname "${path}")"
      rmdir "${sdir}" 2>/dev/null || true
      ok "removed: ${target_name}/${skill} (${path})"
    else
      warn "already absent: ${target_name}/${skill} (${path})"
    fi
    # for workspace entries, also unregister from skills_state.json
    if [[ "${kind}" == "workspace" ]]; then
      local ws_state="${WORKSPACE_SKILLS_DIR}/skills_state.json"
      if [[ -f "${ws_state}" ]]; then
        "$PY" - "${ws_state}" "${skill}" <<'UREOF'
import json, sys
p, skill = sys.argv[1], sys.argv[2]
st = json.loads(open(p, encoding="utf-8").read())
st["installed_plugins"] = [x for x in st.get("installed_plugins", [])
                           if x.get("name") != skill]
with open(p, "w", encoding="utf-8") as f:
    json.dump(st, f, indent=2, ensure_ascii=False)
    f.write("\n")
UREOF
      fi
    fi
  done <<< "${entries}"
  # remove this target's entries from the manifest
  "$PY" - "${MANIFEST_FILE}" "${target_name}" <<'UMEOF'
import json, sys
mfile, target = sys.argv[1], sys.argv[2]
manifest = json.load(open(mfile, encoding="utf-8"))
manifest["installs"] = [e for e in manifest.get("installs", [])
                        if e.get("target") != target]
with open(mfile, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")
UMEOF
  ok "Manifest cleaned for ${target_name}"
  return "${rc}"
}

# ── Ensure MaaS gateway credentials are configured ─────────────
# Every agent's planning-plane dispatch (bin/plan.py) resolves the same
# fixed client path (~/.local/bin/jiuwenswarm) reading the same shared
# ~/.jiuwenswarm/config/.env — the key is gateway-level, not per-agent.
# Whichever agent's install configured it first, every agent installed
# afterward (Claude, Codex, Cursor, Copilot) shares it for free; this
# only prompts when it's genuinely still missing, so a second/third
# agent install is silent. When the key is still missing after the
# attempt, the install hard-fails — a "successful" install with no
# credentials is a deferred failure that surfaces too late.

# Shared "is a key already present" check — used by both ensure_maas_key()
# and run_bootstrap() so the two never drift apart on what counts as
# "configured". Returns 0 (true) when a non-empty API_KEY line exists.
maas_key_present() {
  local env_file="${AI_DLC_ENV_FILE:-$HOME/.jiuwenswarm/config/.env}"
  local maas_key=""
  [[ -f "${env_file}" ]] && maas_key="$(grep '^API_KEY=' "${env_file}" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  [[ -n "${maas_key}" ]]
}

ensure_maas_key() {
  local env_file="${AI_DLC_ENV_FILE:-$HOME/.jiuwenswarm/config/.env}"
  if maas_key_present; then
    ok "MaaS API_KEY already configured (${env_file}) — shared by every installed agent"
    return 0
  fi
  if [[ -t 0 ]]; then
    echo ""
    echo "No MaaS API key configured yet — every installed agent shares one gateway,"
    echo "so this only needs to happen once."
    "${SCRIPT_DIR}/scripts/setup-maas-key.sh" --force \
      || { fail "MaaS API_KEY still not configured"; return 1; }
  else
    fail "MaaS API_KEY not configured and no key piped via stdin — install cannot proceed"
    fail "run './install.sh --setup-maas-key' interactively, or pipe a key: printf '%s\n' \"\$KEY\" | ./install.sh --setup-maas-key"
    return 1
  fi
  # Re-check after setup — the script may have exited 0 but left the key
  # empty (e.g. user pressed Enter at the hidden prompt).
  maas_key_present || { fail "MaaS API_KEY still empty after setup"; return 1; }
}

# ── Review axes configuration helpers ──────────────────────────
# After the per-target skill install loop, each target whose install
# copied config/collapsed.config.yaml gets an interactive prompt to
# pick review axes (presets or custom). Non-interactive environments
# skip with a warn — review axes ship with working factory defaults,
# so unlike the MaaS key this is not a hard failure.

# Compute the installed collapsed.config.yaml path for a target, or
# empty when the kind does not carry one (agents-md, cursor-rules,
# copilot-instructions only write a single prose file — no config/).
installed_config_path() {
  # installed_config_path <config_dir> <kind>
  local config_dir="$1" kind="$2"
  case "${kind}" in
    claude-native-skill) printf '%s' "${config_dir}/skills/ai-dlc/config/collapsed.config.yaml" ;;
    codex-native-skill)  printf '%s' "${config_dir}/ai-dlc/config/collapsed.config.yaml" ;;
    *) printf '' ;;
  esac
}

# Queue a config file for review-axes configuration if it exists on
# disk (the install may have failed or been skipped — only queue what
# actually landed).
maybe_queue_review_config() {
  # maybe_queue_review_config <config_dir> <kind>
  local config_dir="$1" kind="$2"
  local cfg_path
  cfg_path="$(installed_config_path "${config_dir}" "${kind}")"
  if [[ -n "${cfg_path}" && -f "${cfg_path}" ]]; then
    REVIEW_CONFIG_FILES+=("${cfg_path}")
  fi
  return 0
}

# Run setup-review-axes.sh for each queued config file. --configure-roles
# forces a re-prompt (passes --force); without it, the script skips
# targets that already differ from the factory default.
configure_review_axes() {
  local force_arg=""
  [[ "${configure_roles}" == "1" ]] && force_arg="--force"
  local cfg
  for cfg in "${REVIEW_CONFIG_FILES[@]:-}"; do
    [[ -n "${cfg}" ]] || continue
    if [[ ! -t 0 ]]; then
      warn "non-interactive environment — skipping review axes configuration for ${cfg}"
      warn "run './install.sh --configure-roles' interactively to pick review axes"
      continue
    fi
    "${SCRIPT_DIR}/scripts/setup-review-axes.sh" --config-file "${cfg}" ${force_arg} \
      || warn "review axes configuration skipped for ${cfg}"
  done
}

# ── Install upstream packages ────────────────────────────────
install_upstreams() {
  if ! command -v openspec &>/dev/null; then
    info "npm i -g @fission-ai/openspec@${OPENSPEC_VERSION}"
    npm i -g "@fission-ai/openspec@${OPENSPEC_VERSION}" 2>/dev/null && ok "openspec installed" \
      || warn "openspec install failed (optional — spec skills need the CLI)"
  else
    ok "openspec already available"
  fi
}

# ── Bootstrap: fresh-environment orchestration (PRD §3) ──────
run_bootstrap() {
  echo "AI-DLC Bootstrap — fresh environment setup"
  echo "══════════════════════════════════════════════════"
  echo "This will, in order:"
  echo "  1. openspec CLI          (npm package, <5MB, ~seconds)"
  echo "  2. jiuwenswarm gateway    (uv tool install, ~976MB, ~2-15 min depending on network)"
  echo "  3. Huawei Cloud MaaS key  (interactive prompt, one question)"
  echo "  4. OpenDesign tree        (git sparse clone, ~138MB, ~30s-3min)"
  echo "  5. Understand-Anything    (git sparse clone, ~16 files, ~10s)"
  echo "  6. Playwright MCP tree    (npm install, ~几十 MB, ~1-3min)"
  echo "  7. Harbor venv            (pip install, ~几十个包, ~1-3min)"
  echo "  8. AI-DLC skills          (local copy, instant)"
  echo ""
  echo "Continue? [y/N]"

  local answer=""
  if [[ -t 0 ]]; then
    read -r -p "> " answer
  else
    IFS= read -r answer || true
  fi
  if [[ "${answer}" != "y" && "${answer}" != "Y" ]]; then
    echo "Aborted."
    return 0
  fi

  local rc=0

  # ── Step 1/8: openspec ──
  echo ""
  echo "步骤 1/8 开始 — openspec CLI (npm package, <5MB, ~seconds)"
  local t0; t0=$(date +%s)
  install_upstreams || rc=1
  echo "步骤 1/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 2/8: jiuwenswarm ──
  echo ""
  echo "步骤 2/8 开始 — jiuwenswarm gateway (uv tool install, ~976MB, ~2-15 min)"
  t0=$(date +%s)
  if command -v jiuwenswarm &>/dev/null; then
    ok "jiuwenswarm already installed: $(command -v jiuwenswarm)"
  elif command -v uv &>/dev/null; then
    info "uv tool install jiuwenswarm==0.2.3 (verified available on public PyPI)"
    uv tool install jiuwenswarm==0.2.3 && ok "jiuwenswarm installed" \
      || { fail "jiuwenswarm install failed — check network or PyPI access"; rc=1; }
  else
    warn "uv not found — jiuwenswarm install command needs environment-specific configuration — see docs"
    warn "verified: jiuwenswarm==0.2.3 is available on public PyPI (https://pypi.org/pypi/jiuwenswarm)"
    warn "install uv first (https://docs.astral.sh/uv/), then: uv tool install jiuwenswarm==0.2.3"
    rc=1
  fi
  echo "步骤 2/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 3/8: MaaS key ──
  echo ""
  echo "步骤 3/8 开始 — Huawei Cloud MaaS key (interactive prompt)"
  t0=$(date +%s)
  if maas_key_present; then
    ok "MaaS API_KEY already configured — skipping prompt"
  elif [[ -t 0 ]]; then
    "${SCRIPT_DIR}/scripts/setup-maas-key.sh" --force || rc=1
    maas_key_present || { fail "MaaS API_KEY still not configured after setup"; rc=1; }
  else
    fail "MaaS API_KEY not configured and non-interactive environment — cannot proceed"
    fail "run './install.sh --setup-maas-key' interactively to configure credentials"
    rc=1
  fi
  echo "步骤 3/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 4/8: OpenDesign ──
  echo ""
  echo "步骤 4/8 开始 — OpenDesign tree (git sparse clone, ~138MB, ~30s-3min)"
  t0=$(date +%s)
  if [[ -d "${AI_DLC_OPENDESIGN_ROOT:-/opt/open-design}" ]]; then
    ok "OpenDesign tree already present: ${AI_DLC_OPENDESIGN_ROOT:-/opt/open-design}"
  else
    "${SCRIPT_DIR}/scripts/install-opendesign.sh" || rc=1
  fi
  echo "步骤 4/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 5/8: Understand-Anything ──
  echo ""
  echo "步骤 5/8 开始 — Understand-Anything skill tree (git sparse clone, ~16 files, ~10s)"
  t0=$(date +%s)
  if [[ -d "${AI_DLC_UNDERSTAND_ANYTHING_ROOT:-/opt/understand-anything}" ]]; then
    ok "Understand-Anything tree already present: ${AI_DLC_UNDERSTAND_ANYTHING_ROOT:-/opt/understand-anything}"
  else
    "${SCRIPT_DIR}/scripts/install-understand-anything.sh" --write-pin || rc=1
  fi
  echo "步骤 5/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 6/8: Playwright MCP (browser-verify) ──
  echo ""
  echo "步骤 6/8 开始 — Playwright MCP tree (npm install, ~几十 MB, ~1-3min)"
  t0=$(date +%s)
  if [[ -d "${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}" ]]; then
    ok "Playwright MCP tree already present: ${AI_DLC_PLAYWRIGHT_MCP_ROOT:-/opt/playwright-mcp}"
  else
    "${SCRIPT_DIR}/scripts/install-browser-verify.sh" --write-pin || rc=1
  fi
  echo "步骤 6/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 7/8: Harbor/Terminal-Bench (agent-bench) ──
  echo ""
  echo "步骤 7/8 开始 — Harbor venv (pip install, ~几十个包, ~1-3min)"
  t0=$(date +%s)
  if [[ -d "${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}" ]]; then
    ok "Harbor venv already present: ${AI_DLC_AGENT_BENCH_ROOT:-/opt/agent-bench}"
  else
    "${SCRIPT_DIR}/scripts/install-agent-bench.sh" --write-pin || rc=1
  fi
  echo "步骤 7/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  # ── Step 8/8: AI-DLC skills ──
  echo ""
  echo "步骤 8/8 开始 — AI-DLC skills (local copy, instant)"
  t0=$(date +%s)
  local tfile="${TARGETS_DIR}/claude.json"
  local tconfig tkind
  tconfig=$("$PY" -c "import json; print(json.load(open('${tfile}'))['config_dir'])" 2>/dev/null || echo "${HOME}/.claude")
  tconfig="$(expand_tilde "${tconfig}")"
  tkind=$("$PY" -c "import json; print(json.load(open('${tfile}')).get('kind','claude-skill'))" 2>/dev/null || echo "claude-skill")
  install_skills_to_target "claude-code" "${tconfig}" "${tkind}" || rc=1
  install_workspace_skills || rc=1
  echo "步骤 8/8 完成 — 实际耗时 $(( $(date +%s) - t0 ))s"

  echo ""
  echo "══════════════════════════════════════════════════"
  if [[ "${rc}" == "0" ]]; then
    ok "Bootstrap complete. Running doctor to verify…"
  else
    fail "Bootstrap completed with errors. Running doctor to diagnose…"
  fi
  echo ""
  run_doctor || true
}

# ── Main ─────────────────────────────────────────────────────
main() {
  local mode="install" target="" target_dir="" all_targets=0 uninstall=0
  local check_sync=0 configure_roles=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --doctor) mode="doctor"; shift ;;
      --check-sync) check_sync=1; shift ;;
      --provision-plane) mode="provision-plane"; shift ;;
      --opendesign) mode="opendesign"; shift ;;
      --understand-anything) mode="understand-anything"; shift ;;
      --browser-verify) mode="browser-verify"; shift ;;
      --agent-bench) mode="agent-bench"; shift ;;
      --setup-maas-key) mode="setup-maas-key"; shift ;;
      --bootstrap) mode="bootstrap"; shift ;;
      --quickstart) mode="quickstart"; shift ;;
      --gen-root-skill) mode="gen-root-skill"; shift ;;
      --target) target="$2"; shift 2 ;;
      --target-dir) target_dir="$2"; shift 2 ;;
      --all-targets) all_targets=1; shift ;;
      --uninstall) uninstall=1; shift ;;
      --configure-roles) configure_roles=1; shift ;;
      --help|-h)
        cat <<'HEOF'
Usage: install.sh [OPTIONS]

  (no flags)                 full install: default CC target (claude) + workspace
  --target <name>            specific registered target (targets/<name>.json)
  --target-dir <path>        any CLAUDE_CONFIG_DIR, no JSON needed
  --all-targets              every target in targets/*.json + workspace
  --uninstall --target <n>   remove what we installed (manifest-based, K2)
  --opendesign               deploy the OpenDesign tree (host step)
  --understand-anything      deploy the Understand-Anything skill tree (host step)
  --browser-verify           deploy the Playwright MCP tree (host step)
  --agent-bench              deploy the Harbor/Terminal-Bench venv (host step)
  --doctor                   health check + sha256 consistency (K5)
  --check-sync               compare the repo VERSION against each installed
                             target's VERSION; with --doctor, append mismatch
                             lines to its output (advisory, never fails the gate)
  --provision-plane          open the plane runtime
  --bootstrap                fresh-environment setup (openspec → jiuwenswarm → MaaS key → OpenDesign → Understand-Anything → skills)
  --setup-maas-key           interactive MaaS credential entry for the gateway
  --configure-roles          interactively pick review axes for each installed target
  --quickstart               print a minimal task sequence (N8)
  --gen-root-skill           (re)generate SKILL.md at the repo root for Codex
                             native skill-directory discovery
HEOF
        exit 0 ;;
      *) shift ;;
    esac
  done
  if [[ "${mode}" == "doctor" ]]; then
    run_doctor; local drc=$?
    if [[ "${check_sync}" == "1" ]]; then run_check_sync; fi
    exit "${drc}"
  fi
  if [[ "${check_sync}" == "1" ]]; then run_check_sync; exit 0; fi
  if [[ "${mode}" == "provision-plane" ]]; then provision_plane; exit $?; fi
  if [[ "${mode}" == "gen-root-skill" ]]; then
    gen_root_skill
    exit $?
  fi
  if [[ "${mode}" == "quickstart" ]]; then
    cat <<'QEOF'
AI-DLC quickstart — a minimal task (sourced from SKILL.md L0, not a second manual)

  # 1. ROUTE — stamp the task (1–3 files → inline; 4+ → planned)
  python3 bin/report.py init --task-dir <td> --repo <repo> \
    --route inline --task-id <id> --change <change-id>

  # 2. WORK — read, write code, run tests. For planned: get the spec verdict
  python3 bin/plan.py validate --change <change-id> --repo <repo>

  # 3. REPORT — measure landed files + spec validity
  python3 bin/report.py deliver --task-dir <td> --repo <repo> --outcome completed

  # 4. MERGE_GATE — request, human answers, then close
  python3 bin/report.py gate --request --task-dir <td> --repo <repo>
  # human: python3 bin/report.py gate --task-dir <td> \
  #   --decision approve --approver <name> --rationale <why>
  python3 bin/plan.py close --change <change-id> --repo <repo> --task-dir <td>

  # At any point, ask the system what to do next:
  python3 bin/plan.py next --task-dir <td> --repo <repo>
QEOF
    exit 0
  fi
  if [[ "${mode}" == "opendesign" ]]; then
    exec "${SCRIPT_DIR}/scripts/install-opendesign.sh" "$@"
  fi
  if [[ "${mode}" == "understand-anything" ]]; then
    exec "${SCRIPT_DIR}/scripts/install-understand-anything.sh" "$@"
  fi
  if [[ "${mode}" == "browser-verify" ]]; then
    exec "${SCRIPT_DIR}/scripts/install-browser-verify.sh" "$@"
  fi
  if [[ "${mode}" == "agent-bench" ]]; then
    exec "${SCRIPT_DIR}/scripts/install-agent-bench.sh" "$@"
  fi
  if [[ "${mode}" == "setup-maas-key" ]]; then
    exec "${SCRIPT_DIR}/scripts/setup-maas-key.sh" "$@"
  fi
  if [[ "${mode}" == "bootstrap" ]]; then
    run_bootstrap "$@"
    exit $?
  fi

  # --uninstall
  if [[ "${uninstall}" == "1" ]]; then
    if [[ -z "${target}" ]]; then
      fail "--uninstall requires --target <name>"
      exit 1
    fi
    uninstall_target "${target}"
    exit $?
  fi

  echo "AI-DLC Installer (v0.10 — install-targets)"
  echo "══════════════════════════════════════════════════"
  install_upstreams
  local rc=0
  REVIEW_CONFIG_FILES=()

  # --target-dir: install into an explicit path.  If --target <name> is also
  # given, read the real kind from targets/<name>.json so agents-md/cursor-rules/
  # copilot-instructions targets land in the right format (not always claude-skill).
  # Without --target, fall back to the legacy ad-hoc claude-skill behaviour.
  if [[ -n "${target_dir}" ]]; then
    if [[ -n "${target}" ]]; then
      local tfile="${TARGETS_DIR}/${target}.json"
      [[ -f "${tfile}" ]] || { fail "Unknown target: ${target}"; exit 1; }
      local tkind
      tkind=$("$PY" -c "import json; print(json.load(open('${tfile}')).get('kind','claude-skill'))" 2>/dev/null || echo "claude-skill")
      install_skills_to_target "${target}" "${target_dir}" "${tkind}" || rc=1
      maybe_queue_review_config "${target_dir}" "${tkind}"
    else
      install_skills_to_target "ad-hoc" "${target_dir}" || rc=1
      maybe_queue_review_config "${target_dir}" "claude-skill"
    fi

  # --all-targets: every registered target + workspace
  elif [[ "${all_targets}" == "1" ]]; then
    local tfile tname tconfig tkind
    for tfile in "${TARGETS_DIR}"/*.json; do
      [[ -f "${tfile}" ]] || continue
      tname=$("$PY" -c "import json; print(json.load(open('${tfile}'))['name'])" 2>/dev/null || basename "${tfile}" .json)
      tconfig=$("$PY" -c "import json; print(json.load(open('${tfile}'))['config_dir'])" 2>/dev/null || echo "")
      tconfig="$(expand_tilde "${tconfig}")"
      tkind=$("$PY" -c "import json; print(json.load(open('${tfile}')).get('kind','claude-skill'))" 2>/dev/null || echo "claude-skill")
      if [[ -z "${tconfig}" ]]; then
        fail "target ${tname}: no config_dir in ${tfile}"
        rc=1; continue
      fi
      install_skills_to_target "${tname}" "${tconfig}" "${tkind}" || rc=1
      maybe_queue_review_config "${tconfig}" "${tkind}"
    done
    install_workspace_skills || rc=1

  # --target <name>: registered CC target only
  elif [[ -n "${target}" ]]; then
    local tfile="${TARGETS_DIR}/${target}.json"
    [[ -f "${tfile}" ]] || { fail "Unknown target: ${target}"; exit 1; }
    local tconfig tkind
    tconfig=$("$PY" -c "import json; print(json.load(open('${tfile}'))['config_dir'])" 2>/dev/null || echo "")
    tconfig="$(expand_tilde "${tconfig}")"
    tkind=$("$PY" -c "import json; print(json.load(open('${tfile}')).get('kind','claude-skill'))" 2>/dev/null || echo "claude-skill")
    if [[ -z "${tconfig}" ]]; then
      fail "target ${target}: no config_dir in ${tfile}"
      exit 1
    fi
    if [[ "${tconfig}" == *"<project-root>"* ]]; then
      fail "target ${target}: config_dir is a placeholder — pass --target-dir <your-project-path> to install here"
      exit 1
    fi
    install_skills_to_target "${target}" "${tconfig}" "${tkind}" || rc=1
    maybe_queue_review_config "${tconfig}" "${tkind}"

  # default: claude target + workspace
  else
    local tfile="${TARGETS_DIR}/claude.json"
    local tconfig tkind
    if [[ -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
      # A launcher (claude-glm, claude-maas, ...) exports its own
      # CLAUDE_CONFIG_DIR before exec'ing the real claude binary — that
      # is the calling build's actual skill directory, which may not be
      # ~/.claude at all. Prefer it over the static targets/claude.json
      # value so a plain `./install.sh` run from inside any launcher's
      # session lands the skill where that build will actually look for
      # it, with no --target guessing required.
      tconfig="${CLAUDE_CONFIG_DIR}"
      info "CLAUDE_CONFIG_DIR is set — installing into the calling Claude Code build's own config dir: ${tconfig}"
    else
      tconfig=$("$PY" -c "import json; print(json.load(open('${tfile}'))['config_dir'])" 2>/dev/null || echo "${HOME}/.claude")
      tconfig="$(expand_tilde "${tconfig}")"
    fi
    tkind=$("$PY" -c "import json; print(json.load(open('${tfile}')).get('kind','claude-skill'))" 2>/dev/null || echo "claude-skill")
    install_skills_to_target "claude-code" "${tconfig}" "${tkind}" || rc=1
    maybe_queue_review_config "${tconfig}" "${tkind}"
    install_workspace_skills || rc=1
  fi

  if [[ -f ".gitignore" ]]; then
    grep -qF ".ai-dlc/tasks/" ".gitignore" 2>/dev/null || echo ".ai-dlc/tasks/" >> ".gitignore"
  fi
  ensure_maas_key || rc=1
  configure_review_axes
  echo "══════════════════════════════════════════════════"
  if [[ "${rc}" == "0" ]]; then
    ok "Install complete. Run './install.sh --doctor' to verify."
  else
    fail "Install completed with errors. Run './install.sh --doctor' to diagnose."
  fi
  echo "Layout:"
  echo "  claude/    → ai-dlc (execution) · ai-dlc-doctor → each target's <config_dir>/skills/"
  echo "  workspace/ → ui-designer → gateway workspace + skills_state.json"
  echo "  bin/       → report.py (human surface) · plan.py (planning dispatch + close)"
  echo "  gates      → G-DELIVER-1 (spec validity inside) · MERGE_GATE (human)"
  echo "  manifest   → .ai-dlc/install-manifest.json (K4 accounting, K5 consistency)"
  echo "  retired    → git history + tags (delegated: v0.5.1; oracle: v0.8.0; budget: L1)"
  return "${rc}"
}
main "$@"
