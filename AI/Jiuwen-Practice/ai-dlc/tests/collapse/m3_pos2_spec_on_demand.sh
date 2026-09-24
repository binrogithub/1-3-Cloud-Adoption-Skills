#!/usr/bin/env bash
# M3 positive ② (collapse PRD §8): "写规格" — when the human DOES ask for a
# spec, the openspec CLI's own skill flow authors the change, and `openspec validate
# --strict` passes. The negative in the same script proves --strict
# discriminates (a requirement without a scenario is rejected).
set -euo pipefail
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
git -C "$T" init -q; git -C "$T" -c user.name=t -c user.email=t@t commit -q --allow-empty -m s
# 1. init (once) — --tools none: the repo owns its own skills
(cd "$T" && openspec init --tools none --language en) >/dev/null 2>&1
[[ -f "$T/openspec/config.yaml" ]] || { echo "FAIL: openspec init wrote nothing"; exit 1; }
# 2. author the change (the AI writes the markdown; the CLI validates)
C="$T/openspec/changes/add-nav-bar"
mkdir -p "$C/specs/website"
cat > "$C/proposal.md" <<'EOF'
## Why

The site has no navigation; visitors cannot move between pages.

## What Changes

- Add a shared navigation bar to every page.

## Non-goals

- No restructuring of page content.
EOF
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.

#### Scenario: Visitor opens any page

- **WHEN** a visitor opens any page
- **THEN** the navigation bar is visible with links to all top-level pages
EOF
# 3. G-SPEC: validate --strict passes
(cd "$T" && openspec validate add-nav-bar --strict) | grep -q "valid"
# 4. --strict discriminates: strip the scenario → rc 1
cat > "$C/specs/website/spec.md" <<'EOF'
## ADDED Requirements

### Requirement: Navigation bar

The site SHALL show a navigation bar on every page.
EOF
if (cd "$T" && openspec validate add-nav-bar --strict) >/dev/null 2>&1; then
  echo "FAIL: --strict accepted a requirement with no scenario"; exit 1; fi
# 5. GATE 1: nothing was implemented while proposing — no product files exist
[[ -z "$(git -C "$T" ls-files | grep -v '^\.ai-dlc' | grep -v openspec || true)" ]] \
  || { echo "FAIL: implementation started before the human accepted the spec"; exit 1; }
echo "M3 POS2: pass (写规格 → validate --strict green; scenario-less spec rejected; nothing implemented pre-acceptance)"
