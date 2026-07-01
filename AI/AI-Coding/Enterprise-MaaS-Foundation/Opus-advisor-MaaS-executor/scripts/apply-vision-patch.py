#!/usr/bin/env python3
"""Apply the vision-routing patch to forky's src/route.ts.

Used as a fallback when git apply can't handle the documentation-form patch.
Makes the minimal edits directly. Idempotent — skips changes already present.
"""
import sys
import re
import pathlib


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: apply-vision-patch.py <route.ts>", file=sys.stderr)
        return 2

    path = pathlib.Path(sys.argv[1])
    src = path.read_text()
    changed = False

    # 1. Add "vision" to the reason union
    if '"vision"' not in src:
        src = re.sub(
            r'reason:\s*"sentinel"\s*\|\s*"opus"\s*\|\s*"execution"\s*\|\s*"classifier"\s*;',
            'reason: "sentinel" | "opus" | "execution" | "classifier" | "vision";',
            src,
        )
        changed = True

    # 2. Add config-driven Opus/vision constants.
    if "OPUS_MODEL" not in src:
        plan_repl = (
            'const OPUS_MODEL = process.env.FORKY_OPUS_MODEL ?? "claude-opus-4-8";\n'
            'const PLAN_MODE_MODEL = process.env.FORKY_PLAN_MODEL ?? OPUS_MODEL;'
        )
        if re.search(r'^const PLAN_MODE_MODEL = [^\n]+;', src, re.M):
            src = re.sub(r'^const PLAN_MODE_MODEL = [^\n]+;', plan_repl, src, count=1, flags=re.M)
            changed = True
        else:
            insert = "\n" + plan_repl + "\n"
            anchor = re.search(r'^(export function decideRoute|function decideRoute|export function)', src, re.M)
            if anchor:
                pos = anchor.start()
                src = src[:pos] + insert + src[pos:]
                changed = True
    if "FORKY_PLAN_MODEL" not in src:
        src = src.replace(
            'const PLAN_MODE_MODEL = "claude-opus-4-7";',
            'const PLAN_MODE_MODEL = process.env.FORKY_PLAN_MODEL ?? OPUS_MODEL;',
        ).replace(
            'const PLAN_MODE_MODEL = "claude-opus-4-8";',
            'const PLAN_MODE_MODEL = process.env.FORKY_PLAN_MODEL ?? OPUS_MODEL;',
        )
        changed = True

    if "VISION_MODEL" not in src:
        insert = (
            '\n// Vision-capable model for image-bearing requests (execution backend has no vision).\n'
            'const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? OPUS_MODEL;\n'
        )
        # Insert before the first function/export, or at a reasonable anchor
        anchor = re.search(r'^(export function decideRoute|function decideRoute|export function)', src, re.M)
        if anchor:
            pos = anchor.start()
            src = src[:pos] + insert + src[pos:]
            changed = True
    elif "FORKY_VISION_MODEL ?? OPUS_MODEL" not in src:
        src = src.replace(
            'const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? "claude-opus-4-7";',
            'const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? OPUS_MODEL;',
        ).replace(
            'const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? "claude-opus-4-8";',
            'const VISION_MODEL = process.env.FORKY_VISION_MODEL ?? OPUS_MODEL;',
        )
        changed = True

    # 3. Add hasImageContent helper (before decideRoute)
    if "hasImageContent" not in src:
        helper = '''
type MessageContentBlock = { type?: string; content?: unknown };
type RoutableBody = {
  tools?: ReadonlyArray<{ name?: string }>;
  messages?: ReadonlyArray<{ content?: unknown }>;
};

function hasImageContent(body: RoutableBody): boolean {
  const blockHasImage = (block: MessageContentBlock): boolean => {
    if (block?.type === "image") return true;
    return Array.isArray(block?.content)
      && block.content.some((b) => typeof b === "object" && b !== null && (b as MessageContentBlock).type === "image");
  };
  return (body.messages ?? []).some((m) =>
    Array.isArray(m.content)
    && m.content.some((b) => typeof b === "object" && b !== null && blockHasImage(b as MessageContentBlock)),
  );
}
'''
        anchor = re.search(r'^(export function decideRoute|function decideRoute)', src, re.M)
        if anchor:
            pos = anchor.start()
            src = src[:pos] + helper + src[pos:]
            changed = True

    # 4. Add vision branch before the final execution return
    if 'reason: "vision"' not in src:
        # Find the execution return and insert before it
        src = re.sub(
            r'(  return \{ provider:\s*"aistack"[^}]*reason:\s*"execution"[^}]*\};)',
            '  if (hasImageContent(body)) {\n    return { provider: "anthropic-oauth", rewriteModel: VISION_MODEL, reason: "vision" };\n  }\n\n\1',
            src,
        )
        changed = True

    # 5. Update decideRoute signature to accept RoutableBody
    if "RoutableBody" not in src.split("decideRoute")[1].split(")")[0] if "decideRoute" in src else True:
        src = re.sub(
            r'(decideRoute\([^)]*body:\s*)\{\s*tools\?\:\s*ReadonlyArray<unknown>\s*\}',
            r'\1RoutableBody',
            src,
        )
        changed = True

    if changed:
        path.write_text(src)
        print(f"patched {path}")
    else:
        print(f"no changes needed — {path} already has vision routing")


if __name__ == "__main__":
    sys.exit(main())
