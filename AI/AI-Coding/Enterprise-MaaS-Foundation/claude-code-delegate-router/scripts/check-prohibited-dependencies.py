#!/usr/bin/env python3
"""Scan runtime files for prohibited gateway dependencies.

Inspects executable/config dependency surfaces (client/, scripts/, adapter/),
skips docs/ historical explanations and this scanner itself. Distinguishes a
true runtime dependency (an import, install, or invocation of a removed
gateway) from a migration tool's comments/help text that merely *names* the
legacy system it removes. Also verifies that adapter/server.js binds to
loopback only (G-CLOSE9). Prints one offender per line and exits 1 on a match.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED = ("litellm", "claude-code-router", "openrouter", "premium-openrouter")
SELF = Path(__file__).name

# Exa local runtime references that must not appear in runtime code (G-EXA7).
# Checked against comment-stripped code so a migration tool may name the legacy
# package it removes in comments without false-positiving.
EXA_LOCAL_REFS = ("exa-mcp-server", "npx")
# Exa tools that must never be enabled (advanced/agent/deprecated). G-EXA3.
EXA_PROHIBITED_TOOLS = (
    "web_search_advanced_exa",
    "exa_answer",
    "exa_find_similar",
    "exa_contents",
    "exa_agent_exa",
)

# Patterns that indicate a *runtime* dependency, not a comment naming the
# legacy system. Matched against the full file text (lowercased).
RUNTIME_PATTERNS = [
    re.compile(r"import\s+litellm"),
    re.compile(r"from\s+litellm\s+import"),
    re.compile(r"pip\s+install\s+litellm"),
    re.compile(r"pip3\s+install\s+litellm"),
    re.compile(r"\blitellm\s+--"),          # litellm --serve / litellm --config ...
    re.compile(r"\blitellm\s+run\b"),
    re.compile(r"npm\s+install\s+claude-code-router"),
    re.compile(r"npm\s+install\s+@musistudio/claude-code-router"),
    re.compile(r"\bccr\b\s+--"),
    re.compile(r"\bccr\b\s+start\b"),
    re.compile(r"pip\s+install\s+openrouter"),
    re.compile(r"import\s+openrouter"),
    re.compile(r"from\s+openrouter\s+import"),
    # Exa local process invocation (npx exa-mcp / npx -y exa-mcp-server).
    re.compile(r"npx\s+exa"),
]


def strip_comments(text: str) -> str:
    """Remove shell/python comment lines and heredoc bodies naively.

    We only need to avoid false positives where a migration tool names the
    legacy system it removes. Stripping lines starting with # (after optional
    whitespace) handles shell and Python comments. Heredoc-delimited help
    blocks (cat <<'USAGE' ... USAGE) are also stripped.
    """
    out: list[str] = []
    in_heredoc = False
    heredoc_tag: str | None = None
    for line in text.splitlines():
        if in_heredoc:
            if heredoc_tag and line.strip() == heredoc_tag:
                in_heredoc = False
            continue
        # Detect heredoc open: cat <<'TAG' or cat <<"TAG" or <<TAG
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\s*$", line)
        if m:
            in_heredoc = True
            heredoc_tag = m.group(1)
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def scan() -> list[str]:
    offenders: list[str] = []
    for sub in ("client", "scripts", "adapter"):
        for path in (ROOT / sub).glob("*"):
            if not path.is_file() or path.name == SELF:
                continue
            raw = path.read_text(errors="ignore")
            # 1. True runtime dependency patterns (checked against full text).
            for pat in RUNTIME_PATTERNS:
                if pat.search(raw.lower()):
                    offenders.append(
                        f"{path.relative_to(ROOT)}: runtime dependency '{pat.pattern}'"
                    )
            # 2. Bare mentions outside comments (checked against stripped text).
            code = strip_comments(raw).lower()
            for word in PROHIBITED:
                if word in code:
                    offenders.append(
                        f"{path.relative_to(ROOT)}: prohibited reference '{word}' in code"
                    )
            # 3. Exa local runtime refs and prohibited tools (G-EXA3/G-EXA7).
            for ref in EXA_LOCAL_REFS:
                if ref in code:
                    offenders.append(
                        f"{path.relative_to(ROOT)}: Exa local runtime ref '{ref}' in code"
                    )
            for tool in EXA_PROHIBITED_TOOLS:
                if tool in code:
                    offenders.append(
                        f"{path.relative_to(ROOT)}: prohibited Exa tool '{tool}' in code"
                    )
    # 4. Adapter loopback bind check (G-CLOSE9): adapter/server.js must bind
    #    to loopback only. The default HOST must be 127.0.0.1 and the startup
    #    validation must refuse non-loopback binds.
    adapter_server = ROOT / "adapter" / "server.js"
    if adapter_server.is_file():
        adapter_src = adapter_server.read_text(errors="ignore")
        if "127.0.0.1" not in adapter_src or "refusing non-loopback bind" not in adapter_src:
            offenders.append(
                "adapter/server.js: missing loopback bind validation"
            )
        # The adapter must not bind to 0.0.0.0 (wildcard).
        if re.search(r'"0\.0\.0\.0"', adapter_src):
            offenders.append(
                "adapter/server.js: binds to wildcard 0.0.0.0 (must be loopback only)"
            )
    return offenders


def main() -> int:
    found = scan()
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())