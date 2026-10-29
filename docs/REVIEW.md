# Application 1.2 implementation review — 26 October 2026

The approved plan is implemented. The buyer-facing model remains the frozen latest-price replay; no experimental model was promoted.

| Planned improvement | Implemented behavior |
| --- | --- |
| Preserve corrected data during outages | Collection writes reviewed candidates separately. Previous corrections remain applied even if primary retrieval fails. Approved datasets are immutable, hash-verified and selected by one explicit pointer. |
| Isolate model outputs | Training writes isolated experiment directories. The API and builder load a verified immutable release. Interrupted fitting, sealing or builds preserve the active release/site. |
| Exact business arithmetic | Python Decimal and vendored decimal.js implement half-up cent rounding, six-decimal prices, line-summed basket totals and outward interval bounds. New contracts use schema 1.1, a calculation version and mb3 IDs; legacy values/IDs remain intact. |
| Complete record/export validation | Shared fixtures enforce dates, metadata, market/currency, quantities, line sums and export fields in both languages. Every CSV text cell is formula-protected. |
| Safe multi-tab storage | IndexedDB read/write transactions merge against current stored records. Broadcast notifications refresh other tabs. Legacy storage migrates without deleting its original value. |
| Explicit backend and recovery | Runtime configuration selects API or browser storage. API outages do not change the backend. Damaged legacy data can be exported exactly, then recovered/archived explicitly. Backups export in restorable batches. |
| Better interaction | Fractional cost amounts display to cents. Charts support keyboard/touch inspection and full data tables. Coverage wording identifies the fixed reference basket. |
| Bounded new research | Six chronological folds evaluate 20 fixed candidates, including EWMA and shrinkage blends. All qualifying candidates are considered before selection. Joint interval methods, quarterly/volatility diagnostics, block uncertainty, frozen protocols and final model files are retained. |
| Honest research presentation | The lowest observed development error improved 6.60%, below the 10% guard, with a gain interval including no improvement. Neither interval method met the coverage floor. The app shows a separate research-only comparison; previous 2025/early-2026 outcomes are marked exploratory. |
| Complete handoff | Updated documentation, original evaluation, five-page research report, two-page summary, source/model artifacts, tests and private app downloads. |

**Verification:** 98 Python tests, 40 JavaScript tests, and browser checks for both editions pass. See [validation evidence](VALIDATION.md) and the [research report](RESEARCH_REPORT.md).

**Remaining evidence dependencies:** a continuous recent audited source history, fuller primary-source audit (especially 2022), upstream source-rights confirmation, and a prospective buyer trial. The new study does not establish savings or justify promotion without new uninspected outcomes.

---

# Previous application 1.1 review — retained historical record

Release 1.1.0 reviews the data pipeline, forecasting contract, experiments, local API, browser calculator, saved records, exports, deployment and handoff. It implements the corrections below and retains the existing experiment rather than optimizing against already inspected test outcomes.

## Corrections implemented

| Finding | Why it mattered | Correction and evidence |
| --- | --- | --- |
| A saved API basket could be compared against a different source snapshot | A later correction could change labels while a saved plan still appeared to have a valid comparison | API and browser comparisons now withhold outcomes on a source-hash mismatch. Original saved estimates remain intact. Regression tests cover the mismatch. |
| Browser and Python exports used different contract IDs | The same plan could acquire unrelated identifiers depending on where it was exported | A shared, versioned input encoding now produces identical IDs in Python and JavaScript. It normalizes numeric inputs, ignores export timestamps and distinguishes replay from current mode. Legacy IDs are preserved when restoring records. Twenty varied baskets verify cross-language agreement. |
| Backups could be exported but not restored | A user could not recover saved work on a new device | Added validated JSON restoration to browser storage and SQLite, including single-record JSON exports. Duplicate IDs are skipped only when the records agree; conflicting or invalid records reject the whole import. SQL transactions and staged browser merges prevent partial restores. |
| Malformed browser storage could be silently discarded | A later save could overwrite data that failed to load | Corrupt storage is retained, a visible warning appears, and writes are paused. Export retrieves the original stored value for recovery. Browser QA verifies that the original value is not overwritten. |
| Blank quantity fields silently meant zero | Clearing a field could accidentally remove a vegetable while still showing an actionable estimate | Every quantity now needs an explicit number. Use 0 intentionally to omit a vegetable. Invalid input pauses the displayed estimate and disables save/export. |
| Secondary text was faint | Source dates, field units, chart labels and explanatory text were harder to read | Darkened the main secondary-text palette while retaining the visual hierarchy. The revised foreground/background combinations exceed 4.5:1 for the checked white/off-white surfaces. This is a targeted contrast improvement, not a claim of full accessibility certification. |
| Current-day checks used UTC | Sri Lanka's local day starts before the UTC day, causing a valid local-day contract to be withheld | Current mode now uses Asia/Colombo. A regression test checks an instant after Sri Lankan midnight but before UTC midnight. |
| Source files were written directly, and orphaned files could acquire new manifests | Interrupted writes could leave incomplete files that later appeared verified | Downloads use a temporary file and atomic replacement. Existing cache entries require a matching URL, hash and byte count; missing provenance fails closed. Permanent 404s are not retried. Tests simulate disk failure, changed bytes and changed URLs. |
| Some real CBSL link variants were missed | Revised `_e_0.pdf` filenames could be ignored by discovery | Recognize linked numeric-suffix English report variants and skip impossible filename dates. Parsing still validates the printed report date and table. |
| Weather candidate availability inspected all experiment periods | Test-period missingness could influence the development candidate set | Weather candidates now depend only on training/development availability. Later comparisons follow a fixed common complete-input rule, with exclusions reported. Held-out missingness cannot change the candidate-eligibility decision. |
| Tuning intervals used calibration residuals from later dates | A retrospective range could look available before its calibration data existed | Removed those tuning-period intervals. Point-error selection remains development-only; calibrated ranges are evaluated only on the later test/check periods. |
| Artifact versions omitted feature code, splits and dependency versions | Changes to the implementation could reuse the same model identifier | Artifact fingerprints now include code hashes, feature declarations, split definitions, application version and modelling library versions, in addition to the retained input hash. |
| PDF downloads needed a manual packaging step | Rebuilding a distribution could leave old or missing reports on the hosted app | Packaging now copies both reports and the project checksum manifest into the published download folder automatically. |

## Verification and numerical impact

- **49 Python tests and 10 JavaScript tests pass.** The suite adds backup round trips, rollback, source-version mismatch, cache integrity, timezone behavior and exact cross-language contract identity.
- Browser checks pass against the SQLite API and the static browser-storage edition. They cover backup restoration, duplicate imports, persistence after reload, corrupted storage, ordinary planning, saving and exporting, and all five views at six widths from 320 to 1440 px.
- Raw retained source hashes and byte counts were verified. No new observations were appended and no source values were changed in this review.
- Development comparison scores, model-selection inputs, 2025/early-2026 errors and later-period interval results are numerically identical to the first release. The selected method remains the latest-price baseline. Removing the retrospective tuning ranges does not change the actual selection or held-out results.

## Highest-value remaining improvements

1. **Make the evidence current.** Confirm upstream price-source training and redistribution terms, then audit and append continuous recent reports. A single recent bulletin is insufficient to establish a continuous feed. Preserve the source review gate and current-day contract requirement. This remains historical replay through 10 March 2026.
2. **Finish the primary-source audit.** The 2022 sample is still unverified and the existing fifteen primary quotes cover only a small fraction of the archive. Obtain valid archive links and review all unresolved discrepancies, layout periods and anomalies before broad operational use.
3. **Test with an actual buyer.** Validate that a weekly-average target matches their buying schedule. Compare prospective, timestamped forecasts with the buyer's existing method and later benchmarks; use consented invoices separately for delivered-cost analysis. Agree a tolerable rupee error and range width.
4. **Run a newly frozen modelling experiment on new evidence.** The present rule checks the single best basket-error candidate against a commodity guard and otherwise retains the baseline. A future study could choose among all guard-passing candidates, tune ratio/volatility features and test alternative joint interval calibration. The already inspected 2025 and early-2026 results cannot serve as fresh confirmation for those choices. Record a new protocol and reserve new chronological outcomes first.
5. **Pilot operations before broader hosting.** The current service binds to loopback and the private hosted edition uses browser storage. Multi-user identity, centralized persistence, scheduled collection, release approval/rollback and monitoring should follow a real pilot's needs. None are implied by the static demonstration.

These remaining items require source access, rights clarification or prospective evidence. This release does not claim a live feed, completed pilot, forecast accuracy gains or verified savings.
