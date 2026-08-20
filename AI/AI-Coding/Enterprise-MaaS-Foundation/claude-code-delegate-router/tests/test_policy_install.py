"""Tests for scripts/configure-policy.sh — additive policy installation.

These tests verify the PRD section 9.1 contract:

  * Installation preserves arbitrary existing CLAUDE.md text and hooks.
  * It replaces only its own marker block (fenced with identifiable markers).
  * It is idempotent (running twice produces identical output).
  * It NEVER writes an ANTHROPIC_* env entry to settings.json.
  * It writes a fresh backup (.bak) before additive JSON merge.
  * The policy block is marker-fenced for CLAUDE.md insertion.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIGURE_POLICY = ROOT / "scripts" / "configure-policy.sh"
POLICY_DOC = ROOT / "assets" / "orchestrator-policy.md"

BEGIN_MARKER = "<!-- BEGIN claude-maas-policy -->"
END_MARKER = "<!-- END claude-maas-policy -->"


# ---------------------------------------------------------------------------
# Fixture: run_configure
# ---------------------------------------------------------------------------


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env with all ANTHROPIC_* keys removed."""
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


@pytest.fixture()
def fake_home(tmp_path: Path):
    """Create a fake HOME with a ~/.claude/ directory containing pre-existing content."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    # Pre-existing CLAUDE.md with arbitrary user content.
    existing_claude_md = """# My Project

This is my custom CLAUDE.md content that must be preserved.

## Coding Standards

- Use 4-space indentation
- Always write docstrings

## Custom Instructions

Do not delete this section.
"""
    (claude_dir / "CLAUDE.md").write_text(existing_claude_md)

    # Pre-existing settings.json with user hooks that must be preserved.
    existing_settings = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo user-hook-before-bash",
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Read",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo user-hook-after-read",
                        }
                    ],
                }
            ],
        },
        "env": {"SOME_USER_VAR": "user-value"},
    }
    (claude_dir / "settings.json").write_text(json.dumps(existing_settings, indent=2))

    return tmp_path


@pytest.fixture()
def run_configure(fake_home: Path):
    """Return a callable that runs configure-policy.sh with HOME=fake_home."""
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(fake_home)

    def _run(*args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(CONFIGURE_POLICY), *args],
            env=base_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result

    return _run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_claude_md(home: Path) -> str:
    return (home / ".claude" / "CLAUDE.md").read_text()


def _read_settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text())


# ---------------------------------------------------------------------------
# Preservation of existing content
# ---------------------------------------------------------------------------


def test_preserves_existing_claude_md_text(run_configure, fake_home):
    """Arbitrary existing CLAUDE.md content must be preserved."""
    original = _read_claude_md(fake_home)
    result = run_configure()
    assert result.returncode == 0, result.stderr

    updated = _read_claude_md(fake_home)
    # Every line from the original must still be present.
    for line in original.strip().split("\n"):
        assert line in updated, f"lost line: {line!r}"


def test_preserves_existing_hooks(run_configure, fake_home):
    """Existing user hooks in settings.json must be preserved."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    hooks = settings.get("hooks", {})

    # The user's PreToolUse hook must still be present.
    pre_hooks = hooks.get("PreToolUse", [])
    pre_commands = []
    for entry in pre_hooks:
        for h in entry.get("hooks", []):
            pre_commands.append(h.get("command", ""))
    assert "echo user-hook-before-bash" in pre_commands

    # The user's PostToolUse hook must still be present.
    post_hooks = hooks.get("PostToolUse", [])
    post_commands = []
    for entry in post_hooks:
        for h in entry.get("hooks", []):
            post_commands.append(h.get("command", ""))
    assert "echo user-hook-after-read" in post_commands


def test_preserves_existing_permissions(run_configure, fake_home):
    """Existing permissions in settings.json must be preserved."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    assert settings.get("permissions", {}).get("allow") == ["Bash(ls:*)"]


def test_preserves_existing_env_vars(run_configure, fake_home):
    """Existing non-ANTHROPIC env vars in settings.json must be preserved."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    assert settings.get("env", {}).get("SOME_USER_VAR") == "user-value"


# ---------------------------------------------------------------------------
# Marker block replacement
# ---------------------------------------------------------------------------


def test_inserts_marker_block(run_configure, fake_home):
    """The policy block must be inserted with identifiable markers."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    content = _read_claude_md(fake_home)
    assert BEGIN_MARKER in content
    assert END_MARKER in content
    # BEGIN must come before END.
    assert content.index(BEGIN_MARKER) < content.index(END_MARKER)


def test_replaces_only_its_own_marker_block(run_configure, fake_home):
    """Re-running must replace only the marker block, not touch other content."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    content_after_first = _read_claude_md(fake_home)

    # Now modify the content outside the marker block.
    lines = content_after_first.split("\n")
    # Add a new user section at the end.
    lines.append("")
    lines.append("## New User Section")
    lines.append("This was added after the first install.")
    modified = "\n".join(lines)
    (fake_home / ".claude" / "CLAUDE.md").write_text(modified)

    result = run_configure()
    assert result.returncode == 0, result.stderr

    content_after_second = _read_claude_md(fake_home)

    # The new user section must still be present.
    assert "## New User Section" in content_after_second
    assert "This was added after the first install." in content_after_second

    # The marker block content should be the same as after the first run.
    def _extract_block(text: str) -> str:
        start = text.index(BEGIN_MARKER)
        end = text.index(END_MARKER) + len(END_MARKER)
        return text[start:end]

    assert _extract_block(content_after_first) == _extract_block(content_after_second)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotent_claude_md(run_configure, fake_home):
    """Running twice must produce identical CLAUDE.md output."""
    result1 = run_configure()
    assert result1.returncode == 0, result1.stderr
    content1 = _read_claude_md(fake_home)

    result2 = run_configure()
    assert result2.returncode == 0, result2.stderr
    content2 = _read_claude_md(fake_home)

    assert content1 == content2


def test_idempotent_settings_json(run_configure, fake_home):
    """Running twice must produce identical settings.json output."""
    result1 = run_configure()
    assert result1.returncode == 0, result1.stderr
    settings1 = _read_settings(fake_home)

    result2 = run_configure()
    assert result2.returncode == 0, result2.stderr
    settings2 = _read_settings(fake_home)

    assert settings1 == settings2


def test_idempotent_exit_code(run_configure):
    """Both runs must exit 0."""
    assert run_configure().returncode == 0
    assert run_configure().returncode == 0


# ---------------------------------------------------------------------------
# Never writes ANTHROPIC_* env entries
# ---------------------------------------------------------------------------


def test_never_writes_anthropic_env(run_configure, fake_home):
    """settings.json must never contain ANTHROPIC_* keys in env."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    env = settings.get("env", {})
    for key in env:
        assert not key.startswith("ANTHROPIC_"), f"forbidden env key: {key}"


def test_never_writes_anthropic_env_after_reinstall(run_configure, fake_home):
    """Re-running must also never introduce ANTHROPIC_* keys."""
    run_configure()
    run_configure()

    settings = _read_settings(fake_home)
    env = settings.get("env", {})
    for key in env:
        assert not key.startswith("ANTHROPIC_"), f"forbidden env key: {key}"


# ---------------------------------------------------------------------------
# Backup before merge
# ---------------------------------------------------------------------------


def test_writes_fresh_backup_before_merge(run_configure, fake_home):
    """A .bak backup must be written before merging settings.json."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings_bak = fake_home / ".claude" / "settings.json.bak"
    assert settings_bak.exists(), "settings.json.bak not created"

    # The backup should contain valid JSON (the pre-merge state).
    bak_data = json.loads(settings_bak.read_text())
    assert "hooks" in bak_data


def test_writes_claude_md_backup(run_configure, fake_home):
    """A .bak backup of CLAUDE.md must be written before merging."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    claude_md_bak = fake_home / ".claude" / "CLAUDE.md.bak"
    assert claude_md_bak.exists(), "CLAUDE.md.bak not created"


def test_backup_reflects_pre_merge_state(run_configure, fake_home):
    """The backup must reflect the state BEFORE the merge, not after."""
    original_settings = _read_settings(fake_home)

    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings_bak = fake_home / ".claude" / "settings.json.bak"
    bak_data = json.loads(settings_bak.read_text())

    # The backup should match the original pre-merge settings.
    assert bak_data == original_settings


# ---------------------------------------------------------------------------
# Route-hint hook is installed into settings.json
# ---------------------------------------------------------------------------


def test_route_hint_hook_installed(run_configure, fake_home):
    """The route-hint hook must be additively merged into settings.json hooks."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    hooks = settings.get("hooks", {})

    # The route-hint hook should be in one of the hook event types.
    # It should reference route-hint.sh.
    all_commands = []
    for event_type, entries in hooks.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                all_commands.append(h.get("command", ""))

    assert any("route-hint" in cmd for cmd in all_commands), (
        f"route-hint hook not found in commands: {all_commands}"
    )


def test_route_hint_hook_does_not_replace_existing_hooks(run_configure, fake_home):
    """Installing the route-hint hook must not replace existing hooks."""
    result = run_configure()
    assert result.returncode == 0, result.stderr

    settings = _read_settings(fake_home)
    hooks = settings.get("hooks", {})

    # Count total hook entries — must be more than the original 2.
    total_entries = 0
    for event_type, entries in hooks.items():
        total_entries += len(entries)
    assert total_entries > 2, f"existing hooks were replaced; total entries: {total_entries}"


# ---------------------------------------------------------------------------
# Policy document exists and has markers
# ---------------------------------------------------------------------------


def test_policy_document_exists():
    """The orchestrator-policy.md document must exist."""
    assert POLICY_DOC.exists()


def test_policy_document_has_markers():
    """The policy document must contain the marker fences for CLAUDE.md insertion."""
    content = POLICY_DOC.read_text()
    assert BEGIN_MARKER in content
    assert END_MARKER in content


def test_policy_document_has_taxonomy():
    """The policy document must contain the PRD taxonomy (OAuth vs MaaS)."""
    content = POLICY_DOC.read_text().lower()
    # OAuth (stay) signals.
    assert "image" in content or "vision" in content
    assert "security" in content or "auth" in content
    assert "architecture" in content or "cross-service" in content
    # MaaS (delegate) signals.
    assert "unit test" in content or "code gen" in content or "documentation" in content
    # Escalation.
    assert "escalat" in content


# ---------------------------------------------------------------------------
# No ANTHROPIC_* in the policy doc or scripts
# ---------------------------------------------------------------------------


def test_policy_doc_does_not_contain_anthropic_env_instructions():
    """The policy document must not instruct setting ANTHROPIC_* env vars in OAuth session."""
    content = POLICY_DOC.read_text()
    # The policy should not contain instructions to export ANTHROPIC_* in the
    # OAuth session context. We allow mentioning the variable names in
    # prohibition lists, but not as instructions.
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        # Skip prohibition/invariant lines that mention ANTHROPIC_ as things NOT to do.
        lower = stripped.lower()
        if "never" in lower or "must not" in lower or "do not" in lower or "prohibit" in lower:
            continue
        # In non-prohibition lines, ANTHROPIC_ should not appear as an export instruction.
        if "export ANTHROPIC" in stripped:
            pytest.fail(f"policy doc instructs exporting ANTHROPIC env: {stripped!r}")


# ---------------------------------------------------------------------------
# settings.json remains valid JSON after install
# ---------------------------------------------------------------------------


def test_settings_json_remains_valid_json(run_configure, fake_home):
    """settings.json must remain valid JSON after installation."""
    result = run_configure()
    assert result.returncode == 0, result.stderr
    # This will raise json.JSONDecodeError if invalid.
    _read_settings(fake_home)


def test_claude_md_is_not_empty(run_configure, fake_home):
    """CLAUDE.md must not be empty after installation."""
    result = run_configure()
    assert result.returncode == 0, result.stderr
    content = _read_claude_md(fake_home)
    assert len(content.strip()) > 0


def test_preserves_user_anthropic_api_key(tmp_path):
    """configure-policy must NOT delete the user's existing ANTHROPIC_API_KEY.

    Regression: the old env-stripping logic deleted all ANTHROPIC_* keys,
    silently destroying the user's OAuth/API key.  The env dict must be left
    byte-for-byte untouched.
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text("# existing\n")
    settings = {
        "env": {
            "ANTHROPIC_API_KEY": "sk-ant-user-key-must-survive",
            "SOME_USER_VAR": "user-value",
        },
        "hooks": {},
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    env = _strip_anthropic_env(dict(os.environ))
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        [str(CONFIGURE_POLICY)], capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr

    after = json.loads((claude_dir / "settings.json").read_text())
    assert after["env"]["ANTHROPIC_API_KEY"] == "sk-ant-user-key-must-survive"
    assert after["env"]["SOME_USER_VAR"] == "user-value"
