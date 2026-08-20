# Makefile for litellm-auto-plugin — test and static checks.
#
# Targets:
#   make            — run tests + static checks (default)
#   make test       — run the full test suite
#   make check      — static checks (bash syntax, python parse, whitespace)
#   make clean      — remove build artifacts

.PHONY: test check clean all
.DEFAULT_GOAL := all

all: test check

# ── test ──────────────────────────────────────────────────────────────────────
test:
	python3 -m pytest tests/ -q

# ── static checks ─────────────────────────────────────────────────────────────
check:
	@for f in client/claude-litellm-setup.sh client/claude-litellm-migrate.sh \
	         client/claude-litellm client/claude-select \
	         client/configure-claude-code.sh \
	         server/install-litellm-plugin.sh server/deploy-and-verify.sh; do \
		bash -n $$f || { echo "SYNTAX FAIL: $$f"; exit 1; }; \
	done
	@for f in $$(find litellm_plugins -name 'callback.py') \
	         _litellm_adapter.py _request_context.py; do \
		python3 -c "import ast, sys; ast.parse(open('$$f').read())" \
		  || { echo "PY SYNTAX FAIL: $$f"; exit 1; }; \
	done
	@if git rev-parse --git-dir >/dev/null 2>&1; then \
		git diff --check || { echo "WHITESPACE FAIL"; exit 1; }; \
	else \
		echo "(not a git checkout — skipping git diff --check)"; \
	fi
	@echo "Static checks passed."

# ── clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf dist
