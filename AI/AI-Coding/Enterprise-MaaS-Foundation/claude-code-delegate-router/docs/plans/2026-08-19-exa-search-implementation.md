# Isolated Exa Search for claude-maas Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give only `claude-maas` secure Exa web search and page fetch through the official remote MCP while removing the legacy plain-Claude Exa integration.

**Architecture:** Store the Exa key in a separate 0600 data file, use a fail-closed `headersHelper` for the official HTTP MCP, and add only two tools to the isolated Claude profile. Migrate the known plain-Claude legacy shape transactionally and preserve all unrelated state.

**Tech Stack:** Bash 4+, Python 3 standard library, pytest, Claude Code 2.1.235+, HTTP MCP, Exa hosted MCP, Git, SHA-256.

---

Execute from a dedicated worktree. Use `@test-driven-development` for every
code task and `@verification-before-completion` before any completion claim.

### Task 1: Establish the Exa architecture contract

**Files:**
- Create: `tests/test_exa_architecture.py`
- Modify: `scripts/check-prohibited-dependencies.py`
- Modify: `README.md`

**Step 1: Write the failing architecture tests**

```python
EXA_URL = "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
ALLOWED = {"web_search_exa", "web_fetch_exa"}


def test_exa_runtime_has_no_local_package_or_process_dependency(runtime_text):
    assert "exa-mcp-server" not in runtime_text
    assert "npx" not in runtime_text


def test_exa_tool_allowlist_is_exact(exa_config):
    assert exa_config.url == EXA_URL
    assert exa_config.tools == ALLOWED
```

Also assert the Exa MCP exists only under the isolated config and that no
runtime file introduces another search provider or fallback.

**Step 2: Run red**

```bash
pytest -q tests/test_exa_architecture.py
```

Expected: FAIL because no Exa feature contract exists.

**Step 3: Extend the scanner and README**

Teach the scanner to reject runtime references to local Exa packages, `npx`,
advanced/agent/deprecated tools, and non-Exa search fallback. Document the two
tools and isolated-only behavior.

**Step 4: Run green**

```bash
pytest -q tests/test_exa_architecture.py
python3 scripts/check-prohibited-dependencies.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_exa_architecture.py scripts/check-prohibited-dependencies.py README.md
git commit -m "test: establish isolated Exa architecture contract"
```

### Task 2: Implement the fail-closed headers helper

**Files:**
- Create: `scripts/exa-headers-helper.py`
- Create: `tests/test_exa_headers_helper.py`

**Step 1: Write the valid-file test**

```python
def test_valid_key_emits_only_x_api_key(run_helper, key_file):
    key_file.write_text("test-exa-key\n")
    key_file.chmod(0o600)
    result = run_helper(
        server="exa-search",
        url="https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"x-api-key": "test-exa-key"}
    assert result.stderr == ""
```

**Step 2: Add the counterexample matrix**

Add missing, empty, multiline, directory, symlink, wrong owner (skip when not
permitted), 0644, wrong server, HTTP, wrong host, wrong path, and unexpected
tool-query tests. For every rejected case, assert no output contains the key.

**Step 3: Run red**

```bash
pytest -q tests/test_exa_headers_helper.py
```

Expected: FAIL because the helper does not exist.

**Step 4: Implement the minimal helper**

Use `os.lstat`, `stat.S_ISREG`, `os.getuid`, exact mode 0600, `urlsplit`, and
`json.dumps`. The key path is fixed relative to HOME:

```python
KEY_PATH = Path.home() / ".config" / "claude-maas" / "exa-api-key"
EXPECTED_SERVER = "exa-search"
EXPECTED_HOST = "mcp.exa.ai"
EXPECTED_PATH = "/mcp"
EXPECTED_TOOLS = "web_search_exa,web_fetch_exa"
```

Return stable error codes only. Never log file content or environment values.

**Step 5: Run green**

```bash
pytest -q tests/test_exa_headers_helper.py
python3 -m py_compile scripts/exa-headers-helper.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/exa-headers-helper.py tests/test_exa_headers_helper.py
git commit -m "feat: add secure Exa MCP headers helper"
```

### Task 3: Configure isolated Exa MCP and permissions

**Files:**
- Create: `scripts/configure-exa.sh`
- Create: `tests/test_exa_setup.py`
- Modify: `assets/manifest-schema.json`

**Step 1: Write failing installer tests**

Use a temporary HOME and invoke the real script. Assert:

```python
def test_setup_keeps_key_out_of_json_and_output(run_setup, home):
    result = run_setup(stdin="test-exa-key\n")
    assert result.returncode == 0
    key = home / ".config/claude-maas/exa-api-key"
    assert key.stat().st_mode & 0o777 == 0o600
    assert key.read_text() == "test-exa-key\n"
    combined = result.stdout + result.stderr
    assert "test-exa-key" not in combined
    assert "test-exa-key" not in (home / ".claude-maas/.claude.json").read_text()
```

Assert exact HTTP URL, absolute helper path, two exact permissions, additive
merge, strict modes, atomic writes, idempotency, and unchanged MaaS config.

**Step 2: Run red**

```bash
pytest -q tests/test_exa_setup.py
```

Expected: FAIL because the installer is absent.

**Step 3: Implement setup**

Read exactly one key line from stdin. Write it atomically. Use Python stdlib to
merge one `mcpServers.exa-search` object into
`~/.claude-maas/.claude.json` and two exact allow entries into
`~/.claude-maas/settings.json`. Record owned paths and fields in the existing
manifest without recording a key.

**Step 4: Run green**

```bash
pytest -q tests/test_exa_setup.py tests/test_setup.py tests/test_launcher.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/configure-exa.sh tests/test_exa_setup.py assets/manifest-schema.json
git commit -m "feat: configure Exa in isolated MaaS profile"
```

### Task 4: Transactionally retire plain-Claude Exa

**Files:**
- Create: `scripts/migrate-exa.sh`
- Create: `tests/test_exa_migration.py`

**Step 1: Write dry-run and preservation tests**

Seed plain `.claude.json` and settings with the exact old Exa shape plus
unrelated MCP, env, permissions, OAuth metadata, theme, hooks, and 1M context.
Assert dry-run does not change any byte and never prints the key.

**Step 2: Write apply tests**

Assert apply removes only:

```text
mcpServers.exa-search (command == exa-mcp)
env.EXA_API_KEY
mcp__exa-search__exa_search
mcp__exa-search__exa_answer
mcp__exa-search__exa_find_similar
mcp__exa-search__exa_contents
```

Assert an unknown Exa entry fails closed and simulated second-file failure
restores the first file from the in-memory transaction snapshot.

**Step 3: Run red**

```bash
pytest -q tests/test_exa_migration.py
```

Expected: FAIL because the migrator is absent.

**Step 4: Implement exact migration**

Require `--dry-run` or `--apply`. Use Python to parse both files, compare the
legacy fingerprint, render both new documents in memory, write same-directory
0600 temporaries, fsync, and replace transactionally. Do not create persistent
key-bearing backups.

**Step 5: Run green**

```bash
pytest -q tests/test_exa_migration.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/migrate-exa.sh tests/test_exa_migration.py
git commit -m "feat: migrate Exa out of plain Claude"
```

### Task 5: Add isolated Exa uninstall lifecycle

**Files:**
- Create: `scripts/uninstall-exa.sh`
- Create: `tests/test_exa_uninstall.py`
- Modify: `docs/OPERATIONS.md`
- Modify: `docs/SECURITY.md`

**Step 1: Write failing lifecycle tests**

Assert default uninstall removes only the owned isolated MCP entry and two
permissions, retains the key, and is idempotent. Assert `--purge` additionally
deletes only `exa-api-key`. Preserve MaaS and unrelated MCP state.

**Step 2: Run red**

```bash
pytest -q tests/test_exa_uninstall.py
```

Expected: FAIL because the command is absent.

**Step 3: Implement uninstall**

Validate ownership from the manifest, fail closed on drift, merge-delete exact
fields, and require explicit `--purge` for the secret. Never uninstall a global
npm package.

**Step 4: Document operations and incident response**

Add install, rotation, migration dry-run/apply, default uninstall, purge, 401,
403, 429, timeout, and exposed-key rotation procedures.

**Step 5: Run green**

```bash
pytest -q tests/test_exa_uninstall.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/uninstall-exa.sh tests/test_exa_uninstall.py docs/OPERATIONS.md docs/SECURITY.md
git commit -m "feat: add Exa lifecycle and security operations"
```

### Task 6: Add offline and live Exa verification

**Files:**
- Create: `scripts/verify-exa.sh`
- Create: `tests/test_verify_exa.py`
- Modify: `Makefile`

**Step 1: Write verifier contract tests**

Assert gate order and fail-closed aggregation for: key mode, helper identity,
plain absence, isolated config, exact tools, MCP health, live search, live
fetch, MaaS model, and 1M context. Test redaction with the key embedded in
longer stdout/stderr strings.

**Step 2: Run red**

```bash
pytest -q tests/test_verify_exa.py
```

Expected: FAIL because the verifier is absent.

**Step 3: Implement verifier**

Use checkout-pinned helpers. Read the key from stdin. For release mode, run:

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude-maas" claude mcp list
claude mcp list
claude-maas --print --output-format json '<fixed search/fetch canary>'
```

Parse results without printing response bodies. Require isolated Connected,
plain absent, exact tool names, at least one HTTPS source URL, glm-5.2 only,
and contextWindow 1000000.

**Step 4: Add Make targets**

```make
verify-exa-offline:
	pytest -q tests/test_exa_*.py tests/test_verify_exa.py

verify-exa-live:
	./scripts/verify-exa.sh
```

**Step 5: Run green**

```bash
pytest -q tests/test_verify_exa.py
make verify-exa-offline
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/verify-exa.sh tests/test_verify_exa.py Makefile
git commit -m "test: add isolated Exa release gates"
```

### Task 7: Run full regression and review

**Files:**
- Modify only files implicated by a failing test.

**Step 1: Run syntax checks**

```bash
bash -n scripts/configure-exa.sh scripts/migrate-exa.sh scripts/uninstall-exa.sh scripts/verify-exa.sh
python3 -m py_compile scripts/exa-headers-helper.py
```

Expected: exit 0.

**Step 2: Run the full offline gate**

```bash
make verify-offline
make verify-exa-offline
```

Expected: zero failures and a test count above the current 354 baseline.

**Step 3: Scan for secret/runtime violations**

Confirm no long credential assignments, local Exa runtime references, npm
commands, extra tools, or search fallback paths in tracked runtime files.

**Step 4: Review against the PRD**

Use `@review` with the implementation-start commit as the fixed point and
`docs/PRD_EXA_SEARCH_V1.md` as the spec. Resolve all P0/P1 findings.

**Step 5: Commit any focused corrections**

```bash
git add <exact-files>
git commit -m "fix: close Exa integration review findings"
```

### Task 8: Rotate, migrate, install, and collect live evidence

**Files:**
- Create: `evidence/RELEASE-EVIDENCE-EXA.md`
- Modify: `docs/PRD_EXA_SEARCH_V1.md` only after every gate passes.

**Step 1: Obtain a rotated Exa key**

Revoke the key exposed in prior settings/backups and create a new key. Never
paste it into chat, argv, JSON, or Git.

**Step 2: Run migration dry-run**

```bash
./scripts/migrate-exa.sh --dry-run
```

Expected: only the known plain Exa MCP, EXA_API_KEY, and four old permissions.

**Step 3: Apply migration and configure isolated Exa**

```bash
./scripts/migrate-exa.sh --apply
printf '%s\n' "$NEW_EXA_API_KEY" | ./scripts/configure-exa.sh --apply
```

Expected: both exit 0 without printing the key.

**Step 4: Run live verification**

```bash
printf '%s\n' "$NEW_EXA_API_KEY" | make verify-exa-live
```

Expected: plain absent, isolated Connected, search/fetch PASS, exact tools,
glm-5.2 only, contextWindow 1000000, overall exit 0.

**Step 5: Generate evidence**

Record commit/tree, Claude Code version, endpoint host/path, helper/script
digests, tool names, gate statuses/durations, model, and context. Record no key,
query, source body, prompt, or response.

**Step 6: Apply `@verification-before-completion`**

Re-read every Definition of Done item in the PRD and attach fresh evidence.
Only then change status from Approved for implementation to RELEASE.

**Step 7: Commit evidence**

```bash
git add evidence/RELEASE-EVIDENCE-EXA.md docs/PRD_EXA_SEARCH_V1.md
git commit -m "docs: close isolated Exa search release"
```
