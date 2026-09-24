# Source onboarding list (E12-S3, RK-7 licence decisions)

Every L1 source needs a licence decision BEFORE ingest. Current state:

| Priority | Source | Type | Licence | Status |
|---|---|---|---|---|
| P0 | Huawei Cloud international documentation (support.huaweicloud.com/intl) | crawlable docs | public | **blocked**: portal is client-rendered; agree a static export or API with the docs team |
| P0 | Huawei Cloud price pages (www.huaweicloud.com/intl/en-us/price) | price tables | public | blocked same way; pricing/ namespace stays empty until pulled |
| P1 | LATAM region/service matrix (OQ-1) | structured export | internal | waiting on LATAM product team; wiki/regions.json stays empty by design |
| P1 | Huawei Cloud compliance attestations (www.huaweicloud.com compliance pages) | docs | public | pull after docs export agreement |
| P2 | SA notes / RFP answers (internal) | note sets | internal | opt-in per set; owner required |
| P3 | Customer-adjacent material | any | **confidential** | only with explicit designation; filtered pre-retrieval (GL-S2) |

Rules:
- `licence` is set at ingest and immutable afterwards (records are content-addressed).
- Confidential sources must never reach the embedding endpoint of an external provider
  (ours is self-hosted, ADR-001 — NFR-7 satisfied).
- Legal review of crawled-doc licensing (RK-7) is a launch gate for M1 scale-up.
