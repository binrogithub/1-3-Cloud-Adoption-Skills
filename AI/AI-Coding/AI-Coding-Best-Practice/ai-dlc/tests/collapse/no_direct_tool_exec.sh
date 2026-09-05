#!/usr/bin/env bash
# INV-38: outside run_browser_verify_session()/run_agent_bench_session()
# (the two permitted dispatch points) and the two pin-state functions
# that only ever check for a path/executable's presence, no code in
# bin/plan.py or bin/report.py may spawn a playwright/harbor executable
# directly — the orchestrator always goes through the existing
# [CLIENT, "chat", ...] jiuwenswarm dispatch shape, never around it.
#
# An AST walk, not a grep-with-context trick: grep only sees lines, so a
# comment mentioning a permitted function's name would wrongly exempt an
# unrelated line, and a real violation that doesn't happen to repeat that
# name on the same line would wrongly pass. This checks each
# subprocess-shaped call's actual enclosing function.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

"$(command -v python3.12 || command -v python3)" - "$ROOT" <<'PYEOF'
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
ALLOWED_FUNCS = {"run_browser_verify_session", "run_agent_bench_session"}
NAMES = ("playwright", "harbor")
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}

def enclosing_func(node, tree):
    """The innermost FunctionDef containing `node`, or None (module level)."""
    best = None
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
                if best is None or fn.lineno > best.lineno:
                    best = fn
    return best

def const_strings(node):
    """Every string literal reachable inside a call's arguments (covers a
    list literal of argv tokens, an f-string's literal pieces, etc.)."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value

violations = []
for fname in ("bin/plan.py", "bin/report.py"):
    path = root / fname
    if not path.is_file():
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        is_subprocess = (
            isinstance(callee, ast.Attribute)
            and callee.attr in SUBPROCESS_CALLS
            and isinstance(callee.value, ast.Name)
            and callee.value.id == "subprocess"
        )
        is_exec = (
            isinstance(callee, ast.Attribute)
            and callee.attr.startswith("exec")
            and isinstance(callee.value, ast.Name)
            and callee.value.id == "os"
        )
        if not (is_subprocess or is_exec):
            continue
        strings = " ".join(const_strings(node)).lower()
        if not any(name in strings for name in NAMES):
            continue
        fn = enclosing_func(node, tree)
        fn_name = fn.name if fn else "<module level>"
        if fn_name in ALLOWED_FUNCS:
            continue
        violations.append(
            f"{fname}:{node.lineno} in {fn_name}() spawns a "
            f"playwright/harbor-naming process outside "
            f"{sorted(ALLOWED_FUNCS)}")

if violations:
    print("FAIL: direct tool execution outside the permitted dispatchers "
          "(INV-38):")
    for v in violations:
        print(f"  {v}")
    sys.exit(1)

print("NO DIRECT TOOL EXEC: pass (playwright/harbor spawned only inside "
      f"{sorted(ALLOWED_FUNCS)})")
PYEOF
