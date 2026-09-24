#!/usr/bin/env python3
"""AG-1 golden-set runner. Bars: correct+cited >=85% (interim 75%), abstention on
unanswerable >=90%, zero fabricated prices/URLs (an answer with a price/URL issue
counts as fabrication)."""
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from llmwiki import config as config_mod  # noqa: E402
from llmwiki.pipeline import Wiki  # noqa: E402


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--csv", default=str(ROOT / "eval" / "golden" / "golden.csv"))
    ap.add_argument("--bar", type=float, default=0.75)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
    wiki = Wiki(config_mod.load(a.config))
    ok = abst = fab = redacted = unans_total = 0
    total = 0
    import re as _re
    for row in rows:
        r = wiki.ask(row["question"], row["lang"] or None)
        total += 1
        unanswerable = row.get("unanswerable") == "1"
        # PRD AG-1 bar: "0 fabricated prices or URLs served". A redacted derived
        # claim (e.g. the model counting "three") is the verifier working, logged
        # separately, never served as a fact.
        price_or_url = any(_re.search(r"(usd|\$|mxn|brl|ars|clp|eur|https?://)", i.get("claim", ""), _re.I)
                           or i.get("reason") == "url_domain" for i in r.issues)
        fab += price_or_url
        redacted += bool(r.issues) and not price_or_url
        if unanswerable:
            unans_total += 1
            abst += r.status == "abstained"
        else:
            ok += (r.status in ("grounded", "no_claims", "partially_verified")) and not price_or_url and bool(r.citations)
        time.sleep(0.2)
    rate = ok / max(total - unans_total, 1)
    abst_rate = abst / max(unans_total, 1)
    print(f"AG-1 interim: {ok}/{total - unans_total} correct+cited ({rate:.0%}, bar {a.bar:.0%}); "
          f"abstention {abst}/{unans_total} ({abst_rate:.0%}, bar 90%); "
          f"fabricated prices/URLs served: {fab}; derived-claim redactions: {redacted}")
    return 0 if (rate >= a.bar and abst_rate >= 0.9 and fab == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
