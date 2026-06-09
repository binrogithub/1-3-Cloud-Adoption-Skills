#!/usr/bin/env python3
"""Install the claude-glm CCR bridge for LiteLLM-backed search.

The current claude-glm search path is:

  Claude Code -> CCR /v1/messages -> LiteLLM /v1/responses
    -> LiteLLM custom_callbacks.py injects Exa search results
    -> Huawei MaaS GLM answers normally

This script installs the CCR transformer used by that path. The transformer
does not call a search API itself; it strips local Claude Code search/fetch
tools for search-intent prompts and lets the LiteLLM callback do the live
search injection when EXA_API_KEY is configured.
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


TRANSFORMER_JS = r'''class ClaudeWebSearchToResponses {
  constructor(options = {}) {
    this.options = options;
  }

  name = "claude-websearch-to-responses";

  isSearchIntent(body) {
    const text = this.latestUserText(body).toLowerCase();
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/.test(text);
  }

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

  async transformRequestIn(body) {
    const searchIntent = this.isSearchIntent(body);

    if (body && Array.isArray(body.input)) {
      body.use_chat_completions_api = true;
    }

    if (searchIntent) {
      this.addSystemInstruction(
        body,
        "Live search, when configured, is handled before the model call by the LiteLLM proxy. Do not call WebSearch, WebFetch, Fetch, or shell tools for this search request."
      );
      if (Array.isArray(body.tools)) {
        body.tools = [];
      }
    }

    return body;
  }

  async transformResponseOut(response) {
    if (!response || !response.body) return response;

    const decoder = new TextDecoder();
    const encoder = new TextEncoder();
    const pendingTools = new Map();
    let buffer = "";

    const emitSse = (controller, eventName, data) => {
      if (eventName) controller.enqueue(encoder.encode(`event: ${eventName}\n`));
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
    };

    const processEvent = (controller, rawEvent) => {
      const lines = rawEvent.split(/\r?\n/);
      let eventName = "";
      const dataLines = [];
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }

      if (dataLines.length === 0) {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      const dataText = dataLines.join("\n");
      if (dataText === "[DONE]") {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      let data;
      try {
        data = JSON.parse(dataText);
      } catch {
        controller.enqueue(encoder.encode(`${rawEvent}\n\n`));
        return;
      }

      if (
        data.type === "content_block_start" &&
        data.content_block?.type === "tool_use"
      ) {
        pendingTools.set(data.index, { eventName, data, partialJson: "" });
        return;
      }

      if (
        data.type === "content_block_delta" &&
        data.delta?.type === "input_json_delta" &&
        pendingTools.has(data.index)
      ) {
        pendingTools.get(data.index).partialJson += data.delta.partial_json || "";
        return;
      }

      if (data.type === "content_block_stop" && pendingTools.has(data.index)) {
        const pending = pendingTools.get(data.index);
        pendingTools.delete(data.index);

        const startData = JSON.parse(JSON.stringify(pending.data));
        try {
          startData.content_block.input = pending.partialJson
            ? JSON.parse(pending.partialJson)
            : startData.content_block.input || {};
        } catch {
          startData.content_block.input = startData.content_block.input || {};
        }

        emitSse(controller, pending.eventName, startData);
        emitSse(controller, eventName, data);
        return;
      }

      emitSse(controller, eventName, data);
    };

    const stream = new TransformStream({
      transform(chunk, controller) {
        buffer += decoder.decode(chunk, { stream: true });
        let boundary;
        while ((boundary = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const rawEvent = buffer.slice(0, boundary);
          const match = buffer.slice(boundary).match(/^\r?\n\r?\n/);
          buffer = buffer.slice(boundary + (match ? match[0].length : 2));
          processEvent(controller, rawEvent);
        }
      },
      flush(controller) {
        buffer += decoder.decode();
        if (buffer.trim()) processEvent(controller, buffer.trimEnd());
      },
    });

    return new Response(response.body.pipeThrough(stream), {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }
}

module.exports = ClaudeWebSearchToResponses;
'''


BRIDGE_NAME = "claude-websearch-to-responses"
LEGACY_TRANSFORMER_NAMES = {
    "ccr-search-prefetch",
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


def clean_bridge_items(items: list[Any]) -> list[Any]:
    return [
        item
        for item in items
        if normalize_transformer_item(item) not in LEGACY_TRANSFORMER_NAMES | {BRIDGE_NAME}
    ]


def insert_bridge(items: list[Any]) -> list[Any]:
    items = clean_bridge_items(items)
    names = [normalize_transformer_item(item) for item in items]
    if "openai-responses" in names:
        index = names.index("openai-responses")
        return items[:index] + [BRIDGE_NAME, items[index], BRIDGE_NAME] + items[index + 1 :]
    for marker in ("reasoning", "enhancetool"):
        if marker in names:
            index = names.index(marker)
            return items[:index] + [BRIDGE_NAME] + items[index:]
    return items + [BRIDGE_NAME]


def patch_ccr_config(path: Path, plugin_path: Path, apply: bool) -> None:
    data = load_json(path)

    for provider in data.setdefault("Providers", []):
        transformer = provider.setdefault("transformer", {})
        use = transformer.setdefault("use", [])
        transformer["use"] = insert_bridge(use)

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
        default="/root/.claude-code-router/plugins/claude-websearch-to-responses.js",
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
