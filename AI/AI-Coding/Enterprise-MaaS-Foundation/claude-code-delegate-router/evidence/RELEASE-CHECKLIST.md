# Release Evidence — Direct MaaS Delegate Router v1.0

> Immutable evidence record. Contains no credentials, no response bodies.
> Generated 2026-08-20T00:00:00Z (UTC). Updated after P0 release-closure fixes.

## Release identity

| Field | Value |
| --- | --- |
| Git commit | `a5fbec4bffea5c448a017f055e7f7488968760cd` |
| Git tree | `71b0acda5c0f50ea2cf0c5c0389a17f0cb6a3c01` |
| Branch | `feat/direct-maas-router` |
| Claude Code version | 2.1.235 |
| Endpoint host | `api-ap-southeast-1.modelarts-maas.com` |
| Endpoint path | `/anthropic` (native Anthropic Messages API) |
| Model | `glm-5.2` |
| PRD | `docs/PRD.md` (v1.0, approved 2026-08-19) |
| Closure PRD | `docs/PRD_RELEASE_CLOSURE_V1.md` (v1.0, approved 2026-08-19) |

## Offline verification gate

| Gate | Result |
| --- | --- |
| Prohibited-dependency scan | PASS (0 offenders) |
| Architecture contract test | PASS |
| Full test suite | PASS — 354 tests (baseline 312 + 42 regression) |
| `make verify-offline` exit code | 0 |

## P0 release-closure fixes (offline-verified)

| P0 | Fix | Regression test | Status |
| --- | --- | --- | --- |
| P0-1: E2E probe stdin defect | Response routed through protected 0600 file; strict modelUsage set check; stable error codes | `tests/test_claude_e2e_probe.py` (11 cases) | PASS |
| P0-3: PATH stub replaceable | `resolve_helper` pins to PROJECT_ROOT, Git-tracked, SHA-256 logged; test override marked UNTRUSTED | `tests/test_verify_contract.py::test_path_stub_*` | PASS |
| P0-2: isolation gate never invoked claude | `resolve-binary` diagnostic; gate invokes `claude --version` with MaaS env cleared; rejects wrapper/mismatch | `tests/test_verify_contract.py::test_plain_claude_*` | PASS |
| P0-4: evidence not closed | `scripts/write-release-evidence.py` fail-closed writer; rejects pending/skipped/untrusted/dirty/stale/digest-mismatch | `tests/test_release_evidence.py` (19 cases) | PASS |

## Live verification gates (run against configured MaaS endpoint)

| Gate | Status |
| --- | --- |
| `text` — non-streaming Anthropic message | PASS (HTTP 200) |
| `stream` — Anthropic SSE framing | PASS (HTTP 200, message_stop) |
| `thinking` — adaptive thinking block/delta pairing | PASS (HTTP 200) |
| `tool-auto` — automatic structured tool_use | PASS (HTTP 200) |
| `tool-forced` — forced tool choice | PASS (HTTP 200) |
| `image` — documented unsupported (HTTP 400) | KNOWN_UNSUPPORTED (no fallback) |
| Claude Code E2E — token-only, no OAuth | PASS (modelUsage={glm-5.2}) |
| Claude Code tool round trip | PASS (marker created by Bash tool) |
| Plain Claude isolation | PASS (claude --version=2.1.235, MaaS env cleared) |

Live gates run via `printf '%s\n' "$KEY" | make verify-live`. All gates PASS
against the configured endpoint. See `evidence/RELEASE-EVIDENCE-LIVE.md` for
the machine-readable evidence record bound to the verified commit/tree.

## Release helper SHA-256 digests (verified checkout)

```
ca6f33043863099d1b51dcb306bf253de68a7ca9e4e47903b986c2c84914571c  tests/live_maas_probe.py
9d7c31bfc4390de47130179c2e198981f6dd50f7b32a73c3a52aef92f80e892d  tests/claude_e2e_probe.sh
25b4d1ed5a752357550488f51029d19d6815730a1afb0e02abe4f62d5717a6a5  scripts/check-prohibited-dependencies.py
c4a62428ad1bec2aa74ae16e40ffc92efeac5147dce5ac9af30cd74e31efeaa3  scripts/verify.sh
901ecc2f4ba53fcc0506559ed60b69124032ed89a9a9bffaecb9a631d93a3557  client/claude-maas
1f1e0c2fd7587072696e816dd0c7932198c917370d429722e6b285f1184dacf7  scripts/write-release-evidence.py
```

## Release script SHA-256 checksums

```
901ecc2f4ba53fcc0506559ed60b69124032ed89a9a9bffaecb9a631d93a3557  client/claude-maas
6761cfc86228c631bc7c14f68de1a1f195f463d6d7f6552e63ba3d73e66f75a3  client/claude-maas-setup.sh
279e7c35663fb5afa57813f4bc659ba6dae11c92ed1f1789038d1ad04ded6082  client/claude-select
25b4d1ed5a752357550488f51029d19d6815730a1afb0e02abe4f62d5717a6a5  scripts/check-prohibited-dependencies.py
67c88373a54215a1d0f005a6fa83047e9b443218fc907782e0c77bf591a78fd4  scripts/configure-policy.sh
71d4b8b907f1097e21ad38f650438e132308c1a798d3672a35049e8a6bdc2280  scripts/delegate
d034ae8a2f9a42c53c92e3dd2153577317826ffdaee9f38526365b713a0a3ef1  scripts/install.sh
657a8d477c77573952943d7f784cab072fe803428a024b2f964ad795fcd39a5a  scripts/migrate.sh
9bf233c5445a4e372156e4a8e7dc7cd5b7ebc4ec36bc387cba867a48f7ae86a1  scripts/route-hint.sh
eb09bea9506b364fad161097c5a7fc7201510db2159c68234f05a86e404fb5fb  scripts/uninstall.sh
c4a62428ad1bec2aa74ae16e40ffc92efeac5147dce5ac9af30cd74e31efeaa3  scripts/verify.sh
c14b04ee4b03b4c8b280b7a98d19433f4e0eb0bc1e2edea98e6dc0819c561963  scripts/workflow
1f1e0c2fd7587072696e816dd0c7932198c917370d429722e6b285f1184dacf7  scripts/write-release-evidence.py
```

## Product invariants verified

- [x] No LiteLLM, CCR, OpenRouter, or Sidecar in runtime files
- [x] No HTTP listener / protocol converter / local port
- [x] No model fallback chain (`fallback` always `false` in audit)
- [x] Credentials 0600, read as data, never in argv/logs/audit
- [x] `claude-maas` child isolates `CLAUDE_CONFIG_DIR` and unsets `ANTHROPIC_API_KEY`
- [x] Image input returns explicit `unsupported_capability`, no silent reroute
- [x] Delegate: 2-attempt cap, bounded retry, acceptance verification
- [x] Delegate: real client extracts HTTP status from stderr for retry logic
- [x] Workflow: disjoint-scope enforcement, 30% failure abort
- [x] Workflow: strips item_id before delegate; validates numeric fields
- [x] Workflow: verification_timeout enforced as wall-clock cap
- [x] configure-policy: preserves user ANTHROPIC_API_KEY (no destructive env strip)
- [x] Migration: `--dry-run`/`--apply` explicit, ownership-proven removal
- [x] Migration: setup writes manifest ownership fields migrate consumes
- [x] Uninstall: default retains key/audit, `--purge` explicit-only
- [x] verify.sh: stat-failure reported as FAIL, not false-passed
- [x] E2E probe: response via protected file, strict modelUsage, stable error codes
- [x] verify.sh: helpers pinned to checkout, SHA-256 provenance, PATH stubs bypassed
- [x] verify.sh: plain-claude-isolation invokes real `claude --version`, clears MaaS env
- [x] Evidence writer: fail-closed, rejects pending/untrusted/dirty/stale/digest-mismatch

## Post-release action

- [x] Run `printf '%s\n' "$KEY" | make verify-live` — all gates PASS
- [x] Generate final evidence via the evidence writer — `evidence/RELEASE-EVIDENCE-LIVE.md`
- [x] Change `Decision: HOLD` to `Decision: RELEASE` — see `docs/PRD_RELEASE_CLOSURE_V1.md` §9
- [ ] Rotate the MaaS key before production deployment (PRD §FR-7.5, deferred)