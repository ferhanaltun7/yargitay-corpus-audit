# Yargıtay Corpus Audit

Reproducible Data Acceptance Audit for the Yargıtay subset of `hamzabagirsakci/turkish-court-decisions`.

## Scope

- Expected Yargıtay decisions: **9,820,145**
- Reported coverage: **1997–2026**
- Expected Yargıtay Parquet shards: **17**
- Full corpus: **11,045,085** decisions
- License label: **CC0-1.0**

This repository does **not** commit the multi-GB raw corpus. It pins the upstream source, downloads Yargıtay shards locally, verifies them and runs a reproducible acceptance audit.

## Acceptance states

- `ACCEPT`
- `ACCEPT_WITH_CONDITIONS`
- `REJECT`

Production embedding/indexing should not begin before the acceptance decision.

## Quick start

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/download_yargitay.py --one-shard
python scripts/verify_source.py
python scripts/structural_audit.py
python scripts/duplicate_audit.py
python scripts/coverage_audit.py
python scripts/sample_verification.py --n 1000
```

To download all Yargıtay shards:

```powershell
python scripts/download_yargitay.py
```

`data/raw/` is immutable input and is ignored by Git.
