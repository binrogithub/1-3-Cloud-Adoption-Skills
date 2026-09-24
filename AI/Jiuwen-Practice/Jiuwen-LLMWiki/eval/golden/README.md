# Golden set (AG-1 / E13-S4) — 150 SA-written questions + 20 unanswerable

`golden.csv` format: `lang,question,expected_slug(optional),unanswerable(0|1)`.

Status: **bootstrap starter only** (12 questions, machine-written). The acceptance
gate needs the SA-written set: 50 EN / 50 ES / 50 PT-BR from the 15 pilot SAs (E14),
plus 20 deliberately unanswerable questions. SA authorship cannot be faked by the
platform team — that is the point of the gate.

Run once seeded: `python3 eval/run_golden.py --config llmwiki.toml` (bar: correct and
cited >= 85%, abstention on unanswerable >= 90%, 0 fabricated prices/URLs served).
