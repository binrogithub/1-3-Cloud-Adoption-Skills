#!python3.12
"""tests/collapse/records_tool — mint the plane's signed records.

The caller (plan.py / report.py) reads the spec surface only from
signed records under AI_DLC_RECORDS (containment PRD §8); it never
executes openspec. A test therefore stands in for the plane: it writes
the graph record a graph dispatch would produce and the verdict records
a validate dispatch would produce, each signed with the same HMAC the
runtime verifies — the fixture path is the dispatch path's shape, so a
green test says the caller really does read records and nothing else.

Usage (AI_DLC_RECORDS and AI_DLC_VERDICT_KEY decide where things land;
both are set by the test to its own temp dirs):
  records_tool.py key
      create the HMAC key file if it does not exist

  records_tool.py graph CHANGE --schema S --artifacts-json JSON
      sign one graph record: artifacts = [{id, requires, conditional,
      conditions}, ...] (defaults: requires [], conditional false,
      conditions [])

  records_tool.py status CHANGE --artifacts id=state,...
      [--complete true|false]
      sign one status record — what a status dispatch produces

  records_tool.py verdict CHANGE [--rc N] [--stdout TEXT]
      [--artifacts id=state,...] [--complete true|false]
      [--status-json JSON]
      sign one validate verdict, newest wins. --artifacts/--complete
      also mint the matching status record (the two dispatches a round
      really runs, in one fixture call).
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent
                       / "bin"))
import report  # noqa: E402  (the runtime's own signing/reading layer)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="verb", required=True)
    sub.add_parser("key")
    g = sub.add_parser("graph")
    g.add_argument("change")
    g.add_argument("--schema", required=True)
    g.add_argument("--artifacts-json", required=True,
                   help='[{"id": "proposal", "requires": [], '
                        '"conditional": false, "conditions": []}]')
    st = sub.add_parser("status")
    st.add_argument("change")
    st.add_argument("--artifacts", default="",
                    help="id=state pairs, comma separated")
    st.add_argument("--complete", default=None)
    v = sub.add_parser("verdict")
    v.add_argument("change")
    v.add_argument("--rc", type=int, default=0)
    v.add_argument("--stdout", default="")
    v.add_argument("--artifacts", default="",
                   help="id=state pairs, comma separated — also mints "
                         "the matching status record")
    v.add_argument("--complete", default=None)
    v.add_argument("--status-json", default=None)
    args = ap.parse_args()

    key_path = Path(os.environ["AI_DLC_VERDICT_KEY"])
    if args.verb == "key":
        if not key_path.is_file():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(os.urandom(32))
        return 0

    def states_from(arg: str) -> dict:
        out = {}
        for pair in filter(None, arg.split(",")):
            k, _, val = pair.partition("=")
            out[k.strip()] = val.strip() or "unknown"
        return out

    def mint(record: dict, prefix: str) -> None:
        report.write_record(args.change, prefix, record)

    if args.verb == "graph":
        arts = [{"id": a["id"],
                 "requires": list(a.get("requires", [])),
                 "conditional": bool(a.get("conditional", False)),
                 "conditions": list(a.get("conditions", []))}
                for a in json.loads(args.artifacts_json)]
        mint({"verb": "graph", "schema": args.schema,
              "change": args.change, "artifacts": arts,
              "produced_at": report.now_iso(), "session": "fixture"},
             "graph")
    elif args.verb == "status":
        mint({"verb": "status", "change": args.change,
              "argv": ["status", "--json", "--change", args.change],
              "artifacts": states_from(args.artifacts),
              "is_planning_complete": args.complete == "true",
              "ts": report.now_iso(), "session": "fixture"}, "status")
    else:
        if args.status_json is not None:
            status = json.loads(args.status_json)
        else:
            status = {"artifacts": states_from(args.artifacts),
                      "is_planning_complete": args.complete == "true"}
            if not status["artifacts"] and args.complete is None:
                status = {}
        if status:
            # the status dispatch a round also runs, minted alongside
            mint({"verb": "status", "change": args.change,
                  "argv": ["status", "--json", "--change", args.change],
                  "artifacts": status.get("artifacts") or {},
                  "is_planning_complete":
                      bool(status.get("is_planning_complete")),
                  "ts": report.now_iso(), "session": "fixture"},
                 "status")
        mint({"verb": "validate",
              "argv": ["validate", args.change, "--strict", "--json"],
              "rc": args.rc, "stdout": args.stdout,
              "sha256": hashlib.sha256(
                  args.stdout.encode("utf-8")).hexdigest(),
              "change": args.change, "ts": report.now_iso(),
              "session": "fixture"}, "verdict")
    print(json.dumps({"wrote": args.verb, "change": args.change}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
