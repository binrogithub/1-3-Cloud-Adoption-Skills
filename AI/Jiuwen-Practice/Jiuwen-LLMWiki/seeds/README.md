# Seed sources (E12-S4 bootstrap batch)

Each file here is ingested as an L1 source (`llmwiki ingest <file> --compile`) and
compiled into pages **through the real pipeline** (role → mechanical validation →
human approve). They exist to exercise and evidence the pipeline end to end.

Provenance: bootstrap digests written 2026-09-24 from public Huawei Cloud
documentation knowledge, kept deliberately to facts that are stable and verifiable.
They are NOT curator-pulled snapshots. Before the pilot (E14), a curator must replace
them with real document pulls (docs/SOURCES.md) and re-compile.

Deliberate exclusions: no pricing numbers (pricing/ stays empty until real price
pages are pulled), no AZ counts (waiting on the authoritative region source, OQ-1).
