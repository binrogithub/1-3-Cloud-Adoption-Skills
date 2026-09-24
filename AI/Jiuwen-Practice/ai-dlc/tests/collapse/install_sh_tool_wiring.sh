#!/usr/bin/env bash
# Reverse gate (PRD §05 / INV-41): every "host one-shot pin install" external
# tool must be wired into install.sh at four contact points. Parameterized over
# the four tool names with a single loop body (no copy-pasted assertion blocks
# per tool), so a newly added tool can never again go uncovered the way
# browser-verify / agent-bench did before this change.
#
# Per tool, asserts install.sh source contains:
#   1. a usage-comment line  — `#   ./install.sh --<name>`
#   2. a doctor warn line    — `warn "...Run: ./install.sh --<name>"`
#   3. a --help entry        — `  --<name>   <description>`
#   4. a mode-dispatch exec  — `exec ".../scripts/install-<name>.sh" "$@"`
# A missing item fails naming the specific tool AND the specific item (never a
# generic "FAIL"). Bidirectional: passes on fully-wired code; remove any one
# contact point and it reports exactly which tool + which item went missing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_SH="${SCRIPT_DIR}/../../install.sh"

if [[ ! -f "${INSTALL_SH}" ]]; then
  echo "FAIL: install.sh not found at ${INSTALL_SH}" >&2
  exit 1
fi

tools=(opendesign understand-anything browser-verify agent-bench)
fail=0

for name in "${tools[@]}"; do
  # 1. usage-comment flag — a comment line naming ./install.sh --<name>
  if ! grep -nE "^#" "${INSTALL_SH}" | grep -qF "./install.sh --${name}"; then
    echo "FAIL [${name}]: usage-comment flag './install.sh --${name}' missing from install.sh" >&2
    fail=1
  fi

  # 2. doctor warn line — a warn(...) call whose remedy mentions --<name>
  if ! grep -n "warn " "${INSTALL_SH}" | grep -qF -- "--${name}"; then
    echo "FAIL [${name}]: doctor warn line mentioning '--${name}' missing from install.sh" >&2
    fail=1
  fi

  # 3. --help entry — a line beginning with whitespace, then --<name>, then whitespace
  if ! grep -qE "^[[:space:]]*--${name}[[:space:]]" "${INSTALL_SH}"; then
    echo "FAIL [${name}]: --help entry '--${name}' missing from install.sh" >&2
    fail=1
  fi

  # 4. mode-dispatch exec — exec .../scripts/install-<name>.sh
  if ! grep -qE "exec .*scripts/install-${name}\.sh" "${INSTALL_SH}"; then
    echo "FAIL [${name}]: mode-dispatch exec line for 'scripts/install-${name}.sh' missing from install.sh" >&2
    fail=1
  fi
done

if [[ "${fail}" == "0" ]]; then
  echo "OK: all four tools (opendesign, understand-anything, browser-verify, agent-bench) wired into install.sh"
  exit 0
else
  exit 1
fi
