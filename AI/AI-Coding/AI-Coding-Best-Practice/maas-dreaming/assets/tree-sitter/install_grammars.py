"""Install tree-sitter language grammars.

Usage:
    python3 install_grammars.py --languages python,javascript,typescript
    python3 install_grammars.py --all
    python3 install_grammars.py --check

Maps language names to their pip package names.  Installs via subprocess so
that the correct Python environment (virtual env or system) is used.

Exit code: 0 when all requested grammars are installed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from typing import Sequence

# ---------------------------------------------------------------------------
# Language -> pip package mapping
# ---------------------------------------------------------------------------

GRAMMAR_PACKAGES: dict[str, str] = {
    # P0 — shipped in [project.optional-dependencies] languages
    "python":     "tree-sitter-python",
    "javascript": "tree-sitter-javascript",
    "typescript": "tree-sitter-typescript",
    # P1 — available, not in default extras
    "go":         "tree-sitter-go",
    "rust":       "tree-sitter-rust",
    "java":       "tree-sitter-java",
    "c":          "tree-sitter-c",
    "cpp":        "tree-sitter-cpp",
    # P2 — structural/text grammars
    "ruby":       "tree-sitter-ruby",
    "bash":       "tree-sitter-bash",
}

# Canonical "default" set referenced by --all
DEFAULT_LANGUAGES: list[str] = ["python", "javascript", "typescript"]

ALL_LANGUAGES: list[str] = list(GRAMMAR_PACKAGES.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_installed(package: str) -> bool:
    """Return True if *package* is importable in the current environment."""
    # tree-sitter-python installs as tree_sitter_python, etc.
    module_name = package.replace("-", "_")
    return importlib.util.find_spec(module_name) is not None


def _install(package: str) -> bool:
    """pip-install *package*.  Return True on success."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR installing {package}:\n{result.stderr.strip()}", file=sys.stderr)
    return result.returncode == 0


def _resolve_languages(names: Sequence[str]) -> list[str]:
    """Validate language names against GRAMMAR_PACKAGES; return canonical list."""
    resolved = []
    for name in names:
        name = name.strip().lower()
        if name not in GRAMMAR_PACKAGES:
            print(
                f"Unknown language: {name!r}. "
                f"Available: {', '.join(sorted(GRAMMAR_PACKAGES))}",
                file=sys.stderr,
            )
            sys.exit(1)
        resolved.append(name)
    return resolved


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_check(languages: list[str]) -> int:
    """List installed vs missing grammars for *languages*. Return exit code."""
    installed = []
    missing = []

    for lang in languages:
        pkg = GRAMMAR_PACKAGES[lang]
        if _is_installed(pkg):
            installed.append((lang, pkg))
        else:
            missing.append((lang, pkg))

    if installed:
        print("Installed:")
        for lang, pkg in installed:
            print(f"  {lang:<15}  {pkg}")

    if missing:
        print("Missing:")
        for lang, pkg in missing:
            print(f"  {lang:<15}  {pkg}")

    return 0 if not missing else 1


def cmd_install(languages: list[str]) -> int:
    """Install grammars for *languages*. Return exit code (0=all ok, 1=any fail)."""
    any_failed = False

    for lang in languages:
        pkg = GRAMMAR_PACKAGES[lang]
        if _is_installed(pkg):
            print(f"  {lang}: already installed ({pkg})")
            continue
        print(f"  {lang}: installing {pkg} ...", end=" ", flush=True)
        ok = _install(pkg)
        if ok:
            print("OK")
        else:
            print("FAILED")
            any_failed = True

    return 1 if any_failed else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--languages",
        metavar="LANG,...",
        help=(
            "Comma-separated list of language names to install. "
            f"Available: {', '.join(sorted(GRAMMAR_PACKAGES))}"
        ),
    )
    group.add_argument(
        "--all",
        action="store_true",
        help=f"Install all known grammars ({', '.join(ALL_LANGUAGES)})",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help=(
            "Report which grammars are installed vs missing "
            "(default set: python, javascript, typescript)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        # --check with no explicit --languages checks the default set
        return cmd_check(DEFAULT_LANGUAGES)

    if args.all:
        languages = ALL_LANGUAGES
    elif args.languages:
        languages = _resolve_languages(args.languages.split(","))
    else:
        # No flag provided: default to check mode
        parser.print_help()
        return 0

    return cmd_install(languages)


if __name__ == "__main__":
    sys.exit(main())
