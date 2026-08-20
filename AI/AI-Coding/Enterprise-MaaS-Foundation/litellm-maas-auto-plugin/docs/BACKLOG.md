# Backlog

Items carried forward that do **not** block release. Per the anti-recursion
clause of `docs/PRD-closure-convergence.md` §5, any defect discovered after
adoption of that PRD is recorded here with a severity and date. It does not
change release status and does not extend the acceptance criteria.

## Client installer (Unit B)

| # | Item | Severity | Date | Disposition |
|---|---|---|---|---|
| B-2 | Mode-0644 manifest symlinked into place is accepted; uninstall proceeds | P0 (frozen) | 2026-08-12 | Implemented in `aaba7ac` (`validate_manifest_trust`); confirmed by `tests/test_manifest_trust.py::test_manifest_symlink_rejected` |
| B-6 | Deleting the manifest does not stop `claude-litellm` launching | accepted | 2026-08-12 | Accepted in R5 §2.2 — the manifest is an installer ownership record, not a runtime authorization token; the launcher never reads it |

## Gateway (Unit A) — carried from `PRD-final-delivery.md` §5

| # | Item | Impact | Severity | Date |
|---|---|---|---|---|
| H-2 | `_byte_estimate` runs `json.dumps` over the full message array per request | CPU on the event loop; material at ~1M context | P3 | 2026-08-08 |
| R-2 | The context guard is haiku-specific (`HAIKU_CONTEXT_LIMIT`), duplicating a number the registry already holds. Generalize to `profile["max_input_tokens"]` so every family inherits it. | Maintenance hazard; the guard itself is correct | P3 | 2026-08-09 |
| §7 | Length bands are global constants (200K advisory / 500K oversize). Sound for GLM at ~977K, but for haiku the advisory threshold *is* the ceiling. Derive from the profile. | Coarse-grained for non-GLM families | P3 | 2026-08-09 |

## Release mechanism (carried from R7 §6.3)

| # | Item | Impact | Severity | Date |
|---|---|---|---|---|
| F-5 | `Makefile` omits `Makefile` and `server/deploy-and-verify.sh` from `DIST_FILES`. An unpacked artifact cannot run `make verify` or the deploy path. | Artifact is not self-verifying | P3 | 2026-08-12 |
| T-1 | The provenance check in `tests/test_artifact_integrity.py:137-140` asserts on stdout strings (`"/tmp/" in out`, `"extraction" in out`) rather than on bytes. `artifact_hash`, computed at `:107`, is never used after the sanity assert at `:114`. It discriminates fixed from unfixed today only because the unfixed installer dies before printing a plan. A regression that extracts correctly but leaves one `*_FILE` bound to the working tree would still pass. Strengthen to: hash the file at the planned source path and assert equality with `artifact_hash`. | Provenance test could pass on a future regression | P2 | 2026-08-12 |
| T-2 | `--plugin-file` is now inert. It is parsed in the argument loop, then `bind_source_paths()` unconditionally overwrites `PLUGIN_FILE` in both branches. Under `--artifact` the override *should* be refused — accepting it would break provenance — but it should be refused loudly, not ignored. Without `--artifact` the documented flag silently does nothing. Either reject the combination or re-apply the override after binding. | Documented flag silently ignored; provenance could be bypassed if re-enabled carelessly | P2 | 2026-08-12 |
| T-3 | Criterion 9's hash comparison had no discriminating power in this release: the candidate and rollback artifacts have identical gateway bytes (both `775fc076…`), so the comparison passes regardless of whether rollback occurred. Rollback capability is actually established by criterion 4's provenance (verified structurally at `bind_source_paths`). **Trigger**: after the first release where gateway code actually changes, re-run the rollback verification with two artifacts whose gateway bytes genuinely differ — only then does this check discriminate for the first time. Same defect family as T-1 (a verification mechanism asserting on a non-discriminating quantity). | Rollback hash check cannot detect a failed rollback until gateway code changes | P2 | 2026-08-12 |
| T-4 | `r11-closeout.py:1381` computes `gate_13` as `all(v is True for v in gates.items())` — identical to `all_execution_steps_passed` at `:1389`. Gate 13 is a tautology: it passes iff all execution steps pass, without checking any of rev2 §11's seven evidence-consistency sub-checks. Not fixed in this release because `r11-closeout.py` is in `DIST_FILES` and modifying it would invalidate the candidate. Instead, an independent auditor (`scripts/r11-audit.py`, NOT in `DIST_FILES`) recomputes gate_13 from disk. The tautology is a frozen-version known issue; no future closeout run is expected. | Gate 13 self-assessment is not a real check | P2 | 2026-08-14 |

## How to add an item

Append a row with severity (P1–P3) and date. Do not promote a backlog item to a
release blocker unless it meets the single exception in §5.3 of the closure
PRD: reproducible against the deployed gateway and causing incorrect user
responses, credential disclosure, or data loss.
