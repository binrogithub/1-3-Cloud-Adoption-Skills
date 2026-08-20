#!/usr/bin/env bash
# route-hint.sh — advisory task classification hook.
#
# Reads a task description from stdin and/or command-line args, classifies it
# using the approved PRD taxonomy, and outputs ONE concise advisory line:
#
#   route-hint: oauth (reason: image input)
#   route-hint: maas (reason: unit test generation)
#
# Invariants:
#   * Always exits 0 (advisory only, never blocks).
#   * Outputs exactly one line on stdout.
#   * Never invokes MaaS / claude-maas.
#   * Never reads credentials or the api-key file.
#   * Never creates, modifies, or deletes any file.
#   * Uses only bash builtins and grep (no subprocesses to MaaS).
#
# Premium signals win ties: if a task matches both a MaaS signal and an OAuth
# signal, it classifies as OAuth.
set -euo pipefail

# ---------------------------------------------------------------------------
# Collect the task description from args and/or stdin.
# ---------------------------------------------------------------------------

task_text=""

# Command-line args are joined with spaces.
if [[ $# -gt 0 ]]; then
    task_text="$*"
fi

# If stdin has data (pipe or redirect), append it.
if [[ ! -t 0 ]]; then
    stdin_data=""
    stdin_data=$(cat 2>/dev/null || true)
    if [[ -n "${stdin_data}" ]]; then
        if [[ -n "${task_text}" ]]; then
            task_text="${task_text} ${stdin_data}"
        else
            task_text="${stdin_data}"
        fi
    fi
fi

# Normalize to lowercase for keyword matching.
# Using bash parameter expansion instead of tr to avoid subprocess.
lower_text="${task_text,,}"

# ---------------------------------------------------------------------------
# Classify: OAuth (premium / high-judgment) signals.
# ---------------------------------------------------------------------------
# Order matters: we check OAuth signals first so premium wins ties.

oauth_reason=""

# Images / screenshots / vision.
if [[ "${lower_text}" == *"image"* ]] || \
   [[ "${lower_text}" == *"screenshot"* ]] || \
   [[ "${lower_text}" == *"vision"* ]] || \
   [[ "${lower_text}" == *"photo"* ]] || \
   [[ "${lower_text}" == *"picture"* ]]; then
    oauth_reason="image or vision input"
fi

# Security / auth / payment / PCI / incident.
if [[ -z "${oauth_reason}" ]]; then
    if [[ "${lower_text}" == *"security"* ]] || \
       [[ "${lower_text}" == *"auth"* ]] || \
       [[ "${lower_text}" == *"authentication"* ]] || \
       [[ "${lower_text}" == *"encrypt"* ]] || \
       [[ "${lower_text}" == *"crypto"* ]] || \
       [[ "${lower_text}" == *"payment"* ]] || \
       [[ "${lower_text}" == *"pci"* ]] || \
       [[ "${lower_text}" == *"incident"* ]]; then
        oauth_reason="security or high-risk domain"
    fi
fi

# Architecture / cross-service design.
if [[ -z "${oauth_reason}" ]]; then
    if [[ "${lower_text}" == *"architecture"* ]] || \
       [[ "${lower_text}" == *"cross-service"* ]] || \
       [[ "${lower_text}" == *"cross service"* ]] || \
       [[ "${lower_text}" == *"system design"* ]]; then
        oauth_reason="architecture or cross-service design"
    fi
fi

# Complex debugging / multi-failure root cause.
if [[ -z "${oauth_reason}" ]]; then
    if [[ "${lower_text}" == *"root cause"* ]] || \
       [[ "${lower_text}" == *"complex debug"* ]] || \
       [[ "${lower_text}" == *"multi-failure"* ]] || \
       [[ "${lower_text}" == *"multi failure"* ]] || \
       [[ "${lower_text}" == *"race condition"* ]] || \
       [[ "${lower_text}" == *"cascading"* ]] || \
       [[ "${lower_text}" == *"multiple subsystem"* ]]; then
        oauth_reason="complex debugging or root cause analysis"
    fi
fi

# High-risk PR review / infrastructure / DB migration decisions.
if [[ -z "${oauth_reason}" ]]; then
    if [[ "${lower_text}" == *"high-risk"* ]] || \
       [[ "${lower_text}" == *"high risk"* ]] || \
       [[ "${lower_text}" == *"infrastructure"* ]] || \
       [[ "${lower_text}" == *"database migration"* ]] || \
       [[ "${lower_text}" == *"db migration"* ]] || \
       [[ "${lower_text}" == *"sharding"* ]]; then
        oauth_reason="high-risk review or infrastructure decision"
    fi
fi

# Escalation after two failures.
if [[ -z "${oauth_reason}" ]]; then
    if [[ "${lower_text}" == *"escalat"* ]] || \
       [[ "${lower_text}" == *"needs_escalation"* ]]; then
        oauth_reason="escalation from failed delegation"
    fi
fi

# If we matched an OAuth signal, output and exit.
if [[ -n "${oauth_reason}" ]]; then
    printf 'route-hint: oauth (reason: %s)\n' "${oauth_reason}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Classify: MaaS (delegate) signals.
# ---------------------------------------------------------------------------

maas_reason=""

# Unit tests / docs / repo summary.
if [[ -z "${maas_reason}" ]]; then
    if [[ "${lower_text}" == *"unit test"* ]] || \
       [[ "${lower_text}" == *"test"* ]] || \
       [[ "${lower_text}" == *"doc"* ]] || \
       [[ "${lower_text}" == *"summary"* ]]; then
        maas_reason="test or documentation generation"
    fi
fi

# Code generation / single-module modification.
if [[ -z "${maas_reason}" ]]; then
    if [[ "${lower_text}" == *"code gen"* ]] || \
       [[ "${lower_text}" == *"code-gen"* ]] || \
       [[ "${lower_text}" == *"generate"* ]] || \
       [[ "${lower_text}" == *"implement"* ]] || \
       [[ "${lower_text}" == *"crud"* ]]; then
        maas_reason="code generation"
    fi
fi

# CI fix / mechanical refactor / format migration.
if [[ -z "${maas_reason}" ]]; then
    if [[ "${lower_text}" == *"ci"* ]] || \
       [[ "${lower_text}" == *"refactor"* ]] || \
       [[ "${lower_text}" == *"format"* ]] || \
       [[ "${lower_text}" == *"lint"* ]]; then
        maas_reason="CI fix or mechanical refactor"
    fi
fi

# Low/medium-risk review.
if [[ -z "${maas_reason}" ]]; then
    if [[ "${lower_text}" == *"low-risk"* ]] || \
       [[ "${lower_text}" == *"low risk"* ]] || \
       [[ "${lower_text}" == *"medium-risk"* ]] || \
       [[ "${lower_text}" == *"medium risk"* ]] || \
       [[ "${lower_text}" == *"review"* ]]; then
        maas_reason="low or medium risk review"
    fi
fi

# Batch / loop / cron / fan-out.
if [[ -z "${maas_reason}" ]]; then
    if [[ "${lower_text}" == *"batch"* ]] || \
       [[ "${lower_text}" == *"loop"* ]] || \
       [[ "${lower_text}" == *"cron"* ]] || \
       [[ "${lower_text}" == *"fan-out"* ]] || \
       [[ "${lower_text}" == *"fan out"* ]] || \
       [[ "${lower_text}" == *"parallel"* ]]; then
        maas_reason="batch or fan-out workflow"
    fi
fi

# If we matched a MaaS signal, output and exit.
if [[ -n "${maas_reason}" ]]; then
    printf 'route-hint: maas (reason: %s)\n' "${maas_reason}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Default: no signal matched. Lean toward MaaS for ordinary tasks.
# ---------------------------------------------------------------------------

if [[ -n "${task_text}" ]]; then
    printf 'route-hint: maas (reason: no premium signal detected)\n'
else
    printf 'route-hint: maas (reason: empty input)\n'
fi

exit 0
