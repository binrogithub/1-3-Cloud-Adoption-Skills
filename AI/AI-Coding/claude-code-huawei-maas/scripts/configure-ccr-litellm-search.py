#!/usr/bin/env python3
"""Apply CCR/LiteLLM search-tool wiring for Claude Code.

This script intentionally avoids printing environment values or API keys.
"""

from __future__ import annotations

import argparse
import json
import os
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
  logger = null;

  isSearchIntent(body) {
    const textParts = [];
    const collect = (value) => {
      if (!value) return;
      if (typeof value === "string") {
        textParts.push(value);
        return;
      }
      if (Array.isArray(value)) {
        value.forEach(collect);
        return;
      }
      if (typeof value === "object") {
        if (typeof value.text === "string") textParts.push(value.text);
        if (typeof value.content === "string") textParts.push(value.content);
        if (Array.isArray(value.content)) collect(value.content);
      }
    };

    collect(body.messages);
    collect(body.input);

    const text = textParts.join("\n").toLowerCase();
    return /搜索|新闻|最新|今天|今日|current|latest|today|news|search/.test(text);
  }

  webSearchFunctionTool() {
    return {
      type: "function",
      function: {
        name: "litellm_web_search",
        description:
          "Search the web for current information using LiteLLM search tools.",
        parameters: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "The search query to execute",
            },
          },
          required: ["query"],
        },
      },
    };
  }

  normalizeTool(tool) {
    if (tool && tool.name === "WebSearch") {
      return this.webSearchFunctionTool();
    }

    const fn = tool && tool.function;
    if (!fn || fn.name !== "WebSearch") {
      return tool;
    }

    return {
      ...tool,
      function: {
        ...fn,
        name: "litellm_web_search",
        description:
          "Search the web for current information using LiteLLM search tools.",
        parameters: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "The search query to execute",
            },
          },
          required: ["query"],
        },
      },
    };
  }

  async transformRequestIn(body) {
    const searchIntent = this.isSearchIntent(body);

    if (body && Array.isArray(body.input)) {
      body.use_chat_completions_api = true;

      if (searchIntent) {
        body.input.unshift({
          role: "system",
          content:
            "This request requires current web information. Use the litellm_web_search function tool provided in this API request. Do not claim that web access is unavailable and do not use URL fetching tools.",
        });
      }
    }

    if (!Array.isArray(body.tools)) {
      return body;
    }

    if (searchIntent) {
      body.tools = body.tools
        .filter((tool) => {
          const name = tool && (tool.name || (tool.function && tool.function.name));
          return (
            name === "WebSearch" ||
            name === "web_search" ||
            name === "litellm_web_search"
          );
        })
        .map((tool) => this.normalizeTool(tool));
    } else {
      body.tools = body.tools.map((tool) => this.normalizeTool(tool));
    }

    return body;
  }
}

module.exports = ClaudeWebSearchToResponses;
'''


PROXY_SERVER_PATCH_SNIPPET = '''\
    def _dump_response_part(item):
        if hasattr(item, "model_dump"):
            return item.model_dump(exclude_none=True, exclude_unset=True)
        if isinstance(item, dict):
            return item
        return item

    def _get_response_field(item, field, default=None):
        if isinstance(item, dict):
            return item.get(field, default)
        return getattr(item, field, default)

    async def _single_item_async_iterator(item):
        if _get_response_field(item, "object") == "response" and _get_response_field(
            item, "output"
        ):
            response_payload = _dump_response_part(item)
            for index, output_item in enumerate(
                _get_response_field(item, "output", []) or []
            ):
                yield {
                    "type": "response.output_item.added",
                    "output_index": index,
                    "item": _dump_response_part(output_item),
                    "response": {
                        "id": _get_response_field(item, "id"),
                        "model": _get_response_field(item, "model"),
                    },
                }
            yield {"type": "response.completed", "response": response_payload}
            return
        yield item

    if not hasattr(response, "__aiter__"):
        response = _single_item_async_iterator(response)
'''


UTILS_PATCH_SNIPPET = '''\
            if hasattr(gen, "__await__"):
                gen = await gen  # type: ignore[assignment]
            if not hasattr(gen, "__aiter__"):
                yield gen
                return
'''


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
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write(path, text, apply)


def patch_ccr_config(path: Path, plugin_path: Path, apply: bool) -> None:
    data = load_json(path)
    providers = data.setdefault("Providers", [])
    for provider in providers:
        provider["api_base_url"] = provider.get(
            "api_base_url", "http://127.0.0.1:4000/v1/responses"
        ).replace("/v1/chat/completions", "/v1/responses")
        transformer = provider.setdefault("transformer", {})
        use = transformer.setdefault("use", [])
        required = [
            "claude-websearch-to-responses",
            "openai-responses",
            "claude-websearch-to-responses",
        ]
        for item in required:
            if item not in use:
                use.append(item)
    router = data.setdefault("Router", {})
    router.setdefault("webSearch", router.get("default"))
    transformers = data.setdefault("transformers", [])
    plugin_entry = {"path": str(plugin_path)}
    if plugin_entry not in transformers:
        transformers.append(plugin_entry)
    save_json(path, data, apply)


def patch_litellm_config(path: Path, search_tool_name: str, apply: bool) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    if "websearch_interception" not in text:
        text = text.replace(
            "callbacks:\n",
            "callbacks:\n    - \"websearch_interception\"\n",
            1,
        )
    if "websearch_interception_params:" not in text:
        marker = "  callbacks:\n"
        idx = text.find(marker)
        if idx != -1:
            next_section = text.find("\n  ", idx + len(marker))
            insert_at = next_section if next_section != -1 else len(text)
            params = (
                f"\n  websearch_interception_params:\n"
                f"    enabled_providers: [\"openai\"]\n"
                f"    search_tool_name: \"{search_tool_name}\"\n"
            )
            text = text[:insert_at] + params + text[insert_at:]
    if text == original:
        print(f"no LiteLLM config changes needed for {path}")
        return
    write(path, text, apply)


def patch_compose(compose_path: Path, patches_dir: Path, apply: bool) -> None:
    text = compose_path.read_text(encoding="utf-8")
    lines = [
        "      - ./patches/proxy_server.py:/app/litellm/proxy/proxy_server.py:ro",
        "      - ./patches/utils.py:/app/litellm/proxy/utils.py:ro",
        "      - ./patches/proxy_server.py:/app/.venv/lib/python3.13/site-packages/litellm/proxy/proxy_server.py:ro",
        "      - ./patches/utils.py:/app/.venv/lib/python3.13/site-packages/litellm/proxy/utils.py:ro",
    ]
    missing = [line for line in lines if line not in text]
    if not missing:
        print("compose patch mounts already present")
        return
    marker = "      - ./assets/config/custom_callbacks.py:/app/custom_callbacks.py:ro\n"
    if marker not in text:
        raise SystemExit(f"cannot find LiteLLM volume marker in {compose_path}")
    text = text.replace(marker, marker + "\n".join(missing) + "\n", 1)
    write(compose_path, text, apply)


def docker_cp_from(container: str, src: str, dst: Path) -> None:
    subprocess.run(["docker", "cp", f"{container}:{src}", str(dst)], check=True)


def patch_proxy_server_text(text: str) -> str:
    if "_single_item_async_iterator" not in text:
        marker = '    verbose_proxy_logger.debug("inside generator")\n'
        if marker not in text:
            raise SystemExit("cannot find async_data_generator insertion point")
        text = text.replace(marker, marker + "\n" + PROXY_SERVER_PATCH_SNIPPET, 1)

    dict_marker = (
        "            if isinstance(chunk, BaseModel):\n"
        "                chunk = chunk.model_dump_json(exclude_none=True, exclude_unset=True)\n"
    )
    dict_replacement = (
        dict_marker
        + "            elif isinstance(chunk, dict):\n"
        + "                chunk = json.dumps(chunk, ensure_ascii=False)\n"
    )
    if "json.dumps(chunk, ensure_ascii=False)" not in text:
        if dict_marker not in text:
            raise SystemExit("cannot find chunk serialization insertion point")
        text = text.replace(dict_marker, dict_replacement, 1)
    return text


def patch_utils_text(text: str) -> str:
    if "if not hasattr(gen, \"__aiter__\"):" in text:
        return text
    marker = "            async for chunk in gen:\n"
    if marker not in text:
        raise SystemExit("cannot find streaming wrapper insertion point")
    return text.replace(marker, UTILS_PATCH_SNIPPET + marker, 1)


def create_litellm_patch_files(patches_dir: Path, apply: bool, container: str) -> None:
    if not apply:
        print(f"would create patched LiteLLM files in {patches_dir}")
        return

    patches_dir.mkdir(parents=True, exist_ok=True)
    proxy_path = patches_dir / "proxy_server.py"
    utils_path = patches_dir / "utils.py"

    docker_cp_from(
        container,
        "/app/.venv/lib/python3.13/site-packages/litellm/proxy/proxy_server.py",
        proxy_path,
    )
    docker_cp_from(
        container,
        "/app/.venv/lib/python3.13/site-packages/litellm/proxy/utils.py",
        utils_path,
    )

    backup(proxy_path)
    backup(utils_path)
    proxy_path.write_text(
        patch_proxy_server_text(proxy_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    utils_path.write_text(
        patch_utils_text(utils_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    print(f"wrote {proxy_path}")
    print(f"wrote {utils_path}")


def restart_services(apply: bool) -> None:
    if not apply:
        print("would restart ccr and LiteLLM")
        return
    subprocess.run(["bash", "-lc", "ccr restart"], check=False)
    subprocess.run(["bash", "-lc", "docker compose up -d litellm"], cwd="/root/LiteLLM", check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes")
    parser.add_argument("--dry-run", action="store_true", help="show planned changes")
    parser.add_argument("--restart", action="store_true", help="restart CCR and LiteLLM")
    parser.add_argument("--patch-litellm-streaming", action="store_true")
    parser.add_argument("--litellm-container", default="litellm_proxy")
    parser.add_argument("--ccr-config", default="/root/.claude-code-router/config.json")
    parser.add_argument(
        "--ccr-plugin",
        default="/root/.claude-code-router/plugins/claude-websearch-to-responses.js",
    )
    parser.add_argument(
        "--litellm-config",
        default="/root/LiteLLM/assets/config/litellm_config.yaml",
    )
    parser.add_argument("--compose", default="/root/LiteLLM/docker-compose.yml")
    parser.add_argument("--search-tool-name", default="exa-search")
    args = parser.parse_args()

    apply = bool(args.apply)
    if args.dry_run:
        apply = False
    if not args.apply and not args.dry_run:
        parser.error("choose --dry-run or --apply")

    ccr_plugin = Path(args.ccr_plugin)
    write(ccr_plugin, TRANSFORMER_JS, apply)
    patch_ccr_config(Path(args.ccr_config), ccr_plugin, apply)
    patch_litellm_config(Path(args.litellm_config), args.search_tool_name, apply)

    if args.patch_litellm_streaming:
        patches_dir = Path(args.compose).parent / "patches"
        create_litellm_patch_files(patches_dir, apply, args.litellm_container)
        patch_compose(Path(args.compose), patches_dir, apply)

    if args.restart:
        restart_services(apply)

    return 0


if __name__ == "__main__":
    sys.exit(main())
