#!/usr/bin/env python3
"""Patch forky server.ts to accept system/developer roles in messages.

Claude Code 2.1.x can send `messages` entries with role `system` or
`developer`. Anthropic Messages expects those as the top-level `system` field,
so forky should normalize before Zod validation instead of returning 400.
"""
from __future__ import annotations

import pathlib
import sys


HELPERS = '''type RawRecord = Record<string, unknown>;

function isRecord(value: unknown): value is RawRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function contentToSystemText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((block) => {
      if (isRecord(block) && block.type === "text" && typeof block.text === "string") return block.text;
      return JSON.stringify(block);
    }).join("\\n\\n");
  }
  return String(content ?? "");
}

function normalizeIncomingRequest(raw: unknown): unknown {
  if (!isRecord(raw) || !Array.isArray(raw.messages)) return raw;

  const movedSystemTexts: string[] = [];
  const messages = raw.messages.filter((message) => {
    if (!isRecord(message)) return true;
    if (message.role !== "system" && message.role !== "developer") return true;
    movedSystemTexts.push(contentToSystemText(message.content));
    return false;
  });

  if (movedSystemTexts.length === 0) return raw;

  const existingSystem = raw.system;
  const system = Array.isArray(existingSystem)
    ? [...existingSystem, ...movedSystemTexts.map((text) => ({ type: "text", text }))]
    : typeof existingSystem === "string"
      ? [existingSystem, ...movedSystemTexts].join("\\n\\n")
      : movedSystemTexts.join("\\n\\n");

  log("info", "request.normalized_roles", { moved: movedSystemTexts.length });
  return { ...raw, system, messages };
}

'''


def main() -> int:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/server.ts")
    text = path.read_text()
    if "normalizeIncomingRequest(" in text and "request.normalized_roles" in text:
        return 0

    marker = "const app = new Hono();\n\n"
    if marker not in text:
        print(f"marker not found in {path}: {marker!r}", file=sys.stderr)
        return 1
    text = text.replace(marker, marker + HELPERS, 1)

    old = "  const parsed = AnthropicRequest.safeParse(rawBody);\n"
    new = "  const normalizedBody = normalizeIncomingRequest(rawBody);\n  const parsed = AnthropicRequest.safeParse(normalizedBody);\n"
    if old not in text:
        print(f"validation line not found in {path}", file=sys.stderr)
        return 1
    text = text.replace(old, new, 1)
    path.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
