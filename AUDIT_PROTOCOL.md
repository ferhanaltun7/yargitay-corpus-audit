# Data Acceptance Audit v1

## Hard gates

1. Structural integrity
2. Decision-document validity
3. Truncation / malformed-text analysis
4. Year × chamber coverage
5. Independent official-source verification
6. Cross-corpus overlap
7. Provenance integrity
8. PII/KVKK review
9. Retrieval pilot only after data acceptance

## Default targets

| Metric | Target |
|---|---:|
| Metadata accuracy | >= 99.5% |
| Valid decision documents | >= 99.5% |
| Useful/full text | >= 99% |
| Exact duplicate excess | < 0.1% |
| Near duplicate excess | < 1% |
| Critical coverage gap | none |
| Official-source sample verification | >= 99% |

Final state must be exactly one of: `ACCEPT`, `ACCEPT_WITH_CONDITIONS`, `REJECT`.
