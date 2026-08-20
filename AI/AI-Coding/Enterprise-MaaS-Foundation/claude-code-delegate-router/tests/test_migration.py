"""Tests for scripts/migrate.sh — migration from claude-glm/LiteLLM legacy.

These tests verify the PRD section 13.2 contract:

  * --dry-run is byte-for-byte side-effect free (snapshot before == after).
  * --apply removes ONLY values matching the ownership manifest (old claude-glm
    wrapper, old policy marker, owned hook entry, LiteLLM base URL/virtual key/
    model mapping) — only when endpoint + key fingerprint + marker ownership match.
  * OAuth metadata (token, Anthropic API key) remains byte-identical after apply.
  * User's custom hooks, MCP, theme, preferences remain byte-identical after apply.
  * Repeated apply is a no-op (idempotent).
  * Migrate never stops or modifies a remote LiteLLM deployment (only local config).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "scripts" / "migrate.sh"

BEGIN_MARKER = "<!-- BEGIN claude-maas-policy -->"
END_MARKER = "<!-- END claude-maas-policy -->"

# A known LiteLLM base URL and virtual key fingerprint used in legacy config.
LEGACY_LITELLM_BASE_URL = "http://localhost:4000/anthropic"
LEGACY_VIRTUAL_KEY = "sk-litellm-virtual-abc123"
LEGACY_MODEL_MAPPING = {"claude-sonnet-4-5": "glm-5.2", "claude-opus-4": "glm-5.2"}
# The recorded endpoint + key fingerprint that proves ownership.
OWNED_ENDPOINT = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
OWNED_KEY_FINGERPRINT = "fp:maas:deadbeef"


# ---------------------------------------------------------------------------
# Environment helper
# ---------------------------------------------------------------------------


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of env with all ANTHROPIC_* keys removed."""
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


# ---------------------------------------------------------------------------
# Fixture: a fake HOME with mixed user + legacy settings
# ---------------------------------------------------------------------------


@pytest.fixture()
def legacy_home(tmp_path: Path):
    """Create a fake HOME with a mix of user content and legacy claude-glm/LiteLLM data.

    Legacy / owned items (should be removed by --apply):
      * old claude-glm wrapper symlink in ~/.local/bin
      * old policy marker block in ~/.claude/CLAUDE.md
      * owned route-hint hook entry in ~/.claude/settings.json
      * LiteLLM base URL, virtual key, model mapping in ~/.claude/settings.json env
      * an ownership manifest in ~/.claude-maas/manifest.json recording endpoint+fingerprint

    User items (must be preserved byte-identical):
      * custom hooks (PreToolUse, PostToolUse) in settings.json
      * MCP servers in settings.json
      * theme and preferences in settings.json
      * OAuth token in ~/.claude/credentials.json
      * Anthropic API key in ~/.claude/settings.json env (ANTHROPIC_API_KEY)
    """
    home = tmp_path

    # --- ~/.claude/CLAUDE.md: user content + old policy marker block ---
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    claude_md = claude_dir / "CLAUDE.md"
    claude_md.write_text(
        "# My Project\n"
        "\n"
        "Custom user content that must survive migration.\n"
        "\n"
        f"{BEGIN_MARKER}\n"
        "## Old claude-maas policy (legacy)\n"
        "Delegate coding tasks to MaaS.\n"
        f"{END_MARKER}\n"
        "\n"
        "## More user content\n"
        "Do not delete this.\n"
    )

    # --- ~/.claude/settings.json: user + legacy + owned ---
    settings = {
        "permissions": {"allow": ["Bash(ls:*)", "Bash(git:*)"]},
        "theme": "dark",
        "preferences": {"verbose": True, "language": "python"},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "echo user-pre-bash"}],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Read",
                    "hooks": [{"type": "command", "command": "echo user-post-read"}],
                }
            ],
            "UserPromptSubmit": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"bash {ROOT}/scripts/route-hint.sh",
                        }
                    ],
                }
            ],
        },
        "mcpServers": {
            "user-mcp": {"command": "node", "args": ["/home/user/mcp/server.js"]},
        },
        "env": {
            "SOME_USER_VAR": "user-value",
            "ANTHROPIC_API_KEY": "sk-ant-oauth-user-key-keep-me",
            # Legacy LiteLLM values (owned, should be removed on apply).
            "ANTHROPIC_BASE_URL": LEGACY_LITELLM_BASE_URL,
            "LITELLM_VIRTUAL_KEY": LEGACY_VIRTUAL_KEY,
            "LITELLM_MODEL_MAPPING": json.dumps(LEGACY_MODEL_MAPPING),
        },
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # --- ~/.claude/credentials.json: OAuth token (must be preserved) ---
    credentials = {
        "claudeAiOauth": {
            "accessToken": "oauth-access-token-do-not-delete",
            "refreshToken": "oauth-refresh-token-do-not-delete",
            "expiresAt": "2026-12-31T23:59:59Z",
        }
    }
    (claude_dir / "credentials.json").write_text(json.dumps(credentials, indent=2))

    # --- ~/.local/bin: old claude-glm wrapper symlink (legacy, owned) ---
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)
    # Create a fake old wrapper target so the symlink is valid.
    old_wrapper_target = home / ".local" / "share" / "claude-glm" / "claude-glm"
    old_wrapper_target.parent.mkdir(parents=True)
    old_wrapper_target.write_text("#!/usr/bin/env bash\n# old claude-glm wrapper\n")
    old_wrapper_target.chmod(0o755)
    claude_glm_link = local_bin / "claude-glm"
    claude_glm_link.symlink_to(old_wrapper_target)

    # A user-installed binary that must survive.
    user_tool = local_bin / "my-tool"
    user_tool.write_text("#!/usr/bin/env bash\necho user tool\n")
    user_tool.chmod(0o755)

    # --- ~/.claude-maas/manifest.json: ownership manifest ---
    # Records the endpoint + key fingerprint + marker ownership that proves
    # which legacy values belong to this project and are safe to remove.
    claude_maas_dir = home / ".claude-maas"
    claude_maas_dir.mkdir(parents=True)
    manifest = {
        "version": 1,
        "endpoint": OWNED_ENDPOINT,
        "key_fingerprint": OWNED_KEY_FINGERPRINT,
        "markers": [BEGIN_MARKER, END_MARKER],
        "owned_hook_command": "route-hint.sh",
        "owned_wrapper": "claude-glm",
        "owned_env_keys": [
            "ANTHROPIC_BASE_URL",
            "LITELLM_VIRTUAL_KEY",
            "LITELLM_MODEL_MAPPING",
        ],
        "launchers": [],
        "local_bin": str(local_bin),
    }
    (claude_maas_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # --- A fake "remote LiteLLM" marker file to prove migrate doesn't touch it ---
    remote_litellm = home / "remote-litellm-deployment.flag"
    remote_litellm.write_text("remote litellm deployment state\n")

    return home


# ---------------------------------------------------------------------------
# Fixture: run_migrate
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_migrate(legacy_home: Path):
    """Return a callable that runs migrate.sh with HOME=legacy_home."""
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(legacy_home)

    def _run(*args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(MIGRATE), *args],
            env=base_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result

    return _run


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    """Snapshot all regular files + symlink targets under root as {relpath: content}.

    For symlinks, the content is the link target path (readlink), prefixed.
    """
    snap: dict[str, bytes] = {}
    if not root.exists():
        return snap
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            rel = str(path.relative_to(root))
            target = os.readlink(path)
            snap[rel] = f"__SYMLINK__:{target}".encode()
        elif path.is_file():
            rel = str(path.relative_to(root))
            snap[rel] = path.read_bytes()
    return snap


def _snapshot_home(home: Path) -> dict[str, bytes]:
    """Snapshot the entire fake HOME tree (files, dirs, symlinks)."""
    return _snapshot_tree(home)


# ---------------------------------------------------------------------------
# --dry-run is byte-for-byte side-effect free
# ---------------------------------------------------------------------------


def test_dry_run_is_side_effect_free(run_migrate, legacy_home):
    """--dry-run must not modify any file under HOME."""
    before = _snapshot_home(legacy_home)
    result = run_migrate("--dry-run")
    assert result.returncode == 0, result.stderr
    after = _snapshot_home(legacy_home)
    changed = {k for k in before.keys() & after.keys() if before[k] != after[k]}
    assert before == after, (
        "--dry-run modified the filesystem:\n"
        f"new keys: {set(after) - set(before)}\n"
        f"removed keys: {set(before) - set(after)}\n"
        f"changed keys: {changed}\n"
    )


def test_dry_run_exits_zero(run_migrate):
    """--dry-run must exit 0."""
    result = run_migrate("--dry-run")
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# --apply removes ONLY owned legacy values
# ---------------------------------------------------------------------------


def test_apply_removes_old_policy_marker(run_migrate, legacy_home):
    """--apply must remove the old policy marker block from CLAUDE.md."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    content = (legacy_home / ".claude" / "CLAUDE.md").read_text()
    assert BEGIN_MARKER not in content
    assert END_MARKER not in content


def test_apply_preserves_user_claude_md_content(run_migrate, legacy_home):
    """--apply must preserve all non-marker user content in CLAUDE.md."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    content = (legacy_home / ".claude" / "CLAUDE.md").read_text()
    assert "# My Project" in content
    assert "Custom user content that must survive migration." in content
    assert "## More user content" in content
    assert "Do not delete this." in content


def test_apply_removes_owned_hook_entry(run_migrate, legacy_home):
    """--apply must remove the owned route-hint hook entry from settings.json."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    hooks = settings.get("hooks", {})
    user_submit = hooks.get("UserPromptSubmit", [])
    for entry in user_submit:
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            assert "route-hint" not in cmd, f"owned hook not removed: {cmd}"


def test_apply_removes_litellm_base_url(run_migrate, legacy_home):
    """--apply must remove the LiteLLM ANTHROPIC_BASE_URL from settings.json env."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    env = settings.get("env", {})
    assert "ANTHROPIC_BASE_URL" not in env, "LiteLLM base URL not removed"


def test_apply_removes_litellm_virtual_key(run_migrate, legacy_home):
    """--apply must remove LITELLM_VIRTUAL_KEY from settings.json env."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    env = settings.get("env", {})
    assert "LITELLM_VIRTUAL_KEY" not in env


def test_apply_removes_litellm_model_mapping(run_migrate, legacy_home):
    """--apply must remove LITELLM_MODEL_MAPPING from settings.json env."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    env = settings.get("env", {})
    assert "LITELLM_MODEL_MAPPING" not in env


def test_apply_removes_old_claude_glm_wrapper(run_migrate, legacy_home):
    """--apply must remove the old claude-glm wrapper symlink from ~/.local/bin."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    wrapper = legacy_home / ".local" / "bin" / "claude-glm"
    assert not wrapper.exists(), "old claude-glm wrapper not removed"


# ---------------------------------------------------------------------------
# OAuth metadata and Anthropic API key remain byte-identical
# ---------------------------------------------------------------------------


def test_apply_preserves_oauth_token(run_migrate, legacy_home):
    """--apply must leave the OAuth token byte-identical."""
    creds_path = legacy_home / ".claude" / "credentials.json"
    before = creds_path.read_bytes()
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    after = creds_path.read_bytes()
    assert before == after, "OAuth credentials were modified"


def test_apply_preserves_anthropic_api_key(run_migrate, legacy_home):
    """--apply must leave ANTHROPIC_API_KEY in settings.json env byte-identical."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    env = settings.get("env", {})
    assert env.get("ANTHROPIC_API_KEY") == "sk-ant-oauth-user-key-keep-me"


# ---------------------------------------------------------------------------
# User's custom hooks, MCP, theme, preferences remain byte-identical
# ---------------------------------------------------------------------------


def test_apply_preserves_user_hooks(run_migrate, legacy_home):
    """--apply must preserve user's custom hooks."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    hooks = settings.get("hooks", {})

    pre_cmds = []
    for entry in hooks.get("PreToolUse", []):
        for h in entry.get("hooks", []):
            pre_cmds.append(h.get("command", ""))
    assert "echo user-pre-bash" in pre_cmds

    post_cmds = []
    for entry in hooks.get("PostToolUse", []):
        for h in entry.get("hooks", []):
            post_cmds.append(h.get("command", ""))
    assert "echo user-post-read" in post_cmds


def test_apply_preserves_mcp_servers(run_migrate, legacy_home):
    """--apply must preserve user's MCP servers."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    mcp = settings.get("mcpServers", {})
    assert "user-mcp" in mcp
    assert mcp["user-mcp"]["command"] == "node"


def test_apply_preserves_theme(run_migrate, legacy_home):
    """--apply must preserve the user's theme."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    assert settings.get("theme") == "dark"


def test_apply_preserves_preferences(run_migrate, legacy_home):
    """--apply must preserve the user's preferences."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    prefs = settings.get("preferences", {})
    assert prefs.get("verbose") is True
    assert prefs.get("language") == "python"


def test_apply_preserves_user_env_vars(run_migrate, legacy_home):
    """--apply must preserve non-legacy user env vars."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings = json.loads((legacy_home / ".claude" / "settings.json").read_text())
    env = settings.get("env", {})
    assert env.get("SOME_USER_VAR") == "user-value"


def test_apply_preserves_user_local_bin_tool(run_migrate, legacy_home):
    """--apply must not remove user-installed tools from ~/.local/bin."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    user_tool = legacy_home / ".local" / "bin" / "my-tool"
    assert user_tool.exists()
    assert user_tool.read_text() == "#!/usr/bin/env bash\necho user tool\n"


# ---------------------------------------------------------------------------
# Idempotency: repeated apply is a no-op
# ---------------------------------------------------------------------------


def test_apply_is_idempotent(run_migrate, legacy_home):
    """Running --apply twice must produce identical results."""
    r1 = run_migrate("--apply")
    assert r1.returncode == 0, r1.stderr
    snapshot1 = _snapshot_home(legacy_home)

    r2 = run_migrate("--apply")
    assert r2.returncode == 0, r2.stderr
    snapshot2 = _snapshot_home(legacy_home)

    changed = {k for k in snapshot1.keys() & snapshot2.keys() if snapshot1[k] != snapshot2[k]}
    assert snapshot1 == snapshot2, (
        "second --apply changed the filesystem:\n"
        f"new keys: {set(snapshot2) - set(snapshot1)}\n"
        f"removed keys: {set(snapshot1) - set(snapshot2)}\n"
        f"changed keys: {changed}\n"
    )


# ---------------------------------------------------------------------------
# Migrate never stops or modifies a remote LiteLLM deployment
# ---------------------------------------------------------------------------


def test_apply_does_not_touch_remote_litellm(run_migrate, legacy_home):
    """--apply must not modify any remote LiteLLM deployment marker."""
    remote = legacy_home / "remote-litellm-deployment.flag"
    before = remote.read_bytes()
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    after = remote.read_bytes()
    assert before == after, "remote LiteLLM deployment was modified"


def test_dry_run_does_not_touch_remote_litellm(run_migrate, legacy_home):
    """--dry-run must not modify any remote LiteLLM deployment marker."""
    remote = legacy_home / "remote-litellm-deployment.flag"
    before = remote.read_bytes()
    result = run_migrate("--dry-run")
    assert result.returncode == 0, result.stderr
    after = remote.read_bytes()
    assert before == after


# ---------------------------------------------------------------------------
# Requires --dry-run or --apply (never infers apply)
# ---------------------------------------------------------------------------


def test_no_mode_arg_fails(run_migrate):
    """Running with no mode argument must fail, not implicitly apply."""
    result = run_migrate()
    assert result.returncode != 0, "migrate without --dry-run/--apply should fail"


def test_apply_creates_backup(run_migrate, legacy_home):
    """--apply must create a backup before modifying files."""
    result = run_migrate("--apply")
    assert result.returncode == 0, result.stderr
    settings_bak = legacy_home / ".claude" / "settings.json.bak"
    claude_md_bak = legacy_home / ".claude" / "CLAUDE.md.bak"
    assert settings_bak.exists(), "settings.json.bak not created"
    assert claude_md_bak.exists(), "CLAUDE.md.bak not created"


# ---------------------------------------------------------------------------
# Ownership proof: does not remove values that don't match manifest
# ---------------------------------------------------------------------------


def test_apply_does_not_remove_unowned_base_url(tmp_path: Path):
    """--apply must NOT remove ANTHROPIC_BASE_URL if the manifest doesn't claim it."""
    home = tmp_path
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text("# user content\n")

    # settings with a base URL but NO matching ownership manifest
    settings = {
        "env": {
            "ANTHROPIC_BASE_URL": "http://some-other-litellm:4000/anthropic",
            "ANTHROPIC_API_KEY": "sk-keep-me",
        },
        "hooks": {},
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # manifest that does NOT list ANTHROPIC_BASE_URL as owned
    claude_maas_dir = home / ".claude-maas"
    claude_maas_dir.mkdir(parents=True)
    manifest = {
        "version": 1,
        "endpoint": OWNED_ENDPOINT,
        "key_fingerprint": OWNED_KEY_FINGERPRINT,
        "markers": [BEGIN_MARKER, END_MARKER],
        "owned_hook_command": "route-hint.sh",
        "owned_wrapper": "claude-glm",
        "owned_env_keys": [],  # does NOT include ANTHROPIC_BASE_URL
        "launchers": [],
        "local_bin": str(home / ".local" / "bin"),
    }
    (claude_maas_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(MIGRATE), "--apply"],
        env=base_env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr

    after = json.loads((claude_dir / "settings.json").read_text())
    env = after.get("env", {})
    # The unowned base URL must remain.
    assert env.get("ANTHROPIC_BASE_URL") == "http://some-other-litellm:4000/anthropic"
    assert env.get("ANTHROPIC_API_KEY") == "sk-keep-me"


def test_apply_without_manifest_preserves_everything(tmp_path: Path):
    """If no ownership manifest exists, --apply must not remove legacy values."""
    home = tmp_path
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text(
        f"# user\n\n{BEGIN_MARKER}\nlegacy\n{END_MARKER}\n"
    )
    settings = {
        "env": {"ANTHROPIC_BASE_URL": LEGACY_LITELLM_BASE_URL},
        "hooks": {},
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))
    # NO ~/.claude-maas/manifest.json

    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(MIGRATE), "--apply"],
        env=base_env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr

    # Without a manifest, nothing should be removed (no ownership proof).
    content = (claude_dir / "CLAUDE.md").read_text()
    assert BEGIN_MARKER in content, "marker removed without ownership manifest"
    after = json.loads((claude_dir / "settings.json").read_text())
    assert after.get("env", {}).get("ANTHROPIC_BASE_URL") == LEGACY_LITELLM_BASE_URL
