#!/usr/bin/env python3
"""Configure CCR and LiteLLM search-tool routing for Claude Code.

The script avoids printing environment values or API keys. It writes a CCR
transformer, updates the CCR provider to /v1/responses, and inserts LiteLLM
websearch_interception/search_tools blocks when missing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any


TRANSFORMER_JS = r'''class ClaudeWebSearchToResponses {
  name = "claude-websearch-to-responses";

  isSearchIntent(body) {
    const parts = [];
    const collect = (value) => {
      if (!value) return;
      if (typeof value === "string") return parts.push(value);
      if (Array.isArray(value)) return value.forEach(collect);
      if (typeof value === "object") {
        if (typeof value.text === "string") parts.push(value.text);
        if (typeof value.content === "string") parts.push(value.content);
        if (Array.isArray(value.content)) collect(value.content);
      }
    };
    collect(body.messages);
    collect(body.input);
    const text = parts.join("\n").toLowerCase();
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/.test(text);
  }

  searchTool() {
    return {
      type: "function",
      function: {
        name: "litellm_web_search",
        description: "Search the web for current information using LiteLLM search tools.",
        parameters: {
          type: "object",
          properties: {
            query: { type: "string", description: "The search query to execute" }
          },
          required: ["query"]
        }
      }
    };
  }

  normalizeTool(tool) {
    const name = tool && (tool.name || (tool.function && tool.function.name));
    if (name === "WebSearch" || name === "web_search") return this.searchTool();
    return tool;
  }

  async transformRequestIn(body) {
    const searchIntent = this.isSearchIntent(body || {});

    if (body && Array.isArray(body.input)) {
      body.use_chat_completions_api = true;
      if (searchIntent) {
        body.input.unshift({
          role: "system",
          content: "This request needs current web information. Use the litellm_web_search function tool. Do not use URL fetch tools for search."
        });
      }
    }

    if (!body || !Array.isArray(body.tools)) return body;

    const mapped = body.tools.map((tool) => this.normalizeTool(tool));
    body.tools = searchIntent
      ? mapped.filter((tool) => {
          const name = tool && (tool.name || (tool.function && tool.function.name));
          return name === "litellm_web_search" || name === "WebSearch" || name === "web_search";
        })
      : mapped;

    if (searchIntent && body.tools.length === 0) body.tools = [this.searchTool()];
    return body;
  }
}

module.exports = ClaudeWebSearchToResponses;
'''


def backup(path: Path) -> None:
    if path.exists():
        stamp = time.strftime("%Y%m%d%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak.{stamp}"))


def write_text(path: Path, text: str, apply: bool) -> None:
    if not apply:
        print(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any], apply: bool) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", apply)


def patch_ccr_config(path: Path, plugin_path: Path, apply: bool) -> None:
    data = load_json(path)

    for provider in data.get("Providers", []):
        url = provider.get("api_base_url") or "http://127.0.0.1:4000/v1/responses"
        provider["api_base_url"] = url.replace("/v1/chat/completions", "/v1/responses")
        if not provider["api_base_url"].endswith("/v1/responses"):
            provider["api_base_url"] = provider["api_base_url"].rstrip("/") + "/v1/responses"

        transformer = provider.setdefault("transformer", {})
        chain = transformer.setdefault("use", [])
        for name in ["claude-websearch-to-responses", "openai-responses", "claude-websearch-to-responses"]:
            if name not in chain:
                chain.append(name)

    router = data.setdefault("Router", {})
    router.setdefault("webSearch", router.get("default"))

    transformers = data.setdefault("transformers", [])
    entry = {"path": str(plugin_path)}
    if entry not in transformers:
        transformers.append(entry)

    save_json(path, data, apply)


def patch_litellm_config(path: Path, search_tool_name: str, apply: bool) -> None:
    text = path.read_text(encoding="utf-8")
    original = text

    if "websearch_interception" not in text:
        text = text.replace("callbacks:\n", "callbacks:\n    - \"websearch_interception\"\n", 1)

    if "websearch_interception_params:" not in text:
        marker = "  callbacks:\n"
        idx = text.find(marker)
        if idx != -1:
            next_section = text.find("\n  ", idx + len(marker))
            insert_at = next_section if next_section != -1 else len(text)
            text = (
                text[:insert_at]
                + f"\n  websearch_interception_params:\n"
                + f"    enabled_providers: [\"openai\"]\n"
                + f"    search_tool_name: \"{search_tool_name}\"\n"
                + text[insert_at:]
            )

    if "search_tools:" not in text:
        text += (
            f"\nsearch_tools:\n"
            f"  - search_tool_name: \"{search_tool_name}\"\n"
            f"    litellm_params:\n"
            f"      search_provider: \"exa_ai\"\n"
            f"      api_key: \"os.environ/EXA_API_KEY\"\n"
        )

    if text == original:
        print(f"no LiteLLM config changes needed for {path}")
        return
    write_text(path, text, apply)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes")
    parser.add_argument("--dry-run", action="store_true", help="show planned writes")
    parser.add_argument("--ccr-config", default="/root/.claude-code-router/config.json")
    parser.add_argument("--ccr-plugin", default="/root/.claude-code-router/plugins/claude-websearch-to-responses.js")
    parser.add_argument("--litellm-config", default="/root/LiteLLM/assets/config/litellm_config.yaml")
    parser.add_argument("--search-tool-name", default="exa-search")
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        parser.error("choose --dry-run or --apply")

    apply = bool(args.apply)
    ccr_plugin = Path(args.ccr_plugin)

    write_text(ccr_plugin, TRANSFORMER_JS, apply)
    patch_ccr_config(Path(args.ccr_config), ccr_plugin, apply)
    patch_litellm_config(Path(args.litellm_config), args.search_tool_name, apply)

    if not apply:
        print("dry run complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
