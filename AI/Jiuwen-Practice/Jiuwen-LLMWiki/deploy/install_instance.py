#!/root/.local/share/uv/tools/jiuwenswarm/bin/python
"""Create the dedicated LLMWiki JiuwenSwarm instance and install the `llmwiki` role.

Zero changes to JiuwenSwarm code or to the shared default instance (~/.jiuwenswarm):
  * copies the default instance's config into <project>/runtime/jiuwen/config/
  * enables the role in the COPY (react.subagents.llmwiki.enabled = true)
  * installs role/llmwiki.md into <project>/runtime/jiuwen/agents/
  * renders systemd units that run the stock binaries with
    JIUWENSWARM_DATA_DIR / GATEWAY_PORT / WEB_PORT / AGENT_SERVER_PORT set.

Dry-run by default. Use --apply to write files; units are NOT enabled or started here.
Runs with JiuwenSwarm's own interpreter (it ships PyYAML).
"""
from __future__ import annotations

import argparse
import difflib
import os
import shutil
import sys
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parent.parent
BIN = Path("/root/.local/bin")
UNITS = {
    "llmwiki-jiuwen-agentserver": "jiuwenswarm-agentserver",
    "llmwiki-jiuwen-gateway": "jiuwenswarm-gateway",
}
UNIT_TMPL = """[Unit]
Description=LLMWiki dedicated JiuwenSwarm {what} (stock binary, isolated data dir)
After=network-online.target{after}

[Service]
Type=simple
Environment=HOME=/root
Environment=PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=JIUWENSWARM_DATA_DIR={data}
Environment=AGENT_SERVER_PORT={agent_port}
Environment=GATEWAY_PORT={gw_port}
Environment=WEB_PORT={web_port}
WorkingDirectory={work}
ExecStart={bin} --dotenv {data}/config/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def patch_config(cfg: dict, role: str) -> dict:
    react = cfg.setdefault("react", {})
    subs = react.setdefault("subagents", {}) or {}
    react["subagents"] = subs
    subs[role] = {"enabled": True}
    # The role is tool-less and stateless: keep other sub-agents that could act on the host off.
    for name in ("code_agent", "research_agent", "browser_agent"):
        if name in subs:
            subs[name]["enabled"] = False
    cfg["auto_memory_enabled"] = False
    # DeepSeek thinking off (2026-09-24, verified against MaaS): vLLM-style
    # chat_template_kwargs.enable_thinking=false removes reasoning_content.
    for m in cfg.get("models", {}).get("defaults", []):
        mco = m.setdefault("model_config_obj", {})
        mco["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    cfg.setdefault("mcp", {})["servers"] = []
    # Code mode is required (agent-mode custom roles crash in 0.2.3, PRD §5.3 R-6), and its main
    # agent carries shell/file tools. The wiki never needs them: deny, don't "ask" (headless
    # "ask" does not block, R-3). Enforcement is verified live, see PRD §12 AG-6.
    perms = cfg.setdefault("permissions", {})
    perms["enabled"] = True
    tools = perms.setdefault("tools", {}) or {}
    perms["tools"] = tools
    for t in DENY_TOOLS:
        tools[t] = "deny"
    perms["rules"] = [r for r in (perms.get("rules") or [])
                      if not set(r.get("tools") or []) & set(DENY_TOOLS)]
    return cfg


DENY_TOOLS = ("bash", "mcp_exec_command", "create_terminal", "write", "write_file", "edit_file",
              "search_replace", "acp_chat", "cron_create_job", "cron_update_job",
              "cron_delete_job", "cron_toggle_job")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-home", default=os.path.expanduser("~/.jiuwenswarm"))
    ap.add_argument("--data-dir", default=str(PROJECT / "runtime" / "jiuwen"))
    ap.add_argument("--role", default="llmwiki")
    ap.add_argument("--agent-port", type=int, default=20092)
    ap.add_argument("--gateway-port", type=int, default=20001)
    ap.add_argument("--web-port", type=int, default=20000)
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing instance config")
    a = ap.parse_args()

    src = Path(a.source_home) / "config"
    data = Path(a.data_dir)
    dst = data / "config"
    role_src = PROJECT / "role" / f"{a.role}.md"
    for need in (src / "config.yaml", src / ".env", role_src):
        if not need.exists():
            print(f"missing: {need}", file=sys.stderr)
            return 1
    if (dst / "config.yaml").exists() and not a.force:
        print(f"{dst/'config.yaml'} exists; use --force to regenerate", file=sys.stderr)
        return 1

    original = (src / "config.yaml").read_text(encoding="utf-8")
    cfg = patch_config(yaml.safe_load(original) or {}, a.role)
    new_text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
    diff = [l for l in difflib.unified_diff(
        yaml.safe_dump(yaml.safe_load(original), allow_unicode=True, sort_keys=False).splitlines(),
        new_text.splitlines(), "default/config.yaml", "llmwiki/config.yaml", lineterm="", n=1)]
    print("\n".join(diff) or "(no config diff)")

    units = {}
    work = data / "work"          # R-10: code mode creates working folders here, never in the project root
    for unit, binary in UNITS.items():
        units[unit] = UNIT_TMPL.format(
            what=binary.split("-")[-1], data=data, agent_port=a.agent_port, gw_port=a.gateway_port,
            web_port=a.web_port, work=work, bin=BIN / binary,
            after="" if "agentserver" in unit else "\nRequires=llmwiki-jiuwen-agentserver.service\n"
                  "After=llmwiki-jiuwen-agentserver.service")

    plan = [f"mkdir {dst}", f"write {dst/'config.yaml'}", f"copy {src/'.env'} -> {dst/'.env'} (0600)",
            f"copy {src/'builtin_rules.yaml'} (if present)", f"install role {role_src} -> {data/'agents'}"]
    plan += [f"write {PROJECT/'deploy'/'systemd'/(u + '.service')}" for u in units]
    print("\nPlan:\n  " + "\n  ".join(plan))
    if not a.apply:
        print("\nDry run. Re-run with --apply to write. Units are never started by this script.")
        return 0

    dst.mkdir(parents=True, exist_ok=True)
    (dst / "config.yaml").write_text(new_text, encoding="utf-8")
    shutil.copy2(src / ".env", dst / ".env")
    os.chmod(dst / ".env", 0o600)
    if (src / "builtin_rules.yaml").exists():
        shutil.copy2(src / "builtin_rules.yaml", dst / "builtin_rules.yaml")
    (data / "work").mkdir(parents=True, exist_ok=True)   # R-10 working directory for code mode
    (data / "agents").mkdir(parents=True, exist_ok=True)
    shutil.copy2(role_src, data / "agents" / role_src.name)
    for u, text in units.items():
        (PROJECT / "deploy" / "systemd" / f"{u}.service").write_text(text, encoding="utf-8")
    print("\nDone. To start (review units first):\n"
          "  cp deploy/systemd/llmwiki-jiuwen-*.service /etc/systemd/system/ && systemctl daemon-reload\n"
          "  systemctl start llmwiki-jiuwen-agentserver llmwiki-jiuwen-gateway\n"
          "  ./bin/llmwiki doctor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
