# Sourced by tests that dispatch. Expects T (the test's temp dir), PY
# and PLAN set by the sourcing test. Provides the N6 plane-tree
# fixture: a test-local specs home (AI_DLC_SPECS) and the one-time
# migrate of the repo's openspec tree into it — the same shape the
# live plane holds at /var/lib/aidlc/specs/<repo-id>.
#
#   . "$ROOT/tests/collapse/lib_plane.sh"
#   plane_migrate "$REPO"     → sets PLANE_ROOT and PLANE_TREE
#
# The repo-id here mirrors report.repo_id: the absolute path stripped
# of its leading slash with every separator doubled (root--x--repo).
plane_migrate() {
    local repo="$1"
    export AI_DLC_SPECS="${AI_DLC_SPECS:-$T/specs}"
    "$PY" "$PLAN" migrate --repo "$repo" > /dev/null
    PLANE_ROOT="$AI_DLC_SPECS/$(printf '%s' "${repo#/}" | sed 's,/,--,g')"
    PLANE_TREE="$PLANE_ROOT/openspec"
    [ -d "$PLANE_TREE" ]
}

# plane_of <repo> — the repo's plane root, without migrating
plane_of() {
    printf '%s' "$AI_DLC_SPECS/$(printf '%s' "${1#/}" | sed 's,/,--,g')"
}

# plane_git <plane_root> <git-args...> — like `git -C <plane_root> ...`
# but scopes a safe.directory override to exactly that path. Mirrors
# bin/plan.py's git_run(): plane_migrate's real `plan.py migrate` chowns
# the plane root to swarm:swarm, so any fixture that seeds content there
# directly (bypassing plan.py) hits the same dubious-ownership refusal
# plan.py's own code must handle — this is that same fix, applied to the
# test fixtures that recreate the ownership mismatch on purpose.
plane_git() {
    local root="$1"; shift
    git -c "safe.directory=$root" -C "$root" "$@"
}
