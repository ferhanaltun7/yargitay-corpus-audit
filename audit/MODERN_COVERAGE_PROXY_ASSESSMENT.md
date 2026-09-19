# Modern Coverage Proxy Assessment

## Scope

Comparison of the deduplicated candidate corpus against current Bedesten
`YARGITAYKARARI` year totals returned for the generic term `karar`.

This is a **coverage proxy**, not an assertion that Bedesten's raw `total`
equals the number of unique legal decisions.

A separate semantics probe found that six broad queries
(`karar`, `esas`, `mahkeme`, `karar OR esas`,
`karar OR esas OR mahkeme`, `dosya`) returned the exact same year total
for both 2016 and 2025. This materially strengthens—but does not prove—the
interpretation that these totals approximate the searchable yearly inventory.

## Results

| Period | Candidate | Bedesten query total | Difference | Ratio |
|---|---:|---:|---:|---:|
| 2016–2020 | 2,764,269 | 2,768,553 | 4,284 | **99.8453%** |
| 2021–2022 | 836,690 | 859,914 | 23,224 | **97.2993%** |
| 2023–2025 | 876,621 | 883,957 | 7,336 | **99.1701%** |
| **2016–2025** | **4,477,580** | **4,512,424** | **34,844** | **99.2278%** |

Year-level ratios:

- 2016: **99.9867%**
- 2017: **99.8336%**
- 2018: **99.8456%**
- 2019: **99.8233%**
- 2020: **99.6802%**
- 2021: **98.0783%**
- 2022: **96.2645%**
- 2023: **99.4002%**
- 2024: **99.5049%**
- 2025: **98.6611%**
- 2026 snapshot: **30.1416%**

## Why the raw difference is not automatically "missing decisions"

The candidate dataset explicitly deduplicates decisions using
`(source, court, esas_no, karar_no)` and reports **72,441 duplicate records**
removed across the complete source collection. Bedesten search totals are
document/search-record totals and may include multiple `document_id` values
for the same legal decision.

Therefore:

`Bedesten total - candidate rows`

cannot be interpreted as a missing-decision count without a decision-key audit.

A separate cross-source metadata audit is used to distinguish:
1. alternate document IDs for an already represented decision, from
2. metadata keys genuinely absent from the candidate corpus.

## 2026 must be treated separately

The published dataset's current maximum decision date is **2026-05-06**.
The audit date is 2026-09-19. Therefore the large 2026 difference is expected
for a frozen snapshot and demonstrates that an incremental update layer is
required for current production use.

## Gate assessment

- **2016–2025 continuity:** PASS
- **Modern searchable-inventory proximity:** strong, but decision-level
  completeness remains subject to duplicate reconciliation.
- **2026 currentness:** CONDITION — incremental ingestion after the frozen
  snapshot is mandatory.
- **Historical pre-2006 census completeness:** not established.

Current coverage disposition: **ACCEPT WITH CONDITIONS** pending cross-source
decision-key reconciliation.
