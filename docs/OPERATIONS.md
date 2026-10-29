# Operational handoff

## Current release

Private historical research replay. Data through 10 March 2026; no unattended collector is installed. Local API binds to loopback and has no multi-user authentication. Static hosting has no server-side Python or SQLite. IndexedDB transactions synchronize saves across tabs on the same browser; devices exchange explicit backups. Browsers perform only basket/scenario arithmetic on frozen, versioned model outputs.

## Data review

Successful source responses are cached with SHA-256, URL, byte count and acquisition time. The acquisition time is not the original historical publication time. Raw originals are not overwritten on a normal rerun. Canonical records preserve `original_price` and correction source. July 2024 corrections are independently recoverable from the primary PDF table.

Preparation now stages candidates without changing approved inputs. Source failures retain reviewed corrections. Dataset approval validates complete tables and records correction evidence hashes in an immutable approved directory. The review queue is an append-only attempt log, including initial parser failures later resolved by the strict parser update. Use `source_audit.json` to identify successful final parses. Two attempted June 2022 samples returned 404; the 2022 audit is unresolved. Do not interpret a working parser as evidence that every historical layout is supported.

## Move to a live pilot

1. Establish permitted training and redistribution use of upstream price figures. Record the decision separately from the package's GPL metadata.
2. Recruit one caterer/canteen and confirm that buying across a week fits the target. Fixed-date bulk buying needs a different target and a new experiment.
3. Stage CBSL report links via the collector. Inspect complete continuous recent history, missing periods, units, market/type columns and outliers; preserve source evidence. Never splice retail narrative or HARTI ranges into point-price labels.
4. Merge reviewed observations under a new source manifest. If weather is unavailable, use only the already evaluated price-only branch. A new learned-model feature set requires new chronological selection and calibration.
5. Freeze configuration, train cutoff and feature definitions. Run tests, time-ordered evaluation and joint interval checks. Record model and source versions. Keep a rollback copy of the prior artifacts.
6. Release new issue-date contracts only when every required quote is at most three calendar days old. The implemented current-mode API also requires today's contract. Model age and unusual regimes require review beyond this input-age gate.
7. Schedule collection externally only after the source path is approved. A cron example is `0 13 * * 1-5 cd /absolute/MarketBudget && .venv/bin/python -m marketbudget.ingest refresh`. This stages inputs; it does not approve, train or publish them. Adjust timezone and report-availability timing to actual operations.
8. For four to eight weeks, save prospective forecasts before outcomes arrive. Compare against published benchmarks and the buyer's own prior budgeting method. Collect invoices only with consent, remove supplier/customer personal details and keep paid-cost assessment separate.

## Recovery

Source failure: retain last evidence and stage an error; withhold a current forecast if price freshness fails. Parser failure: keep the PDF in the review workflow; do not use page-one retail prose. Corrupt snapshot: restore a previously validated immutable release and matching manifest. API reads validate the approved bundle; a failed digest produces 503. No research artifact is a fallback. Clear browser cache when replacing the static snapshot, then verify model version. Missing outcomes: record unavailable, never zero error. Source mismatch: preserve the saved estimate and withhold comparison against changed labels. Database backup: stop the local API before copying SQLite, or use SQLite's backup command; WAL companion files can hold uncheckpointed transactions.

Portable recovery: use Saved baskets → Export backup, then Restore backup on the target app. Complete backups and single-record JSON exports are accepted by the browser; full backups can also be posted to `/api/v1/baskets/import`. Imports validate dates, amounts, quantities, line totals and provenance before writing. Identical duplicate IDs are skipped; conflicts abort the entire import. Damaged browser storage remains untouched and can be exported as its original value; use Recover saved data to keep valid plans and archive the exact original. The legacy localStorage value is retained after migration/recovery. Restoring records does not recalculate or silently update their historical source version.

## Verification

`make test` runs the numerical/data/API suite and the browser arithmetic suite. `node scripts/browser_qa.cjs` runs optional Playwright browser checks against a running app; install the optional QA dependency first. Report-generation dependencies are optional and separate from runtime. See `scripts/make_reports.py` for reproducible Markdown and PDF outputs.

## Data minimization

This release stores basket names, quantities and forecast records. It has no invoice upload, external analytics, customer records, supplier messaging, demand model or automated ordering. Avoid personal information in basket names. Export a backup before clearing browser storage or deleting local records.


## Release 1.2 boundaries

- `data/approved.json` selects an immutable, hash-verified dataset. `artifacts/approved.json` independently selects the approved forecast bundle. Neither training nor research changes these pointers.
- Original-experiment reruns write `artifacts/experiments/<run>/`; frozen new studies write `reports/research/<run>/`. Review outputs before any explicit promotion. The new study has promotion disabled and fails its point-improvement and interval-coverage guards.
- `GET /runtime.json` fixes API versus browser storage for the page. Runtime/snapshot failures show a retry state; they do not hide SQLite records by switching storage.
- New contract schema 1.1 records `decimal_half_up_v1`. Line amounts round half-up to cents, totals sum rounded lines, and ranges round outward. Legacy schema 1.0 records are validated and retained without recalculation.
- The builder validates an entire staging directory before replacing dist, with rollback on replacement failure. Packaging exports only completed artifacts; user databases, Git history, caches and hosting credentials are excluded.
- Browser backup batches contain at most 500 records and stay below 5 MB. Select an export batch when the collection is larger. Duplicate IDs are skipped only for identical records; conflicts abort an entire import.
