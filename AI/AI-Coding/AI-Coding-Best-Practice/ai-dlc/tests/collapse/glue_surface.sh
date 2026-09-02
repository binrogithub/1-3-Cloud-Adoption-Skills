#!/usr/bin/env bash
# G1 (glue-only architecture PRD, updated by devteam D1 and the
# containment PRD): the pruned
# surface. The gateway is gone, the hand-written ai-dlc-spec skill is gone
# from every tree, the doctor checks only the executables we still own,
# .claude/ carries NO openspec surface (containment D6/D7), no
# dead-wiring instruction survives — and since D1 the oracle plane is
# gone entirely: no executable, no probes, no checker registry, and the
# gate ids our code names are exactly the four that stay.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)   # audit the checkout this
                                             # script belongs to — a hardcoded
                                             # master path once let a worktree
                                             # run audit the wrong tree and
                                             # pass (the dt1_gates lesson)
cd "$REPO"

# 1. dead/duplicated modules absent (tracked AND on disk)
[[ -z "$(git ls-files executor)" ]] || { echo "FAIL: executor/ still tracked"; exit 1; }
[[ ! -e executor ]] || { echo "FAIL: executor/ still on disk"; exit 1; }
[[ ! -e supervisor/skills/ai-dlc-spec ]] || { echo "FAIL: supervisor/skills/ai-dlc-spec present"; exit 1; }
[[ ! -e .claude/skills/ai-dlc-spec ]] || { echo "FAIL: .claude/skills/ai-dlc-spec present"; exit 1; }

# 2. doctor reduced to the executables we still own
L=$(wc -l < supervisor/skills/claude/ai-dlc-doctor/SKILL.md)
[[ "$L" -le 15 ]] || { echo "FAIL: doctor SKILL.md is ${L} lines (want <= 15)"; exit 1; }

# 3. .claude/ carries NO openspec surface (containment D6/D7): the six
#    openspec-* skills and the six opsx commands are deleted — the
#    caller reads signed records, it never runs the CLI
N=$(find .claude/skills -maxdepth 1 -type d -name 'openspec-*' 2>/dev/null | wc -l)
[[ "$N" -eq 0 ]] || { echo "FAIL: ${N} openspec skills survive under .claude/ (containment D6)"; exit 1; }
[[ ! -e .claude/commands/opsx ]] || { echo "FAIL: opsx commands survive under .claude/ (containment D7)"; exit 1; }

# 4. the 1.7 audit: the three dead-wiring names survive only as prose that
#    does not instruct execution (the README's never-modify-upstream
#    constraint line is the one allowed mention). This audit script is
#    excluded from its own grep — its pattern text names the tokens without
#    instructing anything, exactly like the allowed prose.
#    plan.py invokes the shipped openjiuwen client per the devteam pipeline spec — glue, not a hand-built client.
#    docs/plane-runtime.md (devteam D4) records that shipped plane's measured
#    runtime authorisation — configuration paths and restore steps, no
#    execution instruction, the same legitimate-mention class as plan.py.
#    install.sh --doctor (landing L4) verifies the planning dispatch can
#    reach that plane: the client path (same AI_DLC_CLIENT resolution
#    plan.py uses), the service unit name, the config the service reads.
#    Naming them IS the check — the same legitimate-mention class. The
#    l4_doctor test stubs systemctl and asserts those names.
#    The ai-dlc skill (landing L7, both the tracked source and its
#    .claude mirror) names the forbidden dependencies in
#    the admission rule it teaches — naming what must never be modified
#    IS the rule; no execution is instructed.
#    open_plane.sh (open-plane O5) drives install.sh --provision-plane
#    on fixtures: it names the service unit to stub reachability and
#    carries unit-fixture ReadWritePaths lines — the same
#    legitimate-mention class as l4_doctor.sh.
#    docs/team-mode-record.md (review-synthesis S4) cites the upstream
#    source read-only to settle what was measured about team mode —
#    module paths, config paths, the backup's name. Naming them IS the
#    record a future proposal is refused by; no execution is
#    instructed, the plane-runtime.md class exactly.
#    docs/prd-openspec-containment.md names openjiuwen as the sole
#    trust root and records its risk — naming the trust root IS the
#    containment contract; no execution is instructed.
#    docs/prd-gateway-open-sandbox.md (2026-09-01) records the
#    operator's decision to open that unit's sandbox, with the unit's
#    target state and its restore step as HOST steps a person applies —
#    the containment-PRD class exactly: naming the unit IS the decision
#    record; no execution is instructed by the runtime.
#    docs/prd-uidesigner-opendesign.md records another effort's
#    read-only constraints on the same plane's config paths — the
#    plane-runtime.md class (paths and restore steps, no execution
#    instruction).
#    scripts/install-opendesign.sh (uidesigner-opendesign N6) is a
#    HOST step a person runs to deploy the pinned design reference
#    tree: it names the gateway's config path and the workspace skill
#    dir to add exactly one entry in each — the install.sh class
#    exactly (naming the paths IS the deploy record; the runtime
#    never executes this script).
#    scripts/setup-maas-key.sh (install-onboarding PRD) is a HOST step
#    a person runs to write the gateway's own credential file: it names
#    the gateway's .env path and its systemd unit to restart after
#    writing — the install.sh class exactly (naming the paths IS the
#    credential-entry record; the runtime never executes this script).
#    tests/collapse/doctor_opendesign_check.sh (install-onboarding PRD)
#    is a doctor-check test that builds a fake gateway .env under a
#    fixture $HOME to assert the OpenDesign-tree warn behaviour — the
#    l4_doctor.sh class exactly (naming the fixture path IS the test,
#    no execution against the real gateway).
#    README.md's "MaaS gateway key is shared, not per-agent" section
#    (shared-maas-key PRD) documents ensure_maas_key()'s real behaviour
#    for the reader who just asked "why wasn't I prompted for a key" —
#    naming the real .env path and explaining the shared-gateway
#    architecture IS the documentation; no execution is instructed.
#    tests/collapse/maas_key_shared.sh (shared-maas-key PRD) is a
#    doctor-class test that builds a fake gateway .env under a fixture
#    $HOME to assert ensure_maas_key()'s present/missing behaviour —
#    the doctor_opendesign_check.sh class exactly (naming the fixture
#    path IS the test, no execution against the real gateway).
BAD=$(grep -rn "openspec_gateway\|runtime_bridge\|jiuwenswarm" \
      --include="*.py" --include="*.md" --include="*.sh" --include="*.yaml" \
      --exclude="glue_surface.sh" --exclude="plan.py" \
      --exclude="plane-runtime.md" --exclude="install.sh" \
      --exclude="l4_doctor.sh" --exclude="open_plane.sh" --exclude="SKILL.md" \
      --exclude="team-mode-record.md" \
      --exclude="prd-openspec-containment.md" \
      --exclude="prd-gateway-open-sandbox.md" \
      --exclude="prd-uidesigner-opendesign.md" \
      --exclude="install-opendesign.sh" \
      --exclude="configure-gateway-model.sh" \
      --exclude="prd-design-required.md" \
      --exclude="prd-design-autodispatch.md" \
      --exclude="prd-install-targets.md" \
      --exclude="prd-deliver-measures-work.md" \
      --exclude="prd-uidesigner-reliable-fast.md" \
      --exclude="prd-devteam-workflow-hardening.md" \
      --exclude="setup-maas-key.sh" \
      --exclude="doctor_opendesign_check.sh" \
      --exclude="README.md" \
      --exclude="maas_key_shared.sh" . 2>/dev/null \
      | grep -vE '^(\./)?(evidence/|CHANGELOG\.md:|openspec/changes/|openspec/specs/|\.ai-dlc/)' \
      | grep -v 'jiuwenswarm source' || true)
[[ -z "$BAD" ]] || { echo "FAIL: dead-wiring references survive the 1.7 audit:"; echo "$BAD"; exit 1; }

# 5. the oracle plane is absent (devteam D1): executable, probes, registry
[[ ! -e bin/oracle.py ]] || { echo "FAIL: bin/oracle.py still on disk"; exit 1; }
[[ ! -e probes ]] || { echo "FAIL: probes/ still on disk"; exit 1; }
if grep -rq "CHECKER_SETS\|run_property" bin/ 2>/dev/null; then
  echo "FAIL: checker-registry code survives in bin/"; exit 1
fi

# 6. the gate ids our executable names are exactly the two that stay
#    (landing L1): delivery, merge. No oracle gate, no spec gate beyond
#    strict validation inside G-DELIVER-1, no worker gate, no cost gate.
GOT=$(grep -hoE 'G-[A-Z0-9]+(-[A-Z0-9]+)*|MERGE_GATE|WORKER_FAILURE' \
      bin/report.py | sort -u)
WANT=$(printf 'G-DELIVER-1\nMERGE_GATE\n' | sort -u)
[[ "$GOT" == "$WANT" ]] \
  || { echo "FAIL: gate ids in bin/report.py are [$(echo "$GOT" | tr '\n' ' ')], want [$(echo "$WANT" | tr '\n' ' ')]"; exit 1; }
if grep -rq "G-ORACLE-1\|G-SPEC\b\|WORKER_FAILURE" bin/ 2>/dev/null; then
  echo "FAIL: a retired gate id survives in bin/"; exit 1
fi

echo "GLUE SURFACE: pass (gateway+ai-dlc-spec gone, doctor 1-executable, .claude carries no openspec surface, 1.7 grep clean, oracle plane absent, gates = 2)"
