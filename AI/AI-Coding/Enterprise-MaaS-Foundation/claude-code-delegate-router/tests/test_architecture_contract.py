import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED = ("litellm", "claude-code-router", "openrouter", "premium-openrouter")

# Patterns that indicate a *runtime* dependency, not a comment naming the
# legacy system a migration tool removes.
RUNTIME_PATTERNS = [
    re.compile(r"import\s+litellm"),
    re.compile(r"from\s+litellm\s+import"),
    re.compile(r"pip\s+install\s+litellm"),
    re.compile(r"pip3\s+install\s+litellm"),
    re.compile(r"\blitellm\s+--"),
    re.compile(r"\blitellm\s+run\b"),
    re.compile(r"npm\s+install\s+claude-code-router"),
    re.compile(r"npm\s+install\s+@musistudio/claude-code-router"),
    re.compile(r"\bccr\b\s+--"),
    re.compile(r"\bccr\b\s+start\b"),
    re.compile(r"pip\s+install\s+openrouter"),
    re.compile(r"import\s+openrouter"),
    re.compile(r"from\s+openrouter\s+import"),
]


def _strip_comments(text: str) -> str:
    """Remove shell/python comment lines and heredoc bodies."""
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


def test_runtime_files_do_not_depend_on_removed_gateways():
    runtime = [
        *ROOT.glob("client/*"),
        *ROOT.glob("scripts/*"),
        *ROOT.glob("adapter/*"),
    ]
    offenders = []
    for path in runtime:
        if not path.is_file() or path.name == "check-prohibited-dependencies.py":
            continue
        raw = path.read_text(errors="ignore")
        for pat in RUNTIME_PATTERNS:
            if pat.search(raw.lower()):
                offenders.append((str(path.relative_to(ROOT)), pat.pattern))
        code = _strip_comments(raw).lower()
        for word in PROHIBITED:
            if word in code:
                offenders.append((str(path.relative_to(ROOT)), word))
    assert offenders == []


def test_scanner_script_agrees_with_contract_test():
    """The standalone scanner must find the same offenders as the contract test."""
    import subprocess
    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "check-prohibited-dependencies.py")],
        capture_output=True, text=True,
    )
    # Both should agree on zero offenders for a clean repo.
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# Documentation gate (Task 10): README must cover required topics and all
# referenced local paths must exist.
# ---------------------------------------------------------------------------

README_REQUIRED_TOPICS = [
    "bootstrap",
    "OAuth",
    "MaaS-only",
    "image limitation",
    "No Sidecar",
    "Key rotation",
    "Uninstall",
    "verify-offline",
    "verify-live",
]


def test_readme_covers_required_topics():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [t for t in README_REQUIRED_TOPICS if t.lower() not in readme.lower()]
    assert missing == [], f"README missing topics: {missing}"


def test_readme_referenced_local_paths_exist():
    """Backtick-quoted local paths in README must resolve on disk."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Match `path/to/file` style references that look like local paths.
    refs = re.findall(r"`([a-zA-Z0-9_./-]+/[a-zA-Z0-9_./-]+)`", readme)
    missing = []
    for ref in refs:
        # Skip URLs and non-path references.
        if ref.startswith("http") or ref.startswith("$"):
            continue
        # Strip trailing slashes and check existence relative to ROOT.
        candidate = ROOT / ref
        if not candidate.exists():
            missing.append(ref)
    assert missing == [], f"README references missing paths: {missing}"


def test_required_docs_exist():
    for doc in ("docs/PRD.md", "docs/OPERATIONS.md", "docs/SECURITY.md"):
        assert (ROOT / doc).is_file(), f"missing required doc: {doc}"


def test_makefile_has_required_targets():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("test:", "verify-offline:", "verify-live:"):
        assert target in makefile, f"Makefile missing target: {target}"


# ---------------------------------------------------------------------------
# G-WAIT8: stream reliability architecture invariants
# ---------------------------------------------------------------------------


def test_stream_reliability_module_exists():
    """The reliability deep module must be in version control (PRD DoD 1)."""
    assert (ROOT / "client" / "stream_reliability.py").is_file()


def test_stream_reliability_uses_stdlib_only():
    """The module must import only stdlib — no external deps (PRD §1)."""
    content = (ROOT / "client" / "stream_reliability.py").read_text()
    # No third-party imports.
    for forbidden in ("import litellm", "import openai", "import anthropic",
                      "import requests", "import aiohttp", "import httpx"):
        assert forbidden not in content, f"forbidden import: {forbidden}"


def test_stream_reliability_introduces_no_new_gateway():
    """No new HTTP listener/router/sidecar in the module (G-WAIT8)."""
    content = (ROOT / "client" / "stream_reliability.py").read_text().lower()
    for forbidden in ("litellm", "claude-code-router", "openrouter", "sidecar",
                      "fallback", "0.0.0.0", "listen", "bind"):
        assert forbidden not in content, f"gateway pattern in module: {forbidden}"


def test_stream_reliability_tests_exist():
    """Unit + integration tests must be auto-discovered (PRD DoD 2)."""
    assert (ROOT / "tests" / "test_stream_reliability.py").is_file()
    assert (ROOT / "tests" / "test_stream_reliability_integration.py").is_file()


# ---------------------------------------------------------------------------
# G-CLOSE9: loopback-only adapter architecture invariants
# ---------------------------------------------------------------------------


def test_adapter_source_exists():
    """The production adapter source must be in version control."""
    assert (ROOT / "adapter" / "server.js").is_file(), "adapter/server.js missing"


def test_adapter_lifecycle_exists():
    """The RequestLifecycleController must be in version control."""
    assert (ROOT / "adapter" / "lifecycle.js").is_file(), "adapter/lifecycle.js missing"


def test_adapter_binds_loopback_only():
    """The adapter must default to 127.0.0.1 and refuse non-loopback binds."""
    src = (ROOT / "adapter" / "server.js").read_text(encoding="utf-8")
    assert "127.0.0.1" in src, "adapter missing loopback default"
    assert "refusing non-loopback bind" in src, "adapter missing loopback validation"
    # Must not bind to wildcard.
    assert '"0.0.0.0"' not in src, "adapter binds to wildcard 0.0.0.0"


def test_adapter_has_no_gateway_imports():
    """The adapter must not import litellm/CCR/openrouter or use fallback."""
    raw = (ROOT / "adapter" / "server.js").read_text(encoding="utf-8")
    # Check runtime dependency patterns against full text.
    for pat in RUNTIME_PATTERNS:
        assert not pat.search(raw.lower()), f"adapter runtime dependency: {pat.pattern}"
    # Strip JS // comments and /* */ blocks, then check bare mentions.
    code = re.sub(r"//.*", "", raw)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = code.lower()
    for forbidden in ("litellm", "claude-code-router", "openrouter", "fallback"):
        assert forbidden not in code, f"adapter has gateway pattern in code: {forbidden}"


def test_adapter_has_status_endpoint():
    """The adapter must expose a sanitized /status endpoint (G-CLOSE7)."""
    src = (ROOT / "adapter" / "server.js").read_text(encoding="utf-8")
    assert "/status" in src, "adapter missing /status endpoint"


def test_adapter_has_concurrency_guard():
    """The adapter must enforce a concurrency guard (G-CLOSE8)."""
    src = (ROOT / "adapter" / "server.js").read_text(encoding="utf-8")
    assert "ConcurrencyGuard" in src, "adapter missing concurrency guard"
    assert "MAX_CONCURRENCY" in src, "adapter missing concurrency config"


def test_stream_reliability_py_marked_test_only():
    """The Python prototype must be marked test-only/non-authoritative."""
    src = (ROOT / "client" / "stream_reliability.py").read_text(encoding="utf-8")
    assert "TEST-ONLY" in src or "NON-AUTHORITATIVE" in src, \
        "stream_reliability.py not marked as test-only"