# Acceptance Decision Matrix v1

The final corpus decision is one of:

- **ACCEPT**
- **ACCEPT_WITH_CONDITIONS**
- **REJECT**

## Evidence gates

| Gate | Evidence | PASS criterion | Current state |
|---|---|---|---|
| Source integrity | `audit/full_corpus/source_verification.json` | 17/17 size + SHA-256 match | PASS |
| Row/schema integrity | `audit/full_corpus/full_corpus_summary.json` | 9,820,145 rows; identical shard schema | PASS |
| Required fields | same | no empty core metadata/text fields | PASS |
| Exact duplication | same | zero excess ID/document/hash/metadata duplicates | PASS |
| Text structural quality | same | empty text = 0; severe-short-text rate controlled | PASS |
| 2016–2025 continuity | `audit/COVERAGE_ASSESSMENT.md` | no unexplained one-year internal gaps | PASS |
| Official anomaly check | `audit/phase2_official_probe/` | suspicious rows trace back to official source | PASS (12/12 probe) |
| Stratified official validation | `audit/phase2_stratified_100/` | >=95 retrieved; metadata >=99%; text differences explainable | PENDING |
| Official searchable census | `audit/bedesten_year_totals/` | corpus/official differences quantified and explainable | PENDING |
| Direct identifier screening | `audit/pii/` | unmasked direct identifiers quantified; mitigation defined | PENDING |
| Contextual PII/NER | future audit | names/addresses/health/contextual identifiers assessed | PENDING |
| Cross-corpus overlap | future audit | prior corpus A vs candidate B overlap/delta explained | PENDING |

## Decision rules

### ACCEPT

Requires:
1. All hard structural gates PASS.
2. Stratified official-source validation PASS.
3. No unexplained material coverage deficit in the project's 2016–2026 window.
4. PII risks have a reproducible sanitization policy before production indexing.
5. Provenance remains pinned to immutable hashes/revision.

### ACCEPT_WITH_CONDITIONS

Use when the core corpus is authentic and structurally sound but one or more bounded issues remain, such as:
- historical pre-2006 coverage is sparse,
- a defined subset requires exclusion/remediation,
- PII sanitization must run before indexing,
- completeness is strong for 2016–2026 but not defensible for the entire historical range.

### REJECT

Use if any material hard failure is found:
- source hashes/provenance cannot be reproduced,
- systematic metadata/text mismatches against official sources,
- unexplained large coverage holes in the target window,
- material corruption/duplication/truncation that cannot be isolated.

## Important scope distinction

An **ACCEPT** decision means acceptable as the project's canonical raw Yargıtay corpus under the audited scope. It does **not** mean:
- every Yargıtay decision ever issued is publicly searchable,
- every historical year is census-complete,
- raw text is automatically safe for public redistribution or production indexing without PII controls.
