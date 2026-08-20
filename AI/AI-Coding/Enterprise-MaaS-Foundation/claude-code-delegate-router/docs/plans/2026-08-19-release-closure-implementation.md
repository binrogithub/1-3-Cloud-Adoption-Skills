# Direct MaaS Router v1 Release Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Direct MaaS Delegate Router release gates execute the real probes, prove OAuth/MaaS isolation, and produce current secret-free live evidence.

**Architecture:** Keep the direct MaaS and task-delegation architecture unchanged. Repair the release trust chain by passing Claude output through a protected file, pinning helpers to the checkout, making isolation observable, and generating evidence from structured gate results.

**Tech Stack:** Bash 4+, Python 3 standard library, pytest, official Claude Code CLI, Huawei MaaS native Anthropic Messages API, Git, SHA-256.

---

### Task 1: Add a real E2E probe regression harness

**Files:**
- Create: `tests/test_claude_e2e_probe.py`
- Test: `tests/claude_e2e_probe.sh`

**Step 1: Write the failing valid-response test**

Create a temporary executable named `claude` that extracts the marker path
from the final prompt, creates it, and writes:

```json
{"modelUsage":{"glm-5.2":{"inputTokens":1,"outputTokens":1}}}
```

Run the tracked `tests/claude_e2e_probe.sh` with only
`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, and the fake binary on PATH.
Assert exit code 0 and both success markers in stdout.

**Step 2: Run the focused test and confirm red**

Run:

```bash
pytest -q tests/test_claude_e2e_probe.py::test_valid_json_and_tool_marker_pass
```

Expected: FAIL because the validator reads an empty stdin; current stderr also
contains `unbound variable`.

**Step 3: Add the negative response matrix**

Parameterize empty output, invalid JSON, missing `modelUsage`, mixed
`glm-5.2`/another model, missing marker, and non-zero Claude exit. Each must
assert a non-zero probe result and a stable safe error code.

**Step 4: Confirm all new cases are discovered**

Run:

```bash
pytest --collect-only -q tests/test_claude_e2e_probe.py
```

Expected: the valid case plus every negative case is listed.

**Step 5: Commit the red tests**

```bash
git add tests/test_claude_e2e_probe.py
git commit -m "test: expose real Claude E2E probe failures"
```

### Task 2: Repair E2E response and model validation

**Files:**
- Modify: `tests/claude_e2e_probe.sh:84-154`
- Test: `tests/test_claude_e2e_probe.py`

**Step 1: Write the response to the protected probe directory**

After capturing Claude output, create `response.json` under `TMP_DIR`, set mode
0600, and write with `printf`. Do not print it:

```bash
RESPONSE_FILE="$TMP_DIR/response.json"
umask 077
printf '%s' "$RESPONSE_JSON" >"$RESPONSE_FILE"
```

**Step 2: Read the explicit file from Python**

Keep the Python validator in a heredoc, but pass the response path as argv:

```bash
python3 - "$MODEL" "$RESPONSE_FILE" <<'PYEOF'
import json
from pathlib import Path
import sys

model = sys.argv[1]
obj = json.loads(Path(sys.argv[2]).read_text())
PYEOF
```

Never combine piped response data with `python3 - <<HEREDOC`.

**Step 3: Enforce the exact model set**

Add one extraction function for supported Claude JSON `modelUsage` shapes.
Reject an empty set and require `models == {model}`. Delete raw substring
fallback.

**Step 4: Replace `$1` with named values and stable errors**

Failure messages must use `$MODEL` and the error codes defined in
`docs/PRD_RELEASE_CLOSURE_V1.md`; no unset positional variables are allowed.

**Step 5: Run the focused tests**

Run:

```bash
pytest -q tests/test_claude_e2e_probe.py
```

Expected: PASS, with all valid and negative cases covered.

**Step 6: Run shell syntax validation**

```bash
bash -n tests/claude_e2e_probe.sh
```

Expected: exit 0.

**Step 7: Commit**

```bash
git add tests/claude_e2e_probe.sh tests/test_claude_e2e_probe.py
git commit -m "fix: validate real Claude E2E output"
```

### Task 3: Pin release helpers to the checkout

**Files:**
- Modify: `scripts/verify.sh:70-126`
- Modify: `tests/test_verify_contract.py`

**Step 1: Write the PATH-substitution regression test**

Place always-pass files named `live_maas_probe.py`, `claude_e2e_probe.sh`, and
`check-prohibited-dependencies.py` first on PATH. Give each a sentinel write.
Run `scripts/verify.sh` and assert none of the sentinels exists.

**Step 2: Run it and confirm red**

```bash
pytest -q tests/test_verify_contract.py -k path_stub
```

Expected: FAIL because current `resolve_script` chooses PATH first.

**Step 3: Resolve helpers only from `PROJECT_ROOT`**

Remove PATH-first `resolve_script` behavior for release execution. Resolve the
three exact tracked paths, reject missing/non-regular/untracked files, and log
their SHA-256 values.

**Step 4: Refactor existing verifier tests**

Exercise the tracked scripts and inject fake network/CLI behavior at their
external boundary. Do not replace the script being asserted. If a test-only
override remains necessary, require an explicit test flag and make its final
state `UNTRUSTED_TEST_RESULT`, never release PASS.

**Step 5: Run verifier tests**

```bash
pytest -q tests/test_verify_contract.py tests/test_claude_e2e_probe.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/verify.sh tests/test_verify_contract.py tests/test_claude_e2e_probe.py
git commit -m "fix: pin release probes to verified checkout"
```

### Task 4: Make plain-Claude isolation observable

**Files:**
- Modify: `scripts/verify.sh:280-314`
- Modify: `client/claude-maas`
- Modify: `tests/test_verify_contract.py`
- Modify: `tests/test_launcher.py`

**Step 1: Write failing isolation tests**

Use a recording fake official Claude binary. Assert that the gate invokes
`--version`, clears all MaaS `ANTHROPIC_*` values in that subprocess, compares
the resolved binary used by both commands, and rejects a wrapper/self-link.

**Step 2: Confirm red**

```bash
pytest -q tests/test_verify_contract.py -k plain_claude
```

Expected: FAIL because the current gate never invokes plain Claude.

**Step 3: Add a machine-readable binary resolution command**

Add a non-secret diagnostic mode to `client/claude-maas`, for example
`resolve-binary`, that prints only the canonical official CLI path and digest.
It must not load or print the API key.

**Step 4: Implement the gate**

Resolve and canonicalize both binaries, reject recursion or mismatch, then run:

```bash
env -u ANTHROPIC_BASE_URL \
    -u ANTHROPIC_AUTH_TOKEN \
    -u ANTHROPIC_API_KEY \
    -u ANTHROPIC_MODEL \
    "$PLAIN_CLAUDE_BIN" --version
```

Capture version and digest only. This command must not make a model request.

**Step 5: Run focused tests**

```bash
pytest -q tests/test_verify_contract.py -k plain_claude
pytest -q tests/test_launcher.py -k binary
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/verify.sh client/claude-maas tests/test_verify_contract.py tests/test_launcher.py
git commit -m "fix: verify plain Claude binary isolation"
```

### Task 5: Generate fail-closed release evidence

**Files:**
- Create: `scripts/write-release-evidence.py`
- Create: `tests/test_release_evidence.py`
- Modify: `scripts/verify.sh`
- Modify: `evidence/RELEASE-CHECKLIST.md`

**Step 1: Write failing evidence tests**

Define a minimal structured result schema. Test rejection of pending, skipped,
untrusted, dirty-tree, stale commit/tree, and digest mismatch states. Test that
known-unsupported image is accepted only with HTTP 400 and no fallback.

**Step 2: Confirm red**

```bash
pytest -q tests/test_release_evidence.py
```

Expected: FAIL because the writer does not exist.

**Step 3: Implement the writer with Python stdlib**

Read structured gate results, validate every required terminal state, and
write Markdown containing commit/tree, UTC time, CLI version/digest, endpoint
metadata, model, helper digests, gate status/duration, and final verdict. Never
accept or serialize a key, prompt, OAuth metadata, or response body.

**Step 4: Integrate verifier output**

Have `scripts/verify.sh` create a protected result file and optionally pass it
to the evidence writer after all gates complete. A failed gate must still
produce a safe FAIL record and a non-zero verifier exit.

**Step 5: Run tests**

```bash
pytest -q tests/test_release_evidence.py tests/test_verify_contract.py
```

Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/write-release-evidence.py tests/test_release_evidence.py scripts/verify.sh evidence/RELEASE-CHECKLIST.md
git commit -m "feat: generate fail-closed release evidence"
```

### Task 6: Run full offline verification

**Files:**
- Modify only if a failing regression identifies a root cause.

**Step 1: Run syntax checks**

```bash
bash -n client/claude-maas scripts/verify.sh tests/claude_e2e_probe.sh
python3 -m py_compile scripts/check-prohibited-dependencies.py scripts/delegate scripts/workflow tests/live_maas_probe.py scripts/write-release-evidence.py
```

Expected: all exit 0.

**Step 2: Run the prohibited-dependency gate**

```bash
python3 scripts/check-prohibited-dependencies.py
```

Expected: exit 0 with zero offenders.

**Step 3: Run the full suite**

```bash
make verify-offline
```

Expected: exit 0, zero failed tests, and test count greater than the 312-test
baseline.

**Step 4: Review the diff against both PRDs**

Use `@review` with `main` as the fixed point. Resolve all P0 findings before
continuing.

**Step 5: Commit any test-only corrections separately**

```bash
git add <exact-files-changed>
git commit -m "test: close release verification regressions"
```

### Task 7: Rotate the key and run current live gates

**Files:**
- Modify: `evidence/RELEASE-CHECKLIST.md` via the evidence writer only.

**Step 1: Obtain a rotated MaaS key**

Rotate the development key previously exposed in an interactive channel. Keep
the new key out of shell history and Git.

**Step 2: Confirm a clean checkout**

```bash
git status --porcelain
```

Expected: no output.

**Step 3: Run live verification from stdin**

```bash
printf '%s\n' "$ROTATED_MAAS_KEY" | make verify-live
```

Expected: text, stream, thinking, tool-auto, tool-forced, token-only Claude,
tool round trip, and plain isolation PASS; image is exactly
KNOWN_UNSUPPORTED/HTTP 400; overall exit 0.

**Step 4: Scan captured output and evidence**

Confirm neither contains the key, response bodies, prompts, or OAuth metadata.
Confirm no gate is pending, skipped, or untrusted.

**Step 5: Commit evidence**

```bash
git add evidence/RELEASE-CHECKLIST.md
git commit -m "chore: record verified direct MaaS release gates"
```

### Task 8: Final release decision

**Files:**
- Modify: `docs/PRD_RELEASE_CLOSURE_V1.md`
- Modify: `evidence/RELEASE-CHECKLIST.md`

**Step 1: Re-run the complete gates on the release candidate**

Run offline verification again, then repeat the live command with the rotated
key. Evidence must reference the exact verified commit/tree and helper digests.

**Step 2: Verify allowed evidence-only diff**

Compare the verified commit with the evidence commit. Only approved evidence
files may differ.

**Step 3: Apply `@verification-before-completion`**

Read every Definition of Done item in
`docs/PRD_RELEASE_CLOSURE_V1.md` and attach its fresh command result. Do not
infer completion from the test suite alone.

**Step 4: Change the decision only with complete evidence**

If every item passes, update `Decision: HOLD` to `Decision: RELEASE` and mark
the checklist complete. Otherwise leave HOLD and record the exact blocker.

**Step 5: Commit**

```bash
git add docs/PRD_RELEASE_CLOSURE_V1.md evidence/RELEASE-CHECKLIST.md
git commit -m "docs: close direct MaaS v1 release"
```

