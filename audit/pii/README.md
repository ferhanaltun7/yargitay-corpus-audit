# PII / KVKK Direct-Identifier Screening — V2

Validated corrected run: **pii_direct_identifier_gate_v2**

Source revision: `4df66ee63c4adbcae8434787718c7b42381a69dd`

## Aggregate screening results

- Rows scanned: **9,820,145**
- Rows with dataset-provided masking: **4,350 (0.0443%)**
- Dataset masked occurrences (`masked_count` sum): **7,400**
- Unmasked TR IBAN-pattern rows: **0 (0.000000%)**
- Unmasked email-pattern rows: **219 (0.002230%)**
- Unmasked Turkish-mobile-pattern rows: **1,257 (0.012800%)**
- Labeled TCKN-like 11-digit rows: **96 (0.000978%)**
- Labeled card-number-like rows: **387 (0.003941%)**

Dataset mask tokens observed in the corrected run include:
- `[TCKN]`: **1,829 rows**
- `[IBAN]`: **63 rows**
- `[TELEFON]`: **1,974 rows**
- `[EPOSTA]`: **345 rows**
- `[KART]`: **208 rows**

## Interpretation

This is a **screening signal**, not a legal determination that every regex hit is a real personal identifier. False positives are possible.

However, because non-zero unmasked direct-identifier signals remain, the raw corpus must **not** be treated as production-safe solely because the upstream dataset performs masking.

**PII direct-identifier gate: ACCEPT WITH CONDITION — run an independent sanitization layer before production indexing or redistribution.**

A separate contextual/NER audit remains required for names, addresses, health data, minors, victim/suspect identities and other context-dependent personal data.

No matched identifier values or text snippets are committed to this public repository.

## Provenance

GitHub Actions run: `35439663251`

Artifact: `pii-direct-identifier-screening`, artifact id `10583860133`

The run completed the PII audit and artifact upload successfully; only its final git commit step failed due to a concurrent branch update. This README records the validated V2 aggregate output recovered from that artifact.
