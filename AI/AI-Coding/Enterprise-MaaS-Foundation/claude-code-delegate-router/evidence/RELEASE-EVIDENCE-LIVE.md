# Release Evidence — Direct MaaS Delegate Router v1.0

> Immutable evidence record. Contains no credentials, no response bodies.
> Generated 2026-08-20T03:10:00Z (UTC).

## Release identity

| Field | Value |
| --- | --- |
| Git commit | `a5fbec4bffea5c448a017f055e7f7488968760cd` |
| Git tree | `71b0acda5c0f50ea2cf0c5c0389a17f0cb6a3c01` |
| Claude Code version | 2.1.235 |
| Endpoint host | `127.0.0.1:3000` |
| Endpoint path | `/anthropic` |
| Model | `glm-5.2` |
| Worktree | clean |

## Verification gates

| Gate | Status | Duration (ms) | Error summary |
| --- | --- | --- | --- |
| config-modes | PASS | 5 |  |
| direct-api | PASS | 3200 | text/stream/thinking/tool-auto/tool-forced PASS; image KNOWN_UNSUPPORTED |
| token-only-claude-cli | PASS | 1800 |  |
| tool-round-trip | PASS | 1800 |  |
| plain-claude-isolation | PASS | 50 | binary=/usr/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe version=2.1.235 |
| prohibited-dependency-scan | PASS | 10 |  |
| image | KNOWN_UNSUPPORTED (HTTP 400) | — |

## Helper SHA-256 digests

```
ca6f33043863099d1b51dcb306bf253de68a7ca9e4e47903b986c2c84914571c  tests/live_maas_probe.py
9d7c31bfc4390de47130179c2e198981f6dd50f7b32a73c3a52aef92f80e892d  tests/claude_e2e_probe.sh
25b4d1ed5a752357550488f51029d19d6815730a1afb0e02abe4f62d5717a6a5  scripts/check-prohibited-dependencies.py
```

## Claude Code binary

- digest: `bfcf0ae2dbf94b2b6a106074aabf3938b9a10889c3b678e4cb5a00c03274d5d5`

## Verdict: PASS
