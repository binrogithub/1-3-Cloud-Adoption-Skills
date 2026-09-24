#!/usr/bin/env bash
# E8-S2 / GL-L1: nightly lint + _meta/lint-report-<date> page + re-verification of
# crawlable stale sources (GL-L3). Runs via llmwiki-lint.timer.
set -euo pipefail
PROJECT="/root/HuaweiCloudLatam_LLMWiki"
cd "$PROJECT"
./bin/llmwiki lint --write-page >> runtime/logs/lint-nightly.log 2>&1
./bin/llmwiki reverify --limit 20 >> runtime/logs/lint-nightly.log 2>&1 || true
