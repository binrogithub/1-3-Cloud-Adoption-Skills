#!/usr/bin/env bash
# LLMWiki installer — checks prerequisites, writes llmwiki.toml, bootstraps runtime.
# Idempotent: safe to re-run. Never installs system packages silently.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

RUN_TESTS="${LLMWIKI_INSTALL_TESTS:-1}"
[ "${1:-}" = "--skip-tests" ] && RUN_TESTS=0

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[1;32mOK\033[0m %s\n' "$*"; }
warn() { printf '    \033[1;33mMISSING\033[0m %s\n' "$*"; }
fail() { printf '    \033[1;31mFAIL\033[0m %s\n' "$*"; MISSING_ANY=1; }

MISSING_ANY=0
PY="${LLMWIKI_PYTHON:-$(command -v python3.12 || command -v python3.11 || command -v python3)}"

say "LLMWiki installer"

# --- 1. Python >= 3.11 -------------------------------------------------------
if [ -n "$PY" ] && "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
  ok "Python $("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])') at $PY"
else
  fail "Python >= 3.11 not found (set LLMWIKI_PYTHON to an interpreter)"
fi

# --- 2. gbrain (L2 page store) ------------------------------------------------
GBRAIN_BIN="${LLMWIKI_GBRAIN_BIN:-$(command -v gbrain || echo /root/.bun/bin/gbrain)}"
if command -v "$GBRAIN_BIN" >/dev/null 2>&1; then
  ok "gbrain at $GBRAIN_BIN ($("$GBRAIN_BIN" --version 2>/dev/null | head -1 || echo unknown))"
else
  warn "gbrain not found — install with: bun install -g gbrain  (repo: garrytan/gbrain)"
  warn "  development fallback: set backend = \"files\" in llmwiki.toml (keyword-only retrieval)"
fi

# --- 3. Postgres + pgvector (gbrain engine) ------------------------------------
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q llmwiki_pg; then
  ok "llmwiki_pg container running"
else
  warn "llmwiki_pg (pgvector/pgvector:pg16) not running — retrieval needs it in production"
  warn "  docker run -d --name llmwiki_pg --network llmwiki_net -e POSTGRES_PASSWORD=… pgvector/pgvector:pg16"
fi

# --- 4. Embedding endpoint (optional, semantic retrieval) ----------------------
if curl -sf -o /dev/null --max-time 3 http://127.0.0.1:20081/health 2>/dev/null; then
  ok "embedding endpoint (TEI) at 127.0.0.1:20081"
else
  warn "embedding endpoint 127.0.0.1:20081 unreachable — retrieval degrades to keyword-only"
fi

# --- 5. JiuwenSwarm + model endpoint (the LLM) ---------------------------------
JIUWEN_BIN="${LLMWIKI_JIUWEN_BIN:-$(command -v jiuwenswarm || echo /root/.local/bin/jiuwenswarm)}"
if command -v "$JIUWEN_BIN" >/dev/null 2>&1; then
  ok "jiuwenswarm at $JIUWEN_BIN"
  warn "  dedicated instance: python3 deploy/install_instance.py --apply (systemd: llmwiki-jiuwen-*)"
else
  warn "jiuwenswarm not found — compile/ask need it (deploy/install_instance.py sets up the dedicated instance)"
fi
if [ -f runtime/jiuwen/config/.env ]; then
  ok "model credentials present (runtime/jiuwen/config/.env)"
else
  warn "runtime/jiuwen/config/.env missing — add the model API key there after deploy/install_instance.py"
fi

# --- 6. Config + runtime tree ---------------------------------------------------
say "configuration"
if [ ! -f llmwiki.toml ]; then
  cp llmwiki.toml.example llmwiki.toml
  ok "created llmwiki.toml from the example — edit [jiuwen]/[gbrain] paths for this host"
else
  ok "llmwiki.toml already exists (left untouched)"
fi
mkdir -p runtime/{sources,changesets,conversations,logs,auth,uploads,wiki,gbrain}
ok "runtime tree ready under runtime/"

# --- 7. Role + glossary ---------------------------------------------------------
[ -f role/llmwiki.md ]        && ok "llmwiki role present"       || fail "role/llmwiki.md missing"
[ -f wiki/glossary-terms.txt ] && ok "glossary present"          || warn "wiki/glossary-terms.txt missing (term grounding will be weaker)"

# --- 8. Smoke test ---------------------------------------------------------------
if [ "$RUN_TESTS" = "1" ] && [ -n "$PY" ]; then
  say "running the test suite (LLMWIKI_INSTALL_TESTS=0 or --skip-tests to skip)"
  if PYTHONPATH="$HERE" "$PY" -m pytest tests/ -q >/tmp/llmwiki-install-tests.log 2>&1; then
    ok "test suite green ($(grep -oE '[0-9]+ passed' /tmp/llmwiki-install-tests.log | tail -1))"
  else
    fail "test suite red — see /tmp/llmwiki-install-tests.log"
  fi
fi

say "summary"
if [ "$MISSING_ANY" = "1" ]; then
  printf 'Some prerequisites are missing (see above). The glue itself still runs;\nfix the flagged items for full functionality.\n'
else
  printf 'All checks passed. Next:\n  ./bin/llmwiki doctor\n  ./bin/llmwiki ingest seeds/obs-bootstrap.md\n  ./bin/llmwiki serve --host 127.0.0.1 --port 20080\n'
fi
