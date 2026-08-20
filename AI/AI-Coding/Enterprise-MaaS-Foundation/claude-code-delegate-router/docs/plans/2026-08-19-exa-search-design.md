# Isolated Exa Search for claude-maas — Approved Design

**Date:** 2026-08-19  
**Status:** Approved  
**Product PRD:** `docs/PRD_EXA_SEARCH_V1.md`

## Context

The host currently has a working Exa integration only in plain Claude. It uses
the local `exa-mcp@0.0.7` stdio package, four legacy tool names, and a key copied
into plain-Claude JSON and backups. The isolated `claude-maas` profile has no
MCP servers.

Exa now recommends its hosted HTTP MCP. Claude Code supports dynamic
`headersHelper` commands, allowing the key to stay in a protected data file
instead of JSON. The approved scope is `claude-maas` only, with exactly
`web_search_exa` and `web_fetch_exa`.

## Decision

Use the official hosted endpoint:

```text
https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa
```

The isolated profile stores a key-free HTTP MCP definition. A repository-owned
helper validates the MCP server identity and reads
`~/.config/claude-maas/exa-api-key` as data to produce the `x-api-key` header.

Plain Claude is migrated away from Exa. Its unrelated MCP servers, settings,
permissions, OAuth state, and environment values remain unchanged.

## Components and data flow

```text
claude-maas (CLAUDE_CONFIG_DIR=~/.claude-maas)
  -> ~/.claude-maas/.claude.json
  -> remote HTTP MCP
  -> headersHelper
       -> validate server name + HTTPS host/path
       -> validate regular 0600 key file
       -> emit one JSON header object
  -> web_search_exa / web_fetch_exa
  -> untrusted result with source URLs
  -> glm-5.2 response
```

`configure-exa.sh` owns the isolated MCP entry and two exact permissions.
`migrate-exa.sh` removes the known plain-Claude legacy shape only after a
side-effect-free dry run. `uninstall-exa.sh` removes only owned isolated state;
the default retains the key.

## Security

The key never enters static configuration JSON, argv, environment, Git, logs,
evidence, query parameters, or user-visible output. Its only output path is the
helper's controlled JSON stdout consumed directly by Claude Code. The helper
rejects symlinks, wrong ownership, broad modes,
multiline values, unexpected server names, and non-Exa URLs. It performs no
network or file writes.

Existing plaintext copies are handled by rotating the old Exa key after
migration. Historical backups are not silently deleted; explicit purge is a
separate destructive operation.

Exa content is untrusted. Search answers preserve source URLs, and page content
cannot issue system instructions, request credentials, run commands, or write
persistent project memory.

## Failure behavior

Authentication failures fail closed without anonymous fallback. Rate limits,
timeouts, and disconnects fail the tool call while leaving the MaaS session
usable. No other provider is attempted. Tool-list drift blocks release.

## Testing

1. Test the header helper against file-type, ownership, mode, content, server,
   and URL counterexamples.
2. Test additive isolated-config installation and exact permissions.
3. Test migration with unrelated MCP/env/permission canaries and byte-identical
   dry-run snapshots.
4. Test idempotent install, rotation, uninstall, and purge.
5. Prove no runtime references to npm Exa packages or local listeners.
6. Run a live search and fetch canary through `claude-maas`.
7. Confirm plain Claude has no Exa and MaaS remains glm-5.2 with 1M context.

## Non-decisions

This design does not enable advanced search, Exa Agent, deprecated tools,
anonymous Exa, Tool Search beta, a local MCP server, or another search
provider. Each requires a new approved change.
