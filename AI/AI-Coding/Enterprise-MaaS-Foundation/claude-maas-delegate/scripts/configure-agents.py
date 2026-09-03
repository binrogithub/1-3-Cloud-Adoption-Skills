#!/usr/bin/env python3
"""Install additive Claude-MaaS delegation guidance for supported coding agents."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


SUPPORTED = frozenset({"codex", "copilot", "cursor", "opencode"})
OWNER_FILE = ".claude-maas-delegate-owner.json"
BEGIN = "<!-- BEGIN claude-maas-delegate-policy -->"
END = "<!-- END claude-maas-delegate-policy -->"
POLICY = f"""{BEGIN}
For bounded implementation, testing, bug-fix, refactor, CI, or documentation execution, use the installed `claude-maas-delegate` Skill and `maas-delegate`. Keep architecture, security, incidents, payment, complex diagnosis, and failed-twice work local. Do not change this agent's provider, model, or authentication.
{END}
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _replace_marker(path: Path, block: str | None) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    start = text.find(BEGIN)
    end = text.find(END)
    if start != -1 and end != -1 and end >= start:
        end += len(END)
        text = text[:start] + text[end:]
    if block:
        text = text.rstrip() + ("\n\n" if text.strip() else "") + block
    _atomic_write(path, text.rstrip() + "\n" if text.strip() else "")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_skill(source: Path, target: Path, *, force: bool) -> None:
    if target.exists():
        marker = target / OWNER_FILE
        if not marker.exists() and not force:
            raise OwnershipConflict(f"unowned skill exists: {target}")
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    _atomic_write(target / OWNER_FILE, json.dumps({"owner": "claude-maas-delegate"}) + "\n")


class OwnershipConflict(Exception):
    pass


def _agents(raw: str) -> list[str]:
    agents = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(agents) - SUPPORTED)
    if unknown:
        raise ValueError(f"unsupported agents: {','.join(unknown)}")
    if not agents:
        raise ValueError("at least one agent is required")
    return list(dict.fromkeys(agents))


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "managed_paths": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(path: Path, managed: list[Path]) -> None:
    payload = {
        "version": 1,
        "owner": "claude-maas-delegate",
        "managed_paths": [str(path) for path in managed],
        "digests": {str(path): _digest(path) for path in managed if path.is_file()},
    }
    _atomic_write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _strip_jsonc_comments(text: str) -> str:
    """Strip JSONC comments (// line and /* block */) from text.

    Handles comments inside strings correctly by tracking string state.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    string_char = ""
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            # Line comment — skip to end of line.
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            # Block comment — skip to */.
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _strip_jsonc_trailing_commas(text: str) -> str:
    """Remove JSONC trailing commas without touching string content."""
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    string_char = ""
    while i < n:
        ch = text[i]
        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue
        if ch == ",":
            next_index = i + 1
            while next_index < n and text[next_index].isspace():
                next_index += 1
            if next_index < n and text[next_index] in "}]":
                i += 1
                continue
        result.append(ch)
        i += 1
    return "".join(result)


def _load_jsonc(path: Path) -> dict:
    """Load JSONC with comments and trailing commas into a JSON object."""
    text = path.read_text(encoding="utf-8")
    return json.loads(_strip_jsonc_trailing_commas(_strip_jsonc_comments(text)))


def _opencode_path(home: Path) -> Path:
    root = home / ".config" / "opencode"
    jsonc = root / "opencode.jsonc"
    if jsonc.exists():
        return jsonc
    return root / "opencode.json"


def _install(home: Path, source: Path, manifest: Path, agents: list[str], force: bool) -> dict:
    if not (source / "SKILL.md").is_file():
        raise ValueError("skill source is missing SKILL.md")
    if "opencode" in agents:
        _opencode_path(home)  # validate before making any changes
    managed: list[Path] = []
    agents_skill = home / ".agents" / "skills" / "claude-maas-delegate"
    if any(agent in agents for agent in ("copilot", "cursor", "opencode")):
        _copy_skill(source, agents_skill, force=force)
        managed.append(agents_skill)
    if "codex" in agents:
        codex_skill = home / ".codex" / "skills" / "claude-maas-delegate"
        _copy_skill(source, codex_skill, force=force)
        managed.append(codex_skill)
        codex_policy = home / ".codex" / "AGENTS.md"
        _replace_marker(codex_policy, POLICY)
        managed.append(codex_policy)
    if "copilot" in agents:
        copilot_policy = home / ".copilot" / "copilot-instructions.md"
        _replace_marker(copilot_policy, POLICY)
        managed.append(copilot_policy)
    if "cursor" in agents:
        rule = home / ".cursor" / "rules" / "claude-maas-delegate.mdc"
        _atomic_write(rule, "---\ndescription: Claude-MaaS delegation policy\nalwaysApply: true\n---\n\n" + POLICY)
        managed.append(rule)
    if "opencode" in agents:
        config_path = _opencode_path(home)
        config = _load_jsonc(config_path) if config_path.exists() else {}
        instructions = config.get("instructions", [])
        if not isinstance(instructions, list) or not all(isinstance(item, str) for item in instructions):
            raise ValueError("OpenCode instructions must be a string array")
        instruction = str(agents_skill / "references" / "routing-policy.md")
        if instruction not in instructions:
            instructions.append(instruction)
        config["instructions"] = instructions
        _atomic_write(config_path, json.dumps(config, indent=2, sort_keys=True) + "\n")
        managed.append(config_path)
    _save_manifest(manifest, managed)
    return {"status": "success", "agents": agents, "manifest": str(manifest)}


def _uninstall(home: Path, manifest_path: Path, force: bool) -> dict:
    manifest = _load_manifest(manifest_path)
    for raw in manifest.get("managed_paths", []):
        path = Path(raw)
        if path.is_dir():
            marker = path / OWNER_FILE
            if marker.exists() or force:
                shutil.rmtree(path)
        elif path.name in {"AGENTS.md", "copilot-instructions.md"}:
            _replace_marker(path, None)
        elif path.name == "claude-maas-delegate.mdc":
            if path.exists():
                path.unlink()
        elif path.name in {"opencode.json", "opencode.jsonc"} and path.exists():
            config = _load_jsonc(path)
            installed = str(home / ".agents" / "skills" / "claude-maas-delegate" / "references" / "routing-policy.md")
            if isinstance(config.get("instructions"), list):
                config["instructions"] = [item for item in config["instructions"] if item != installed]
                _atomic_write(path, json.dumps(config, indent=2, sort_keys=True) + "\n")
    if manifest_path.exists():
        manifest_path.unlink()
    return {"status": "success"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--skill-source", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--force", action="store_true")

    install = commands.add_parser("install")
    common(install)
    install.add_argument("--agents", required=True)
    uninstall = commands.add_parser("uninstall")
    common(uninstall)
    check = commands.add_parser("check")
    common(check)
    check.add_argument("--agents", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    home = Path(os.environ.get("HOME", str(Path.home())))
    try:
        if args.command == "install":
            result = _install(home, args.skill_source, args.manifest, _agents(args.agents), args.force)
        elif args.command == "uninstall":
            result = _uninstall(home, args.manifest, args.force)
        else:
            requested = _agents(args.agents)
            result = {"status": "success", "agents": requested, "manifest_exists": args.manifest.exists()}
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except OwnershipConflict as exc:
        print(json.dumps({"status": "ownership_conflict", "summary": str(exc)}, separators=(",", ":")))
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "config_error", "summary": str(exc)}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
