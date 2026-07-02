#!/usr/bin/env python3
"""Patch forky anthropic.ts to keep Anthropic cache_control TTLs ordered.

Anthropic rejects requests where a normal 5-minute cache marker appears before
an extended `ttl: "1h"` marker in processing order. Forky may add a 5-minute
tool marker before Claude Code's existing 1-hour system marker, so normalize
later 1-hour markers down to 5 minutes before dispatch.
"""
from __future__ import annotations

import pathlib
import sys


NORMALIZER = '''function isCacheRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeCacheControlTtlOrder(body: AnthropicBody): AnthropicBody {
  let sawFiveMinuteTtl = false;
  let changed = false;

  const normalizeBlock = (block: unknown): unknown => {
    if (!isCacheRecord(block) || !isCacheRecord(block.cache_control)) return block;
    const cacheControl = block.cache_control;
    if (cacheControl.type !== "ephemeral") return block;

    const ttl = cacheControl.ttl;
    if (ttl === "1h") {
      if (!sawFiveMinuteTtl) return block;
      changed = true;
      return { ...block, cache_control: { ...cacheControl, ttl: "5m" } };
    }

    // Anthropic treats an omitted TTL as the default 5m. Once a 5m marker has
    // appeared, a later 1h marker is rejected.
    if (ttl == null || ttl === "5m") {
      sawFiveMinuteTtl = true;
    }
    return block;
  };

  const out: AnthropicBody = { ...body };

  const tools = (out as { tools?: Array<unknown> }).tools;
  if (Array.isArray(tools)) {
    const normalized = tools.map(normalizeBlock);
    if (normalized.some((block, i) => block !== tools[i])) {
      (out as { tools?: Array<unknown> }).tools = normalized;
    }
  }

  if (Array.isArray(out.system)) {
    const normalized = out.system.map(normalizeBlock) as typeof out.system;
    if (normalized.some((block, i) => block !== out.system![i])) {
      out.system = normalized;
    }
  }

  const messages = (out as { messages?: Array<Record<string, unknown>> }).messages;
  if (Array.isArray(messages)) {
    const normalizedMessages = messages.map((message) => {
      const content = message.content;
      if (!Array.isArray(content)) return message;
      const normalizedContent = content.map(normalizeBlock);
      if (!normalizedContent.some((block, i) => block !== content[i])) return message;
      return { ...message, content: normalizedContent };
    });
    if (normalizedMessages.some((message, i) => message !== messages[i])) {
      (out as { messages?: Array<Record<string, unknown>> }).messages = normalizedMessages;
    }
  }

  return changed ? out : body;
}

'''


def main() -> int:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/anthropic.ts")
    text = path.read_text()
    changed = False

    if "const prepared = normalizeCacheControlTtlOrder(" not in text:
        old = "  const prepared = addCachingMarkers(normalizeCacheBustingTokens(stripUnsupportedFields(injectSystemBlock(body))));\n"
        new = (
            "  const prepared = normalizeCacheControlTtlOrder(\n"
            "    addCachingMarkers(normalizeCacheBustingTokens(stripUnsupportedFields(injectSystemBlock(body)))),\n"
            "  );\n"
        )
        if old not in text:
            print(f"forwardOAuth prepared line not found in {path}", file=sys.stderr)
            return 1
        text = text.replace(old, new, 1)
        changed = True

    if "function normalizeCacheControlTtlOrder" not in text:
        marker = "\n/**\n * Same as forwardOAuth"
        if marker not in text:
            print(f"insertion marker not found in {path}", file=sys.stderr)
            return 1
        text = text.replace(marker, "\n" + NORMALIZER + marker, 1)
        changed = True

    if changed:
        path.write_text(text)
        print(f"patched {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
