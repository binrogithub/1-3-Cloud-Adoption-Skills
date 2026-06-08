#!/usr/bin/env python3
"""Install CCR-layer web search prefetching for Claude Code.

This script intentionally avoids changing LiteLLM. Search is performed by a
CCR transformer before the model call. If no search API key is configured,
search prompts degrade to a normal model answer instead of breaking claude-glm.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


TRANSFORMER_JS = r'''class CcrSearchPrefetch {
  constructor(options = {}) {
    this.options = options;
  }

  name = "ccr-search-prefetch";

  latestUserText(body) {
    const textParts = [];
    const addText = (text) => {
      if (!text || text.includes("<system-reminder>")) return;
      textParts.push(text);
    };
    const collect = (value) => {
      if (!value) return;
      if (typeof value === "string") {
        addText(value);
        return;
      }
      if (Array.isArray(value)) {
        value.forEach(collect);
        return;
      }
      if (typeof value === "object") {
        if (typeof value.text === "string") addText(value.text);
        if (typeof value.content === "string") addText(value.content);
        if (Array.isArray(value.content)) collect(value.content);
      }
    };
    const latestUserMessage = (messages) => {
      if (!Array.isArray(messages)) return undefined;
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        if (messages[i] && messages[i].role === "user") return messages[i];
      }
      return undefined;
    };

    collect(latestUserMessage(body && body.messages));
    collect(latestUserMessage(body && body.input));
    return textParts.join("\n");
  }

  isSearchIntent(body) {
    const text = this.latestUserText(body).toLowerCase();
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/.test(text);
  }

  addSystemInstruction(body, content) {
    if (!body || !content) return;

    if (Array.isArray(body.input)) {
      body.input.unshift({ role: "system", content });
    }

    if (typeof body.system === "string") {
      body.system = `${body.system}\n\n${content}`;
    } else if (Array.isArray(body.system)) {
      body.system.push({ type: "text", text: content });
    } else if (Array.isArray(body.messages)) {
      body.system = [{ type: "text", text: content }];
    }
  }

  appendLatestUserText(body, text) {
    const appendToMessage = (message) => {
      if (!message || message.role !== "user") return false;
      if (typeof message.content === "string") {
        message.content += text;
        return true;
      }
      if (Array.isArray(message.content)) {
        message.content.push({ type: "text", text });
        return true;
      }
      return false;
    };

    for (const key of ["messages", "input"]) {
      if (!Array.isArray(body[key])) continue;
      for (let i = body[key].length - 1; i >= 0; i -= 1) {
        if (appendToMessage(body[key][i])) return;
      }
    }
  }

  readEnvFile(path, name) {
    try {
      const fs = require("fs");
      const text = fs.readFileSync(path, "utf8");
      const line = text
        .split(/\r?\n/)
        .find((entry) => entry.trim().startsWith(`${name}=`));
      if (!line) return "";
      return line
        .slice(line.indexOf("=") + 1)
        .trim()
        .replace(/^['"]|['"]$/g, "");
    } catch {
      return "";
    }
  }

  readEnvValue(name) {
    if (process.env[name]) return process.env[name];
    const envFiles = [
      this.options.envFile,
      process.env.CCR_SEARCH_ENV_FILE,
      "/root/.config/claude-glm/env",
      "/root/LiteLLM/.env",
    ].filter(Boolean);
    for (const path of envFiles) {
      const value = this.readEnvFile(path, name);
      if (value) return value;
    }
    return "";
  }

  searchApiKey() {
    return (
      this.readEnvValue("CCR_SEARCH_API_KEY") ||
      this.readEnvValue("EXA_API_KEY")
    );
  }

  async fetchExa(query) {
    const apiKey = this.searchApiKey();
    if (!apiKey || !query) return "";

    try {
      const response = await fetch("https://api.exa.ai/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
        },
        body: JSON.stringify({
          query,
          numResults: Number(this.options.numResults || 5),
          contents: { text: true },
        }),
      });
      if (!response.ok) return "";

      const data = await response.json();
      const results = Array.isArray(data.results) ? data.results : [];
      if (results.length === 0) return "";

      const lines = results.map((item, index) => {
        const title = item.title || "Untitled";
        const url = item.url || item.id || "";
        const published = item.publishedDate || "unknown date";
        const snippet = String(item.text || item.summary || "")
          .replace(/\s+/g, " ")
          .slice(0, 900);
        return `${index + 1}. ${title}\nURL: ${url}\nPublished: ${published}\nSnippet: ${snippet}`;
      });
      return `CCR web search results for: ${query}\n\n${lines.join("\n\n")}`;
    } catch {
      return "";
    }
  }

  stripSearchAndFetchTools(body) {
    if (!Array.isArray(body.tools)) return;
    body.tools = body.tools.filter((tool) => {
      const name = tool && (tool.name || (tool.function && tool.function.name));
      return !["WebSearch", "WebFetch", "Fetch", "web_search", "litellm_web_search"].includes(name);
    });
  }

  async transformRequestIn(body) {
    if (!body || !this.isSearchIntent(body)) return body;

    const query = this.latestUserText(body).slice(0, 500);
    const searchResults = await this.fetchExa(query);

    if (searchResults) {
      this.addSystemInstruction(
        body,
        "CCR has already searched the web for this request. Answer only from the injected CCR web search results. Include source URLs from those results. Do not call search, fetch, or shell tools."
      );
      this.appendLatestUserText(body, `\n\n${searchResults}`);
    } else {
      this.addSystemInstruction(
        body,
        "CCR web search is not configured or returned no results. Do not call WebSearch, WebFetch, Fetch, or shell tools for this search request. If the user asked for current information, clearly say that live search is unavailable and answer from available model knowledge only when useful."
      );
    }

    this.stripSearchAndFetchTools(body);
    return body;
  }
}

module.exports = CcrSearchPrefetch;
'''


LEGACY_TRANSFORMER_NAMES = {
    "claude-websearch-to-responses",
    "litellm_web_search",
}


def backup(path: Path) -> None:
    if path.exists():
        ts = time.strftime("%Y%m%d%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak.{ts}"))


def write(path: Path, content: str, apply: bool) -> None:
    if not apply:
        print(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any], apply: bool) -> None:
    write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", apply)


def normalize_transformer_item(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, list) and item and isinstance(item[0], str):
        return item[0]
    return None


def without_legacy_search(items: list[Any]) -> list[Any]:
    return [
        item
        for item in items
        if normalize_transformer_item(item) not in LEGACY_TRANSFORMER_NAMES
    ]


def insert_ccr_search_prefetch(items: list[Any]) -> list[Any]:
    items = without_legacy_search(items)
    if "ccr-search-prefetch" in items:
        return items

    for marker in ("openai-responses", "reasoning", "enhancetool"):
        if marker in items:
            index = items.index(marker)
            return items[:index] + ["ccr-search-prefetch"] + items[index:]
    return items + ["ccr-search-prefetch"]


def patch_ccr_config(path: Path, plugin_path: Path, apply: bool) -> None:
    data = load_json(path)

    for provider in data.setdefault("Providers", []):
        transformer = provider.setdefault("transformer", {})
        use = transformer.setdefault("use", [])
        transformer["use"] = insert_ccr_search_prefetch(use)

    transformers = data.setdefault("transformers", [])
    plugin_entry = {"path": str(plugin_path)}
    if plugin_entry not in transformers:
        transformers.append(plugin_entry)

    save_json(path, data, apply)


def restart_ccr(apply: bool) -> None:
    if not apply:
        print("would restart ccr")
        return
    subprocess.run(["bash", "-lc", "ccr restart"], check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes")
    parser.add_argument("--dry-run", action="store_true", help="show planned changes")
    parser.add_argument("--restart", action="store_true", help="restart CCR")
    parser.add_argument("--ccr-config", default="/root/.claude-code-router/config.json")
    parser.add_argument(
        "--ccr-plugin",
        default="/root/.claude-code-router/plugins/ccr-search-prefetch.js",
    )
    args = parser.parse_args()

    apply = bool(args.apply)
    if args.dry_run:
        apply = False
    if not args.apply and not args.dry_run:
        parser.error("choose --dry-run or --apply")

    ccr_plugin = Path(args.ccr_plugin)
    write(ccr_plugin, TRANSFORMER_JS, apply)
    patch_ccr_config(Path(args.ccr_config), ccr_plugin, apply)

    if args.restart:
        restart_ccr(apply)

    return 0


if __name__ == "__main__":
    sys.exit(main())
