# Validation evidence — application 1.2.0

Verified on 26 October 2026 with Python 3.12, Node.js 24 and Chromium.

| Check | Result |
| --- | --- |
| `python -m pytest -q` | **98 passed** |
| `node --test tests/*.test.mjs` | **40 passed** |
| `python -m compileall -q marketbudget scripts` | Passed |
| API / SQLite browser verification | Passed |
| Static / IndexedDB browser verification | Passed |
| Five views at 320, 390, 680, 820, 1024 and 1440 px | No document horizontal overflow |
| Approved snapshot integrity | Original bytes and model preserved |
| Technical report / project summary / research report | 6 / exactly 2 / 5 pages |

The shared Python/JavaScript fixtures cover complete current and legacy records, missing export fields, invalid timestamps, currency/market mismatches, line metadata and amount inconsistencies. Decimal boundary cases, including 0.0015 kg beans at LKR 290/kg, agree exactly at LKR 0.44; basket totals equal rounded line amounts and interval bounds round outward. Legacy records retain original amounts and identifiers.

Data/release tests simulate unavailable primary audit evidence, changed source bytes, missing provenance, interrupted model fitting, interrupted approval and failed builds. Approved corrections, release pointers and the previously built site remain intact. API runtime configuration identifies storage explicitly, and its snapshot bytes match the published digest. Corrupt releases return 503; research files cannot become a fallback.

Browser tests cover saving and historical comparisons, backup restoration, duplicate detection, persistence after reload, blank input handling, budget warnings, CSV exports, simultaneous two-tab saves, non-destructive legacy migration, exact export of damaged data, explicit recovery/archiving, and 501-record export batches. API failures do not switch storage. A successful save followed by a failed list refresh is acknowledged without prompting another save.

Charts have one keyboard-controlled observation selector, arrow-key date/series navigation, touch inspection and a complete accessible table. The approved 2025 chart exposes all 201 outcomes without 402 separate circle tab stops. A separate research panel exposes the new study's candidates and failed guards.

Research tests check chronological folds and purges, as-of EWMA invariance, selection among all guard-passing candidates, insufficient calibration, a perfect zero-error baseline, joint-residual dependence, protocol hashes and all 24 final research model digests. The executed six-fold study used 300 development baskets and 20 candidates. Best observed gain was 6.60% (95% block interval −2.84% to 15.72%); no learned model cleared the 10% guard. Relative/additive nominal-80% development coverage was 71.67%/67.67%, below the 75% floor. Promotion remains disabled. Previously inspected 2025/early-2026 checks are exploratory.

A successful isolated reproduction of the original training run produced exactly the same evaluation metrics and intervals, while leaving the approved release untouched. The original approved latest-price model and its historical evaluation remain unchanged: 201 complete 2025 baskets, LKR 2,674.05 MAE and 78.11% observed nominal-80% coverage. The new business arithmetic is explicitly versioned separately from those unrounded research calculations. No new source observations, pilot results or verified savings are claimed.

Machine-readable browser evidence and screenshots are in reports/. Frozen protocol, per-date development predictions, model artifacts and confidence intervals are in reports/research/. A FastAPI/Starlette test-client deprecation warning is emitted by the pinned HTTPX combination; assertions and actual service/browser checks pass.
