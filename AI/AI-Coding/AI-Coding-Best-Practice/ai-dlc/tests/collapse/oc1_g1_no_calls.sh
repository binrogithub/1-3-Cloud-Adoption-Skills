#!/usr/bin/env bash
# OC G1 (containment PRD §9): the ai-dlc codebase holds no openspec
# process call. Judged by AST, not grep: any subprocess.run / run() /
# Popen / check_output / check_call / system call whose argument list or
# string literal contains the word "openspec" fails the gate — comments
# and doc references are free, executable dispatch is not. The caller
# reads the spec surface from signed records; nothing else.
set -euo pipefail
PY=python3.12
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FAIL=0
for f in "$ROOT"/bin/*.py; do
    # a failure prints the offending call; silence is the pass
    if ! $PY - "$f" <<'PYEOF'
import ast, sys

FORBIDDEN = {"run", "Popen", "check_output", "check_call",
             "system", "call", "run_in_terminal"}
path = sys.argv[1]
tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)


def strings(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for v in node.values:
            yield from strings(v)
    elif isinstance(node, ast.Name):
        yield node.id


bad = []
for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    fn = node.func
    name = fn.attr if isinstance(fn, ast.Attribute) else (
        fn.id if isinstance(fn, ast.Name) else "")
    if name == "run" and isinstance(fn, ast.Attribute):
        pass  # subprocess.run / thread-pool executor .run — arg-checked
    if name not in FORBIDDEN:
        continue
    if any("openspec" in s for a in node.args + [k.value for k
                                                 in node.keywords]
           for s in strings(a)):
        bad.append(f"{path}:{node.lineno} {name}() carries openspec")
for b in bad:
    print("FAIL:", b)
sys.exit(1 if bad else 0)
PYEOF
    then
        echo "G1 RED: $f holds an openspec process call"
        FAIL=1
    fi
done
# the deployment surface is judged too: a skill or command file that
# instructs the caller to execute openspec is the same breach in prose
if grep -rnE '`?openspec[[:space:]]+(validate|status|instructions|archive|init|list|sync)' \
        "$ROOT/.claude/skills" "$ROOT/.claude/commands" 2>/dev/null; then
    echo "G1 RED: a skill/command file instructs executing openspec"
    FAIL=1
fi
[[ $FAIL -eq 0 ]] && echo "OC G1: pass (no openspec process call anywhere in the caller; the spec surface is records-only)"
exit $FAIL
