"""Tests for scripts/uninstall.sh — precise uninstall with safety guarantees.

These tests verify the PRD section 13.3 contract:

  * Default uninstall removes only: project marker block, owned hook entry,
    agents/skills, wrapper, symlinks.
  * Default uninstall RETAINS ~/.claude-maas, Key, and audit data (and tells
    the user their location).
  * --purge (explicit only) removes ~/.claude-maas and audit.
  * Repeated uninstall is a no-op.
  * Uninstall without --purge never deletes the key file.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNINSTALL = ROOT / "scripts" / "uninstall.sh"

BEGIN_MARKER = "<!-- BEGIN claude-maas-policy -->"
END_MARKER = "<!-- END claude-maas-policy -->"

OWNED_ENDPOINT = "https://api-ap-southeast-1.modelarts-maas.com/anthropic"
OWNED_KEY_FINGERPRINT = "fp:maas:deadbeef"


# ---------------------------------------------------------------------------
# Environment helper
# ---------------------------------------------------------------------------


def _strip_anthropic_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not k.startswith("ANTHROPIC_")}


# ---------------------------------------------------------------------------
# Fixture: an installed project state
# ---------------------------------------------------------------------------


@pytest.fixture()
def installed_home(tmp_path: Path):
    """Create a fake HOME with a fully installed claude-maas project state.

    Items that should be removed by default uninstall:
      * project marker block in ~/.claude/CLAUDE.md
      * owned route-hint hook entry in ~/.claude/settings.json
      * agents/skills files under ~/.claude/agents/ and ~/.claude/skills/
      * wrapper symlink in ~/.local/bin/claude-maas
      * other project symlinks (claude-select, delegate, workflow)

    Items that must be RETAINED by default uninstall:
      * ~/.claude-maas/ directory and all contents (api-key, config.json, manifest.json)
      * audit data in ~/.claude-hybrid/audit/
      * user's own hooks, MCP, theme, preferences, OAuth token
    """
    home = tmp_path

    # --- ~/.claude/CLAUDE.md with project marker block + user content ---
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text(
        "# My Project\n"
        "\n"
        "User content to preserve.\n"
        "\n"
        f"{BEGIN_MARKER}\n"
        "## claude-maas policy\n"
        "Delegate to MaaS.\n"
        f"{END_MARKER}\n"
        "\n"
        "## More user content\n"
    )

    # --- ~/.claude/settings.json with owned hook + user content ---
    settings = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "theme": "dark",
        "preferences": {"verbose": True},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "echo user-pre-bash"}],
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
        "env": {"SOME_USER_VAR": "user-value"},
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # --- OAuth credentials (must be preserved) ---
    (claude_dir / "credentials.json").write_text(
        json.dumps(
            {"claudeAiOauth": {"accessToken": "oauth-keep-me"}},
            indent=2,
        )
    )

    # --- agents/skills (should be removed by default uninstall) ---
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "maas-delegate.md").write_text("# MaaS delegate agent\n")
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "maas-route.md").write_text("# MaaS route skill\n")

    # User's own agent that must survive.
    (agents_dir / "my-personal-agent.md").write_text("# My personal agent\n")

    # --- ~/.local/bin: project wrapper symlinks + user tool ---
    local_bin = home / ".local" / "bin"
    local_bin.mkdir(parents=True)

    # Project wrapper sources.
    for name, src in [
        ("claude-maas", ROOT / "client" / "claude-maas"),
        ("claude-select", ROOT / "client" / "claude-select"),
        ("delegate", ROOT / "scripts" / "delegate"),
        ("workflow", ROOT / "scripts" / "workflow"),
    ]:
        link = local_bin / name
        if src.exists():
            link.symlink_to(src)
        else:
            # Create a placeholder so the symlink exists for uninstall to remove.
            link.write_text(f"#!/usr/bin/env bash\n# {name}\n")
            link.chmod(0o755)

    # User's own tool that must survive.
    user_tool = local_bin / "my-tool"
    user_tool.write_text("#!/usr/bin/env bash\necho user tool\n")
    user_tool.chmod(0o755)

    # --- ~/.claude-maas/: config, key, manifest (RETAINED by default) ---
    claude_maas_dir = home / ".claude-maas"
    claude_maas_dir.mkdir(parents=True)
    (claude_maas_dir / "api-key").write_text("test-secret-key\n")
    (claude_maas_dir / "api-key").chmod(0o600)
    (claude_maas_dir / "config.json").write_text(
        json.dumps(
            {
                "anthropic_base_url": OWNED_ENDPOINT,
                "model": "glm-5.2",
                "context_tokens": 190000,
                "max_output_tokens": 32768,
            },
            indent=2,
        )
    )
    (claude_maas_dir / "config.json").chmod(0o600)
    manifest = {
        "version": 1,
        "endpoint": OWNED_ENDPOINT,
        "key_fingerprint": OWNED_KEY_FINGERPRINT,
        "markers": [BEGIN_MARKER, END_MARKER],
        "owned_hook_command": "route-hint.sh",
        "owned_wrapper": "claude-glm",
        "owned_env_keys": [],
        "launchers": [
            {"name": "claude-maas", "installed": str(local_bin / "claude-maas")},
            {"name": "claude-select", "installed": str(local_bin / "claude-select")},
            {"name": "delegate", "installed": str(local_bin / "delegate")},
            {"name": "workflow", "installed": str(local_bin / "workflow")},
        ],
        "local_bin": str(local_bin),
    }
    (claude_maas_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # --- ~/.claude-hybrid/audit/: audit data (RETAINED by default) ---
    audit_dir = home / ".claude-hybrid" / "audit"
    audit_dir.mkdir(parents=True)
    (audit_dir / "route-stats.json").write_text(
        json.dumps({"maas_attempts": 10, "successes": 9}, indent=2)
    )
    (audit_dir / "delegate.log").write_text("audit log line\n")

    return home


# ---------------------------------------------------------------------------
# Fixture: run_uninstall
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_uninstall(installed_home: Path):
    """Return a callable that runs uninstall.sh with HOME=installed_home."""
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(installed_home)

    def _run(*args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(UNINSTALL), *args],
            env=base_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result

    return _run


# ---------------------------------------------------------------------------
# Default uninstall removes only project-owned items
# ---------------------------------------------------------------------------


def test_default_removes_project_marker(run_uninstall, installed_home):
    """Default uninstall must remove the project marker block from CLAUDE.md."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    content = (installed_home / ".claude" / "CLAUDE.md").read_text()
    assert BEGIN_MARKER not in content
    assert END_MARKER not in content


def test_default_preserves_user_claude_md_content(run_uninstall, installed_home):
    """Default uninstall must preserve user content in CLAUDE.md."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    content = (installed_home / ".claude" / "CLAUDE.md").read_text()
    assert "# My Project" in content
    assert "User content to preserve." in content
    assert "## More user content" in content


def test_default_removes_owned_hook_entry(run_uninstall, installed_home):
    """Default uninstall must remove the owned route-hint hook entry."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    settings = json.loads(
        (installed_home / ".claude" / "settings.json").read_text()
    )
    hooks = settings.get("hooks", {})
    for entry in hooks.get("UserPromptSubmit", []):
        for h in entry.get("hooks", []):
            assert "route-hint" not in h.get("command", "")


def test_default_preserves_user_hooks(run_uninstall, installed_home):
    """Default uninstall must preserve user's custom hooks."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    settings = json.loads(
        (installed_home / ".claude" / "settings.json").read_text()
    )
    hooks = settings.get("hooks", {})
    pre_cmds = []
    for entry in hooks.get("PreToolUse", []):
        for h in entry.get("hooks", []):
            pre_cmds.append(h.get("command", ""))
    assert "echo user-pre-bash" in pre_cmds


def test_default_removes_project_agents(run_uninstall, installed_home):
    """Default uninstall must remove project agent files."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    agent = installed_home / ".claude" / "agents" / "maas-delegate.md"
    assert not agent.exists(), "project agent not removed"


def test_default_removes_project_skills(run_uninstall, installed_home):
    """Default uninstall must remove project skill files."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    skill = installed_home / ".claude" / "skills" / "maas-route.md"
    assert not skill.exists(), "project skill not removed"


def test_default_preserves_user_agents(run_uninstall, installed_home):
    """Default uninstall must preserve user's own agent files."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    agent = installed_home / ".claude" / "agents" / "my-personal-agent.md"
    assert agent.exists(), "user agent was removed"
    assert agent.read_text() == "# My personal agent\n"


def test_default_removes_wrapper_symlinks(run_uninstall, installed_home):
    """Default uninstall must remove project wrapper symlinks from ~/.local/bin."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    local_bin = installed_home / ".local" / "bin"
    for name in ("claude-maas", "claude-select", "delegate", "workflow"):
        assert not (local_bin / name).exists(), f"{name} symlink not removed"


def test_default_preserves_user_local_bin_tools(run_uninstall, installed_home):
    """Default uninstall must preserve user's own tools in ~/.local/bin."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    user_tool = installed_home / ".local" / "bin" / "my-tool"
    assert user_tool.exists()
    assert user_tool.read_text() == "#!/usr/bin/env bash\necho user tool\n"


def test_default_preserves_mcp_and_theme(run_uninstall, installed_home):
    """Default uninstall must preserve MCP, theme, preferences."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    settings = json.loads(
        (installed_home / ".claude" / "settings.json").read_text()
    )
    assert settings.get("theme") == "dark"
    assert settings.get("preferences", {}).get("verbose") is True
    assert "user-mcp" in settings.get("mcpServers", {})


def test_default_preserves_oauth(run_uninstall, installed_home):
    """Default uninstall must preserve OAuth credentials."""
    creds = installed_home / ".claude" / "credentials.json"
    before = creds.read_bytes()
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    after = creds.read_bytes()
    assert before == after


# ---------------------------------------------------------------------------
# Default uninstall RETAINS ~/.claude-maas, Key, and audit data
# ---------------------------------------------------------------------------


def test_default_retains_claude_maas_dir(run_uninstall, installed_home):
    """Default uninstall must retain ~/.claude-maas/ directory."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    assert (installed_home / ".claude-maas").is_dir()


def test_default_retains_api_key(run_uninstall, installed_home):
    """Default uninstall must retain the api-key file."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    key = installed_home / ".claude-maas" / "api-key"
    assert key.exists()
    assert key.read_text() == "test-secret-key\n"


def test_default_retains_config_json(run_uninstall, installed_home):
    """Default uninstall must retain config.json."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    cfg = installed_home / ".claude-maas" / "config.json"
    assert cfg.exists()


def test_default_retains_manifest(run_uninstall, installed_home):
    """Default uninstall must retain manifest.json."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    manifest = installed_home / ".claude-maas" / "manifest.json"
    assert manifest.exists()


def test_default_retains_audit(run_uninstall, installed_home):
    """Default uninstall must retain audit data."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    audit = installed_home / ".claude-hybrid" / "audit"
    assert audit.is_dir()
    assert (audit / "route-stats.json").exists()
    assert (audit / "delegate.log").exists()


def test_default_tells_user_locations(run_uninstall, installed_home):
    """Default uninstall must tell the user the location of retained data."""
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    # Must mention the retained key/config location.
    assert ".claude-maas" in combined or "claude-maas" in combined.lower()


def test_default_never_deletes_key_file(run_uninstall, installed_home):
    """Uninstall without --purge must never delete the key file."""
    key = installed_home / ".claude-maas" / "api-key"
    assert key.exists()
    result = run_uninstall()
    assert result.returncode == 0, result.stderr
    assert key.exists(), "key file was deleted without --purge"


# ---------------------------------------------------------------------------
# --purge removes ~/.claude-maas and audit
# ---------------------------------------------------------------------------


def test_purge_removes_claude_maas_dir(run_uninstall, installed_home):
    """--purge must remove ~/.claude-maas/ directory."""
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    assert not (installed_home / ".claude-maas").exists()


def test_purge_removes_api_key(run_uninstall, installed_home):
    """--purge must remove the api-key file."""
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    assert not (installed_home / ".claude-maas" / "api-key").exists()


def test_purge_removes_audit(run_uninstall, installed_home):
    """--purge must remove audit data."""
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    assert not (installed_home / ".claude-hybrid" / "audit").exists()


def test_purge_still_removes_project_items(run_uninstall, installed_home):
    """--purge must also remove all the default uninstall items."""
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    content = (installed_home / ".claude" / "CLAUDE.md").read_text()
    assert BEGIN_MARKER not in content
    assert not (installed_home / ".local" / "bin" / "claude-maas").exists()


def test_purge_preserves_user_content(run_uninstall, installed_home):
    """--purge must still preserve user content."""
    result = run_uninstall("--purge")
    assert result.returncode == 0, result.stderr
    content = (installed_home / ".claude" / "CLAUDE.md").read_text()
    assert "User content to preserve." in content
    settings = json.loads(
        (installed_home / ".claude" / "settings.json").read_text()
    )
    assert settings.get("theme") == "dark"
    assert "user-mcp" in settings.get("mcpServers", {})


# ---------------------------------------------------------------------------
# Idempotency: repeated uninstall is a no-op
# ---------------------------------------------------------------------------


def test_default_is_idempotent(run_uninstall, installed_home):
    """Running default uninstall twice must be a no-op (exit 0 both times)."""
    r1 = run_uninstall()
    assert r1.returncode == 0, r1.stderr
    r2 = run_uninstall()
    assert r2.returncode == 0, r2.stderr


def test_purge_is_idempotent(run_uninstall, installed_home):
    """Running --purge twice must be a no-op (exit 0 both times)."""
    r1 = run_uninstall("--purge")
    assert r1.returncode == 0, r1.stderr
    r2 = run_uninstall("--purge")
    assert r2.returncode == 0, r2.stderr


def test_default_then_purge_is_idempotent(run_uninstall, installed_home):
    """Default then --purge then --purge must all exit 0."""
    assert run_uninstall().returncode == 0
    assert run_uninstall("--purge").returncode == 0
    assert run_uninstall("--purge").returncode == 0


# ---------------------------------------------------------------------------
# Uninstall on a clean (never-installed) HOME is a no-op
# ---------------------------------------------------------------------------


def test_uninstall_clean_home_exits_zero(tmp_path: Path):
    """Uninstall on a HOME with nothing installed must exit 0 (idempotent)."""
    home = tmp_path
    base_env = _strip_anthropic_env(dict(os.environ))
    base_env["HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(UNINSTALL)],
        env=base_env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
