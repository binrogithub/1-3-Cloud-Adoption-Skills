#!/usr/bin/env bash
# L4 (landing tasks 4.1-4.4): the health check describes the runtime
# that exists. It checks the executables we own (report.py AND plan.py),
# keeps the strict-validation discrimination smoke, reaches for the
# planning client the dispatch actually invokes, the gateway service it
# talks to and the config that service reads — and never mentions a
# cost or budget gate (none exists). Reverse: with the gateway
# unreachable, the check fails and names the missing reachability
# setting; with the planning client missing, it fails naming the client.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# 1. (4.3) no cost or budget gate reference survives anywhere in the
#    installer (the phrase "no budget gate exists" states an absence)
grep -qE 'G-COST|cost gate|--cap |report\.py (bill|cost)' "$ROOT/install.sh" \
  && { echo "FAIL: install.sh still references a cost/budget gate"; grep -nE 'G-COST|cost gate|--cap ' "$ROOT/install.sh"; exit 1; }

# 2. the healthy path: exit 0, both executables and the gateway named
"$ROOT/install.sh" --doctor > "$T/ok.out" 2>&1
RC=$?
[[ "$RC" -eq 0 ]] || { echo "FAIL: doctor exited $RC on a healthy host"; cat "$T/ok.out"; exit 1; }
grep -q "executable present: bin/report.py" "$T/ok.out"
grep -q "executable present: bin/plan.py" "$T/ok.out"
grep -q "scenario-less requirement rejected" "$T/ok.out"
grep -q "gateway service: jiuwenswarm-gateway active" "$T/ok.out"
# and it never mentions a budget or cost check
if grep -qiE 'budget|cost' "$T/ok.out"; then
  echo "FAIL: doctor output mentions budget/cost:"; grep -niE 'budget|cost' "$T/ok.out"; exit 1
fi

# 3. (4.4) gateway unreachable -> fail, naming the missing setting.
#    systemctl is resolved through PATH, so a stub stands in for it.
mkdir -p "$T/bin"
cat > "$T/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
# unreachable-gateway double: the service exists but is not running
if [[ "$1" == "is-active" && "$2" == "jiuwenswarm-gateway" ]]; then
  echo "inactive"; exit 3
fi
exec /usr/bin/systemctl "$@"
EOF
chmod +x "$T/bin/systemctl"
set +e
PATH="$T/bin:$PATH" "$ROOT/install.sh" --doctor > "$T/gw.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: unreachable gateway exited $RC, want 1"; cat "$T/gw.out"; exit 1; }
grep -q "gateway service jiuwenswarm-gateway is inactive" "$T/gw.out"
grep -q "systemctl start jiuwenswarm-gateway" "$T/gw.out" \
  || { echo "FAIL: doctor did not name the missing reachability setting"; cat "$T/gw.out"; exit 1; }
# everything else still passes — the failure is the gateway, and only that
grep -q "executable present: bin/plan.py" "$T/gw.out"

# 4. planning client missing -> fail naming the client the dispatch invokes
set +e
AI_DLC_CLIENT="$T/nonexistent-client" "$ROOT/install.sh" --doctor > "$T/cl.out" 2>&1
RC=$?
set -e
[[ "$RC" -eq 1 ]] || { echo "FAIL: missing client exited $RC, want 1"; cat "$T/cl.out"; exit 1; }
grep -q "planning client missing: $T/nonexistent-client" "$T/cl.out" \
  || { echo "FAIL: doctor did not name the missing client"; cat "$T/cl.out"; exit 1; }

echo "L4 DOCTOR: pass (report.py + plan.py checked, discrimination smoke kept, gateway + client + config reachability verified; no budget/cost reference; unreachable gateway fails naming systemctl start jiuwenswarm-gateway; missing client fails naming itself)"
