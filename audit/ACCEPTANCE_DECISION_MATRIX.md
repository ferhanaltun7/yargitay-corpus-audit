# Acceptance Decision Matrix v1

Final corpus decision states:

- **ACCEPT**
- **ACCEPT_WITH_CONDITIONS**
- **REJECT**

## Evidence gates

| Gate | Evidence | Current state |
|---|---|---|
| Source integrity | `audit/full_corpus/source_verification.json` | **PASS** — 17/17 size + SHA-256 match |
| Row/schema integrity | `audit/full_corpus/full_corpus_summary.json` | **PASS** — 9,820,145 rows; identical schema |
| Required fields | same | **PASS** — no empty core metadata/text fields |
| Exact duplication | same | **PASS** — zero excess ID/document/hash/metadata duplicates |
| Text structural quality | same | **PASS** — empty text = 0; severe-short-text rate low |
| 2016–2025 continuity | `audit/MODERN_COVERAGE_PROXY_ASSESSMENT.md` | **PASS** |
| Official anomaly check | `audit/phase2_official_probe/` | **PASS** — 12/12 official retrieval |
| Stratified official validation | `audit/phase2_stratified_100/` | **PASS** — 98/100 retrieved; 98/98 text similarity >=0.95; median 0.999731 |
| Modern searchable-inventory proxy | coverage assessment | **CONDITIONAL PASS** — 2016–2025 ratio 99.2278%; 2026 snapshot incomplete |
| Independent metadata cross-source audit | `audit/cross_source_metadata/` | **CONDITIONAL PASS** — 9,744,523 exact document-ID overlap; residual decision-key differences bounded but non-zero |
| Direct identifier screening/sanitization | `audit/pii_sanitization/` | **RUNNING / REQUIRED BEFORE INDEXING** |
| Contextual PII/NER | future audit | **PENDING** |
| 2026 incremental freshness | update layer | **REQUIRED** |

## Current decision

# **ACCEPT_WITH_CONDITIONS**

The candidate corpus is accepted as the project's canonical raw Yargıtay source **subject to the conditions below**.

### Conditions

1. **Do not treat the frozen 2026 snapshot as current.**
   The published corpus ends at the frozen source snapshot and requires an incremental update layer.

2. **Run direct-identifier sanitization before production indexing.**
   Raw data remains immutable; sanitized derivatives must be reproducible.

3. **Complete contextual PII/NER policy before any public-facing or broadly redistributed index.**
   Names, addresses, health/minor/victim/suspect identifiers are outside the direct-regex layer.

4. **Preserve cross-source reconciliation evidence.**
   The independent metadata corpus contains 83,067 metadata keys absent from the candidate under exact normalized matching; these are investigation candidates, not automatically proven missing legal decisions.

5. **Keep provenance immutable.**
   Production derivatives must retain source revision, shard hash, document ID, metadata key and transformation lineage.

## Why this is not REJECT

No evidence of systematic corruption, fabricated text, duplicate inflation, schema inconsistency, empty-document inflation, or material text mismatch was found. Official-source validation is extremely strong.

## Why this is not unconditional ACCEPT

The remaining issues concern:
- 2026 freshness,
- bounded cross-source completeness uncertainty,
- contextual PII governance.

These are operational/data-governance conditions rather than evidence that the corpus itself is unreliable.
