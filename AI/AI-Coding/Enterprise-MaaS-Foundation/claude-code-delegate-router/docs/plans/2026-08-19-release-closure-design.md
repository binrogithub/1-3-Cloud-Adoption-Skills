# Direct MaaS Router v1 Release Closure — Approved Design

**Date:** 2026-08-19  
**Status:** Approved  
**Product contract:** `docs/PRD.md`  
**Closure contract:** `docs/PRD_RELEASE_CLOSURE_V1.md`

## Context

The feature branch has a broad implementation and 312 passing offline tests,
but it does not meet the original PRD's release definition. All live results
remain pending. More importantly, the real Claude E2E probe loses its response
because a heredoc replaces piped stdin, the plain-Claude isolation gate never
invokes plain Claude, and release helpers can be replaced by PATH stubs.

The selected approach is to preserve the approved product PRD and add a
separate release-closure PRD. This keeps stable product intent separate from a
bounded remediation project and prevents temporary implementation findings
from obscuring the architecture contract.

## Decision

Release closure is a trust-chain problem, not a routing redesign:

```text
verified Git source
  -> checkout-pinned probes
  -> offline + live execution
  -> structured, secret-free results
  -> evidence tied to commit/tree/digests
  -> release decision
```

Every gate must test the real behavior it names. Unit tests may use controlled
dependencies, but a stub result cannot be promoted into release evidence.

## Components

### Real E2E probe

The Claude response is persisted in the probe's protected temporary directory
and read by a Python validator from that file. The validator requires a
non-empty `modelUsage` whose extracted model set is exactly `glm-5.2`. It no
longer falls back to substring matching. The Bash marker remains the evidence
of a real tool round trip.

### Pinned verifier

`scripts/verify.sh` resolves all project helpers relative to its own checkout.
PATH lookup is not part of release execution. Tests invoke the real scripts
with fake external services at lower component boundaries, rather than
replacing the scripts under test.

### Plain-Claude isolation gate

The gate resolves both plain `claude` and the binary reached by
`claude-maas`, rejects wrapper recursion, clears MaaS variables, and invokes
the official binary with `--version`. This provides an observable,
network-free isolation check. Tests use a recording fake binary; release runs
use the installed official binary.

### Evidence writer

Machine-readable results are the source for the Markdown release record.
Evidence records commit/tree, tool versions, endpoint metadata, helper
digests, statuses, and durations. It records neither model response bodies nor
credentials. Pending, skipped, untrusted, dirty, or stale states fail closed.

## Error handling

Each failure has one stable code and one safe summary. Probe output and
temporary files are cleaned on every exit. Image HTTP 400 is the only accepted
non-PASS capability result and is represented as `KNOWN_UNSUPPORTED`, never as
a generic skip.

## Testing strategy

1. Reproduce the current E2E stdin failure with the real probe and a valid fake
   Claude response.
2. Fix the data channel, then exercise invalid JSON, missing/mixed modelUsage,
   missing marker, and non-zero CLI cases.
3. Place always-pass helper names at the front of PATH and prove they are not
   executed by release mode.
4. Record the plain-Claude subprocess argv/environment and prove it is invoked
   without MaaS state.
5. Run the full offline gate.
6. Rotate the exposed development key and run every live gate against the
   current checkout.
7. Generate and independently validate release evidence.

## Non-decisions

This closure does not add LiteLLM, CCR, Sidecars, fallback, performance tuning,
C256 testing, or a new routing policy. Any such change needs another approved
product PRD.

