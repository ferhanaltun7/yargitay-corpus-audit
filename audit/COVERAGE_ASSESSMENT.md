# Coverage Assessment — 2016–2026

This note evaluates whether the full-corpus audit shows obvious structural coverage gaps in the project's primary 2016–2026 window.

## Year totals

| Year | Decisions | Active court labels |
|---|---:|---:|
| 2016 | 654,309 | 50 |
| 2017 | 628,788 | 50 |
| 2018 | 511,482 | 44 |
| 2019 | 523,722 | 44 |
| 2020 | 445,968 | 43 |
| 2021 | 481,139 | 36 |
| 2022 | 355,551 | 28 |
| 2023 | 264,489 | 28 |
| 2024 | 298,654 | 27 |
| 2025 | 313,478 | 27 |
| 2026 | 36,496 | 26 |

2026 is an incomplete calendar year at the audit date and must not be compared as a completed annual total.

## Internal-gap check

A court-year was flagged if:
- the same court had at least 1,000 decisions in the previous year,
- zero decisions in the current year,
- and at least 1,000 decisions in the following year.

**Result: 0 suspicious one-year internal gaps for 2017–2024.**

This does not prove census completeness against the official source, but it provides no evidence of a simple missing-year ingestion failure in the main 2016–2025 window.

## Interpretation

- The main 2016–2025 period is temporally continuous at corpus level.
- The number of active court labels declines gradually rather than through isolated missing-year holes.
- Pre-2006 coverage is sparse and should not be described as census-like without separate historical-source validation.
- The 2016–2026 project window remains the priority for acceptance testing.

## Gate

**Coverage continuity gate: PASS for obvious internal missing-year failures in 2016–2025.**

This gate is separate from official-source completeness testing.
