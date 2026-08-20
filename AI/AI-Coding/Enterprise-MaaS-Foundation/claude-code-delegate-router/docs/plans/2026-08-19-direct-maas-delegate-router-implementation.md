# Direct MaaS Delegate Router Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an isolated `claude-maas` launcher and OAuth task-delegation workflow that connects Claude Code directly to Huawei MaaS `glm-5.2` through the native Anthropic API, with no LiteLLM, CCR, Sidecar, or fallback.

**Architecture:** Plain `claude` remains the official OAuth client. `claude-maas` wraps the same official CLI in an isolated `CLAUDE_CONFIG_DIR` and injects only the MaaS Anthropic base URL, Bearer token, and fixed GLM-5.2 model. `delegate` and `workflow` provide bounded task-level orchestration; compatibility knowledge is enforced by release canaries rather than runtime middleware.

**Tech Stack:** Bash 4+, Python 3.10+ standard library, pytest, JSON Schema, official Claude Code CLI 2.1.x+, Huawei MaaS Anthropic Messages API.

---

Execute from a dedicated Git worktree. Use `@test-driven-development` for every implementation task and `@verification-before-completion` before each completion claim.

### Task 1: Repository skeleton and prohibited-dependency gate

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `tests/test_architecture_contract.py`
- Create: `scripts/check-prohibited-dependencies.py`

**Step 1: Write the failing architecture test**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED = ("litellm", "claude-code-router", "openrouter", "premium-openrouter")


def test_runtime_files_do_not_depend_on_removed_gateways():
    runtime = [
        *ROOT.glob("client/*"),
        *ROOT.glob("scripts/*"),
    ]
    offenders = []
    for path in runtime:
        if not path.is_file() or path.name == "check-prohibited-dependencies.py":
            continue
        text = path.read_text(errors="ignore").lower()
        for word in PROHIBITED:
            if word in text:
                offenders.append((str(path.relative_to(ROOT)), word))
    assert offenders == []
```

**Step 2: Run the test to establish the baseline**

Run: `pytest tests/test_architecture_contract.py -v`  
Expected: PASS on the empty runtime skeleton.

**Step 3: Add the scanner and project overview**

The scanner must inspect executable/config dependency surfaces, skip `docs/`
historical explanations, print one offender per line, and exit 1 on a match.
README must state the two commands and the absence of any HTTP router.

**Step 4: Verify**

Run: `python3 scripts/check-prohibited-dependencies.py && pytest -q`  
Expected: exit 0 and all tests pass.

**Step 5: Commit**

```bash
git add README.md .gitignore pytest.ini tests scripts/check-prohibited-dependencies.py
git commit -m "chore: establish direct MaaS architecture contract"
```

### Task 2: Configuration and secret storage installer

**Files:**
- Create: `client/claude-maas-setup.sh`
- Create: `tests/test_setup.py`
- Create: `tests/helpers/fake-claude`

**Step 1: Write failing installer tests**

Use a temporary HOME and invoke the installer with the key on stdin. Assert:

```python
def test_setup_stores_key_as_data_with_strict_permissions(run_setup, tmp_path):
    result = run_setup(stdin="test-secret-key\n")
    assert result.returncode == 0
    key = tmp_path / ".config/claude-maas/api-key"
    config = tmp_path / ".config/claude-maas/config.json"
    assert key.read_text() == "test-secret-key\n"
    assert key.stat().st_mode & 0o777 == 0o600
    assert config.stat().st_mode & 0o777 == 0o600
    assert "test-secret-key" not in result.stdout + result.stderr


def test_setup_rejects_empty_or_multiline_key(run_setup):
    assert run_setup(stdin="\n").returncode != 0
    assert run_setup(stdin="one\ntwo\n").returncode != 0
```

Also snapshot fake HOME shell profiles and `.claude*` files and assert they are
unchanged.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_setup.py -v`  
Expected: FAIL because the installer does not exist.

**Step 3: Implement the minimal installer**

Requirements:

- `set -euo pipefail`;
- accept `--base-url`, `--model`, `--context-tokens`, `--max-output-tokens`;
- default base URL ends in `/anthropic`, not `/anthropic/v1`;
- reject URL credentials, fragments, query strings, non-HTTPS except explicit localhost test mode;
- read exactly one non-empty key line from stdin;
- create `~/.config/claude-maas` as `0700`;
- write key/config through `mktemp` in that directory, `chmod 0600`, atomic `mv`;
- never write shell profiles or plain Claude config;
- install project-owned launchers into `~/.local/bin` using copies/symlinks whose ownership is recorded in a manifest.

**Step 4: Run tests**

Run: `pytest tests/test_setup.py -v`  
Expected: all installer tests pass.

**Step 5: Commit**

```bash
git add client/claude-maas-setup.sh tests/test_setup.py tests/helpers/fake-claude
git commit -m "feat: add isolated MaaS credential setup"
```

### Task 3: `claude-maas` isolated launcher

**Files:**
- Create: `client/claude-maas`
- Create: `client/claude-select`
- Create: `tests/test_launcher.py`

**Step 1: Write failing child-environment tests**

The fake Claude binary serializes argv and a whitelist of environment variable
names. Assert:

```python
def test_launcher_injects_only_child_maas_environment(launch, parent_env):
    captured = launch("-p", "OK")
    assert captured["env"]["ANTHROPIC_BASE_URL"].endswith("/anthropic")
    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == "test-secret-key"
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert captured["env"]["ANTHROPIC_MODEL"] == "glm-5.2"
    assert captured["env"]["CLAUDE_CONFIG_DIR"].endswith("/.claude-maas")
    assert not any(name.startswith("ANTHROPIC_") for name in parent_env)


def test_launcher_does_not_source_key_file_as_shell(launch, key_file):
    key_file.write_text("$(touch /tmp/must-not-exist)\n")
    launch("--version")
    assert not Path("/tmp/must-not-exist").exists()
```

Test `--version`, `doctor`, and `mcp` do not receive an inserted model flag;
normal interactive/print invocations do.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_launcher.py -v`  
Expected: FAIL because launchers do not exist.

**Step 3: Implement launchers**

`claude-maas` must read JSON with Python stdlib, read the secret with
`IFS= read -r`, validate file modes, export child-only variables, locate the
real `claude` without resolving to itself, start no service, and `exec` the
official binary. `claude-select native` uses plain `claude`; `maas` uses
`claude-maas`; `status` prints no secret.

**Step 4: Run tests**

Run: `pytest tests/test_launcher.py -v`  
Expected: all launcher and selector tests pass.

**Step 5: Commit**

```bash
git add client/claude-maas client/claude-select tests/test_launcher.py
git commit -m "feat: add direct MaaS Claude launcher"
```

### Task 4: Direct Anthropic protocol canary

**Files:**
- Create: `tests/live_maas_probe.py`
- Create: `tests/fixtures/valid-thinking-stream.sse`
- Create: `tests/fixtures/invalid-pretty-json-stream.sse`
- Create: `tests/fixtures/invalid-done-stream.sse`
- Create: `tests/test_sse_contract.py`

**Step 1: Write failing SSE parser tests**

```python
def test_valid_stream_passes(parse_sse, fixture):
    result = parse_sse(fixture("valid-thinking-stream.sse"))
    assert result.event_types[-1] == "message_stop"
    assert result.errors == []


def test_pretty_json_and_done_regressions_fail(parse_sse, fixture):
    assert "unprefixed" in parse_sse(fixture("invalid-pretty-json-stream.sse")).errors
    assert "openai_done" in parse_sse(fixture("invalid-done-stream.sse")).errors
```

Add tests for thinking/text/tool block-to-delta pairing.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_sse_contract.py -v`  
Expected: FAIL because the parser is absent.

**Step 3: Implement canary, not middleware**

The script must read the key from stdin, never echo it, and execute named
probes: `text`, `stream`, `thinking`, `tool-auto`, `tool-forced`, `image`, or
`all`. It must validate responses and report only status/schema facts. `image`
currently expects typed unsupported HTTP 400 and is not a global failure.

**Step 4: Run offline tests**

Run: `pytest tests/test_sse_contract.py -v`  
Expected: valid fixture passes; both historical regressions are detected.

**Step 5: Commit**

```bash
git add tests/live_maas_probe.py tests/fixtures tests/test_sse_contract.py
git commit -m "test: add native MaaS Anthropic contract canary"
```

### Task 5: Structured single-task delegate runner

**Files:**
- Create: `scripts/delegate`
- Create: `assets/brief-schema.json`
- Create: `tests/test_delegate.py`

**Step 1: Write failing safety tests**

```python
def test_attempt_and_turn_limits_are_clamped(delegate):
    assert delegate.bounded_attempts(99) == 2
    assert delegate.bounded_turns(999) == delegate.MAX_TURNS


def test_image_brief_is_rejected_before_launch(delegate, fake_client):
    result = delegate.run({"task_type": "image", "goal": "inspect image"})
    assert result["status"] == "unsupported_capability"
    assert fake_client.calls == []


def test_failed_twice_returns_needs_escalation(delegate, fake_client):
    fake_client.fail_always()
    result = delegate.run(valid_brief(max_attempts=99))
    assert result["status"] == "needs_escalation"
    assert len(fake_client.calls) == 2
```

Test bounded Retry-After, timeout, acceptance authority, audit redaction, and
`--max-turns` propagation.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_delegate.py -v`  
Expected: FAIL because the runner is absent.

**Step 3: Implement minimal runner**

Port the reference `delegate` contract, rename its client default to
`claude-maas`, add schema validation, image rejection, `--max-turns`, model
assertion, and `fallback:false` audit field. Never store brief text or tool
arguments in audit. Run acceptance with an explicit cwd and timeout.

**Step 4: Run tests**

Run: `pytest tests/test_delegate.py -v`  
Expected: all delegate safety tests pass.

**Step 5: Commit**

```bash
git add scripts/delegate assets/brief-schema.json tests/test_delegate.py
git commit -m "feat: add bounded GLM-5.2 task delegation"
```

### Task 6: Workflow fan-out and isolation

**Files:**
- Create: `scripts/workflow`
- Create: `assets/manifest-schema.json`
- Create: `tests/test_workflow.py`

**Step 1: Write failing workflow tests**

```python
def test_overlapping_scopes_are_rejected_before_workers_start(workflow, delegate):
    manifest = fanout(items=[{"scope": ["src/a.py"]}, {"scope": ["src/a.py"]}])
    result = workflow.run(manifest)
    assert result["status"] == "invalid_manifest"
    assert delegate.calls == []


def test_remainder_over_thirty_percent_aborts(workflow, delegate):
    delegate.fail_items(2, total=5)
    result = workflow.run(fanout_five())
    assert result["status"] == "reclassify_premium"
```

Test concurrency hard cap, deterministic item result order, and aggregate
verification timeout.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_workflow.py -v`  
Expected: FAIL because the runner is absent.

**Step 3: Implement workflow**

Port only `fanout` and `suborchestrate` behavior. Enforce disjoint scope before
creating a thread pool. Record per-item files under
`~/.claude-hybrid/workflows/<run-id>/` with mode `0600`. Do not add worktrees or
Sidecar routing in v1.

**Step 4: Run tests**

Run: `pytest tests/test_workflow.py -v`  
Expected: all workflow tests pass.

**Step 5: Commit**

```bash
git add scripts/workflow assets/manifest-schema.json tests/test_workflow.py
git commit -m "feat: add isolated MaaS workflow delegation"
```

### Task 7: OAuth orchestration policy and advisory hook

**Files:**
- Create: `assets/orchestrator-policy.md`
- Create: `scripts/route-hint.sh`
- Create: `scripts/configure-policy.sh`
- Create: `tests/test_policy_install.py`
- Create: `tests/test_route_hint.py`

**Step 1: Write failing additive-merge tests**

Assert installation preserves arbitrary existing CLAUDE.md text and hooks,
replaces only its own marker block, is idempotent, and never writes an
`ANTHROPIC_*` env entry. Route-hint fixtures must classify images/security as
OAuth and ordinary tests/docs as MaaS, with premium signals winning ties.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_policy_install.py tests/test_route_hint.py -v`  
Expected: FAIL because policy assets do not exist.

**Step 3: Implement policy tooling**

Use the approved PRD taxonomy. The hook is advisory and outputs one concise
context line. It must not block, invoke MaaS, inspect credentials, or mutate
files. `configure-policy.sh` writes a fresh backup before additive JSON merge.

**Step 4: Run tests**

Run: `pytest tests/test_policy_install.py tests/test_route_hint.py -v`  
Expected: all policy tests pass.

**Step 5: Commit**

```bash
git add assets/orchestrator-policy.md scripts/route-hint.sh scripts/configure-policy.sh tests/test_policy_install.py tests/test_route_hint.py
git commit -m "feat: add OAuth task routing policy"
```

### Task 8: Verification command and real Claude Code probes

**Files:**
- Create: `scripts/verify.sh`
- Create: `tests/claude_e2e_probe.sh`
- Create: `tests/test_verify_contract.py`

**Step 1: Write failing verifier contract tests**

Test that verify requires and reports these gates in order: config modes,
direct API text/stream/thinking/tools, token-only Claude CLI, tool round trip,
plain Claude isolation, and prohibited dependency scan. Assert secret strings
inserted into fake errors are redacted.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_verify_contract.py -v`  
Expected: FAIL because verify scripts are absent.

**Step 3: Implement verifier**

The E2E probe creates a validated `mktemp -d`, sets an empty
`CLAUDE_CONFIG_DIR`, uses only `ANTHROPIC_AUTH_TOKEN`, invokes
`claude --model glm-5.2 --print --output-format json`, checks `modelUsage`, and
executes one harmless Bash marker in the temporary directory. Trap cleanup.
Never use root-only `--dangerously-skip-permissions`; pre-authorize the exact
test tool with `--allowedTools=Bash`.

**Step 4: Run offline verifier tests**

Run: `pytest tests/test_verify_contract.py -v`  
Expected: all verifier contract tests pass.

**Step 5: Commit**

```bash
git add scripts/verify.sh tests/claude_e2e_probe.sh tests/test_verify_contract.py
git commit -m "test: add direct MaaS release verification"
```

### Task 9: Migration and uninstall safety

**Files:**
- Create: `scripts/migrate.sh`
- Create: `scripts/uninstall.sh`
- Create: `tests/test_migration.py`
- Create: `tests/test_uninstall.py`

**Step 1: Write failing ownership tests**

Fixtures must contain mixed user and legacy settings. Assert dry-run is
byte-for-byte side-effect free, apply removes only values matching the ownership
manifest, OAuth metadata remains byte-identical, repeated apply/uninstall is a
no-op, and default uninstall retains Key/audit data.

**Step 2: Run tests to verify failure**

Run: `pytest tests/test_migration.py tests/test_uninstall.py -v`  
Expected: FAIL because scripts are absent.

**Step 3: Implement exact removal**

Require `--dry-run` or `--apply`; never infer apply. Create backups before
apply. Do not stop or modify a remote LiteLLM deployment. Remove only the
client-side legacy wrapper/config values proven by endpoint plus key
fingerprint plus marker ownership.

**Step 4: Run tests**

Run: `pytest tests/test_migration.py tests/test_uninstall.py -v`  
Expected: all migration and uninstall tests pass.

**Step 5: Commit**

```bash
git add scripts/migrate.sh scripts/uninstall.sh tests/test_migration.py tests/test_uninstall.py
git commit -m "feat: add reversible migration and uninstall"
```

### Task 10: Final documentation and release gate

**Files:**
- Modify: `README.md`
- Create: `docs/OPERATIONS.md`
- Create: `docs/SECURITY.md`
- Create: `Makefile`

**Step 1: Add documentation checks**

Extend `tests/test_architecture_contract.py` to assert README includes direct
endpoint setup, OAuth/MaaS-only modes, image limitation, no-Sidecar contract,
key rotation, uninstall, and verification. Assert all referenced local paths
exist.

**Step 2: Run tests to verify the documentation gate fails**

Run: `pytest tests/test_architecture_contract.py -v`  
Expected: FAIL for missing operations/security documents.

**Step 3: Write final docs and Make targets**

Required targets:

```make
test:
	pytest -q

verify-offline:
	python3 scripts/check-prohibited-dependencies.py
	pytest -q

verify-live:
	./scripts/verify.sh
```

Document incident response, Key rotation, endpoint regression triage, 429
governance, and the rule that a runtime router requires a new approved PRD.

**Step 4: Run fresh full verification**

Run: `make verify-offline`  
Expected: exit 0; all tests pass; prohibited dependency count is zero.

Run with a temporary/rotated MaaS Key: `printf '%s\n' "$HUAWEI_MAAS_API_KEY" | make verify-live`  
Expected: protocol and Claude E2E gates pass; image is reported as known unsupported; plain Claude isolation passes.

**Step 5: Commit**

```bash
git add README.md docs/OPERATIONS.md docs/SECURITY.md Makefile tests/test_architecture_contract.py
git commit -m "docs: complete direct MaaS operations guide"
```

### Task 11: Release evidence and final review

**Files:**
- Create: `evidence/RELEASE-CHECKLIST.md`

**Step 1: Record immutable evidence fields**

Record UTC timestamp, Git commit, Claude Code version, endpoint host (not Key),
model, offline test count, live gate names/results, and SHA-256 checksums of
release scripts. Never store response bodies or credentials.

**Step 2: Run `@requesting-code-review`**

Review against `docs/PRD.md`, emphasizing supplier isolation, no runtime
router, no Sidecar, credentials, and destructive-operation safety.

**Step 3: Run final verification after review changes**

Run: `make verify-offline` and then `make verify-live` with a rotated Key.  
Expected: both exit 0 with no skipped required gates.

**Step 4: Inspect the worktree**

Run: `git status --short && git diff --check`  
Expected: no uncommitted files and no whitespace errors after the evidence
commit.

**Step 5: Commit evidence**

```bash
git add evidence/RELEASE-CHECKLIST.md
git commit -m "chore: record direct MaaS release evidence"
```

After this plan is implemented and verified, use
`@finishing-a-development-branch` to choose merge, PR, or branch retention.
