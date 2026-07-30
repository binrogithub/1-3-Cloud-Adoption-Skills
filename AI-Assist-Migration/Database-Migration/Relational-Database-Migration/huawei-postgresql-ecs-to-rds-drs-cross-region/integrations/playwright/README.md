# Playwright Integration

## Overview

Playwright MCP is used by huaweicloud-drs for DRS console automation via browser.

## Package

@playwright/mcp@0.0.78

## Consumer MCPs

- huaweicloud-drs (required for console automation)

## Consumer Skills

- huawei-cce-cross-region-velero-migration (optional)
- huawei-snowflake-to-dataarts-migration (optional)

## Risks

- Fragile selectors (console UI changes break automation)
- Requires Chromium installation
- Session cookies expire
- May expose sensitive data in page snapshots

## Status

PINNED — @playwright/mcp@0.0.78 (validated 2026-07-27)
