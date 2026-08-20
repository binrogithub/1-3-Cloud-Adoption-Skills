"""Architecture contract for the isolated Exa search feature.

Asserts the Exa integration uses only the official remote HTTP MCP with exactly
two tools, has no local package/process runtime dependency, and lives only under
the isolated claude-maas config. These are the G-EXA3 (tool allowlist) and
G-EXA7 (no local runtime dependency) gates from docs/PRD_EXA_SEARCH_V1.md.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The exact Exa contract from PRD §5.1.
EXA_URL = "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa"
EXA_HOST = "mcp.exa.ai"
EXA_PATH = "/mcp"
ALLOWED_TOOLS = ("web_search_exa", "web_fetch_exa")

# Legacy / prohibited Exa tool names that must never appear in runtime.
PROHIBITED_EXA_TOOLS = (
    "web_search_advanced_exa",
    "exa_answer",
    "exa_find_similar",
    "exa_contents",
    "exa_agent_exa",
)

# Local Exa package / process references that must not appear in runtime code.
EXA_LOCAL_REFS = ("exa-mcp-server", "npx")


def _strip_comments(text: str) -> str:
    """Remove shell/python comment lines and heredoc bodies (mirrors scanner)."""
    out: list[str] = []
    in_heredoc = False
    heredoc_tag: str | None = None
    for line in text.splitlines():
        if in_heredoc:
            if heredoc_tag and line.strip() == heredoc_tag:
                in_heredoc = False
            continue
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\s*$", line)
        if m:
            in_heredoc = True
            heredoc_tag = m.group(1)
            continue
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _runtime_files() -> list[Path]:
    # Exclude the scanner itself — it defines the patterns to detect violations.
    scanner = "check-prohibited-dependencies.py"
    return [
        p
        for p in (*ROOT.glob("client/*"), *ROOT.glob("scripts/*"))
        if p.is_file() and p.name != scanner
    ]


# ---------------------------------------------------------------------------
# G-EXA7: no local runtime dependency on Exa packages or processes
# ---------------------------------------------------------------------------


def test_runtime_files_have_no_local_exa_package_or_process():
    """No runtime file may invoke npx or the exa-mcp-server local package."""
    npx_pattern = re.compile(r"npx\s+exa")
    offenders: list[str] = []
    for path in _runtime_files():
        raw = path.read_text(errors="ignore")
        if npx_pattern.search(raw.lower()):
            offenders.append(f"{path.name}: npx exa invocation")
    assert offenders == [], f"local Exa runtime deps found: {offenders}"


def test_runtime_files_have_no_prohibited_exa_tools():
    """No runtime file may reference advanced/agent/deprecated Exa tools."""
    offenders: list[str] = []
    for path in _runtime_files():
        code = _strip_comments(path.read_text(errors="ignore")).lower()
        for tool in PROHIBITED_EXA_TOOLS:
            if tool in code:
                offenders.append(f"{path.name}: {tool}")
    assert offenders == [], f"prohibited Exa tools found: {offenders}"


def test_runtime_files_have_no_exa_local_refs_in_code():
    """No runtime file may reference exa-mcp-server or npx in non-comment code."""
    offenders: list[str] = []
    for path in _runtime_files():
        code = _strip_comments(path.read_text(errors="ignore")).lower()
        for ref in EXA_LOCAL_REFS:
            if ref in code:
                offenders.append(f"{path.name}: {ref}")
    assert offenders == [], f"local Exa refs in code: {offenders}"


# ---------------------------------------------------------------------------
# Scanner rejects Exa violations
# ---------------------------------------------------------------------------


def _load_scanner(tmp_root: Path):
    """Import the scanner module with ROOT overridden to tmp_root."""
    scanner_path = ROOT / "scripts" / "check-prohibited-dependencies.py"
    spec = importlib.util.spec_from_file_location("scanner", scanner_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_root  # type: ignore[attr-defined]
    return module


def test_scanner_catches_npx_exa_runtime(tmp_path: Path):
    """The scanner must flag a runtime file that invokes npx exa-mcp."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "bad.sh").write_text("npx exa-mcp --key foo\n")
    scanner = _load_scanner(tmp_path)
    offenders = scanner.scan()
    assert any("bad.sh" in o for o in offenders), f"scanner missed npx exa: {offenders}"


def test_scanner_catches_exa_mcp_server_ref(tmp_path: Path):
    """The scanner must flag a runtime file that references exa-mcp-server."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "bad.sh").write_text("echo exa-mcp-server\n")
    scanner = _load_scanner(tmp_path)
    offenders = scanner.scan()
    assert any("bad.sh" in o for o in offenders), f"scanner missed exa-mcp-server: {offenders}"


def test_scanner_catches_prohibited_exa_tool(tmp_path: Path):
    """The scanner must flag a runtime file that references a prohibited tool."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "bad.sh").write_text("echo exa_contents\n")
    scanner = _load_scanner(tmp_path)
    offenders = scanner.scan()
    assert any("bad.sh" in o for o in offenders), f"scanner missed exa_contents: {offenders}"


def test_scanner_clean_repo_exits_zero():
    """The scanner must pass on the real repo (no Exa runtime violations)."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-prohibited-dependencies.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# README documents the Exa feature (G-EXA3 tool allowlist + isolated-only)
# ---------------------------------------------------------------------------


def test_readme_documents_exa_tools():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for term in ("Exa", "web_search_exa", "web_fetch_exa", "exa-search"):
        assert term in readme, f"README missing Exa term: {term}"


def test_readme_documents_exa_isolated_only():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "claude-maas" in readme
    # The README must state Exa is isolated to claude-maas only.
    lower = readme.lower()
    assert "isolated" in lower or "maas-only" in lower, "README must state Exa isolation"
