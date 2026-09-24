"""P1-8 codegraph author-side channel — tests.

query: read the graph, not the code — deterministic, local, no session;
a 1..N-hop neighborhood around a file or symbol plus the complement
(what the author need NOT read). brief: every Callers/Callees line
carries (high)/(low) confidence, and the template names the unread
complement.

Run:  python3 -m pytest tests/test_codegraph_query.py -v
"""
import importlib.util
import json
import sys
from pathlib import Path

_BIN = Path(__file__).resolve().parent.parent


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = _load("plan_cg_query_t", _BIN / "bin" / "plan.py")


GRAPH = {
    "nodes": [
        {"id": "src/gate.py", "type": "file", "name": "gate.py",
         "path": "src/gate.py"},
        {"id": "src/report.py", "type": "file", "name": "report.py",
         "path": "src/report.py"},
        {"id": "src/policy.py", "type": "file", "name": "policy.py",
         "path": "src/policy.py"},
        {"id": "docs/readme.md", "type": "document",
         "name": "readme.md", "path": "docs/readme.md"},
        {"id": "fn:checkpoint", "type": "function",
         "name": "checkpoint", "path": "src/gate.py"},
    ],
    "edges": [
        {"source": "src/report.py", "target": "src/gate.py",
         "type": "imports"},
        {"source": "src/gate.py", "target": "src/policy.py",
         "type": "calls"},
        {"source": "fn:checkpoint", "target": "src/policy.py",
         "type": "calls"},
    ],
}


def _repo_with_graph(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    (d / ".ua").mkdir(parents=True, exist_ok=True)
    (d / ".ua" / "knowledge-graph.json").write_text(
        json.dumps(GRAPH), encoding="utf-8")
    return d


def _run(tmp_path, capsys, **kw):
    repo = _repo_with_graph(tmp_path)
    rc = plan.cmd_codegraph_query(repo, kw.get("file"),
                                  kw.get("symbol"), kw.get("hop", 1))
    return rc, json.loads(capsys.readouterr().out)


def test_query_by_file_gives_neighborhood_and_complement(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, file="src/gate.py")
    assert rc == 0 and out["found"] is True
    files = out["neighborhood_files"]
    assert "src/gate.py" in files and "src/report.py" in files \
        and "src/policy.py" in files
    assert "docs/readme.md" not in files
    assert out["graph_nodes_total"] == 5
    assert out["files_not_in_neighborhood"] >= 1
    rel = {n["id"]: n["relation"] for n in out["neighborhood"]}
    assert rel["src/report.py"].startswith("incoming/")
    assert rel["src/policy.py"].startswith("outgoing/")


def test_query_by_symbol(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, symbol="checkpoint")
    assert rc == 0 and out["found"] is True
    assert out["seeds"][0]["id"] == "fn:checkpoint"
    assert "src/policy.py" in out["neighborhood_files"]


def test_query_two_hops_reaches_farther(tmp_path, capsys):
    rc, one = _run(tmp_path, capsys, file="src/report.py", hop=1)
    assert "src/policy.py" not in one["neighborhood_files"]
    rc, two = _run(tmp_path, capsys, file="src/report.py", hop=2)
    assert "src/policy.py" in two["neighborhood_files"]


def test_query_no_graph_refuses_with_remedy(tmp_path, capsys):
    rc = plan.cmd_codegraph_query(tmp_path / "empty", "a.py", None, 1)
    out = json.loads(capsys.readouterr().out)
    assert rc != 0
    assert out["refused"] is True
    assert "codegraph build" in out["remedy"]


def test_query_no_match_reports_not_found(tmp_path, capsys):
    rc, out = _run(tmp_path, capsys, symbol="nonexistent")
    assert rc == 0 and out["found"] is False


def test_brief_template_carries_confidence_and_complement():
    src = (_BIN / "bin" / "plan.py").read_text(encoding="utf-8")
    # fragments chosen to sit inside single string literals
    assert "confidence: (high)" in src
    assert ", (low) for a connection" in src
    assert "## Files you need not read" in src
