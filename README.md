# MarketBudget

**A working seven-day vegetable procurement budgeting project for Dambulla, Sri Lanka.** Enter beans, carrots and tomatoes in kilograms, set an optional spending limit, and inspect a dated benchmark estimate with a nominal 80% joint basket range.

This implementation uses recovered real source data. It is an **explicit historical research replay through 10 March 2026**, not a current quotation or a validated live procurement service. A separate 16 October 2026 CBSL reference report is retained for audit and is not spliced across the missing months.

## Start in two minutes

Requires Python 3.11 or newer (tested on 3.12), a current browser, and an internet connection for dependency installation. Approved artifacts and browser assets are already included; startup does not download data or retrain.

```bash
cd MarketBudget
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python scripts/build.py
python -m marketbudget.api
```

Open **http://127.0.0.1:8000**. API documentation is at **http://127.0.0.1:8000/docs**. Baskets persist in `data/marketbudget.sqlite3`. Override its path with `MARKETBUDGET_DB`. Keep the local service bound to loopback: authentication and multi-user hosting are outside this release.

For a dependency-free static demo, run `python -m http.server 8080 --directory dist` and open `http://127.0.0.1:8080`. Static mode saves baskets transactionally in IndexedDB; clearing browser data removes them. Valid legacy browser records migrate automatically while the original value is retained. Two tabs can save independently without overwriting each other. CSV estimates and portable JSON backups are available. Use **Restore backup** in Saved baskets to merge a full backup or an individual exported basket, preserving original records and skipping identical duplicates. Invalid/conflicting backups make no changes. Each import accepts up to 500 records and a 5 MB browser-selected file. Unreadable legacy data is preserved for exact export. Use Recover saved data to retain readable plans and archive the original before continuing. Large collections export in individually restorable batches selected in Saved baskets.

Release **1.2.0** adds immutable approved data/model releases, exact decimal calculations, transactional IndexedDB storage, safe legacy migration and recovery, explicit runtime storage selection, accessible chart controls and a separate six-fold research study. See [implementation review](docs/REVIEW.md) and [research report](docs/RESEARCH_REPORT.md). The approved forecasting model and original historical evaluation remain unchanged.

## What is implemented

- Responsive basket planner, budget headroom, joint uncertainty, price explorer and interactive observed-price charts.
- Historical issue-date selection, explicit planning windows and source dates; current mode withholds stale contracts.
- Saved baskets, portable exports, transactional multi-tab storage, recovery and comparison against available historical weekly outcomes.
- FastAPI service with SQLite storage, request validation and CSV formula protection for all text metadata.
- Immutable raw-response hashes, package extraction, strict coordinate-aware CBSL PDF parser, review queue and staged report collector.
- Past-only calendar/price features and NASA POWER weather features with a seven-day availability buffer.
- Three baselines and four LightGBM configurations: pooled/individual models with and without weather, each with 0.1/0.5/0.9 quantiles.
- Chronological selection, purged label boundaries, held-out interval calibration, 2025 evaluation, later-period check and an earlier development fold.
- Versioned artifacts, machine-readable results, source corrections, tests, technical report, two-page summary and demo script.

## Actual results

The strongest development candidate, the pooled weather model, reduced reference-basket MAE by **16.96%** against the strongest simple baseline. It regressed on tomatoes beyond the predefined **5% commodity guard**, so the release selected the **latest-price baseline**. This conservative release rule chooses the lowest basket-MAE learned candidate first, then applies both guards; it does not search for another candidate after rejection.

On **201 complete 2025 baskets**, the selected method's MAE was **LKR 2,674.05**, signed bias **LKR −52.11**, and nominal 80% basket range coverage **78.11%**. Mean range width was **LKR 8,855.59**. The basket is fixed at 20 kg beans, 30 kg carrots and 20 kg tomatoes. These are benchmark errors, not savings or paid invoice accuracy.

See [the complete results](reports/evaluation.json), [technical report](docs/TECHNICAL_REPORT.md), [model card](artifacts/model_card.json), and [source audit](data/processed/source_audit.json). No model was selected using the final test results.

## Forecasting contract

For issue date `d`, each target is the average CBSL Dambulla wholesale point quote observed on `d+1` through `d+7`, excluding `d`. At least four valid observations per vegetable are required. Missing labels remain missing, and the full seven-day calendar window must be observable. A basket outcome requires all three labels.

The central estimate adds quantity × each six-decimal per-kg central price, with each line rounded half-up to cents and the basket total equal to the sum of line amounts. It need not be the basket median. Python Decimal and locally bundled decimal.js 10.6.0 use the shared `decimal_half_up_v1` policy. Contract schema 1.1 stores the calculation version and uses mb3 IDs; legacy 1.0 records retain their original values and identifiers. Interval bounds round outward to cents; the original unrounded research evaluation is preserved. Joint percentage residual triplets from complete July–December 2024 calibration dates generate basket scenarios with nonnegative scenario prices. Conservative order statistics define the nominal 80% interval and include the central estimate. Commodity interval endpoints are never added. This is an empirical range, not a conformal or conditional coverage guarantee.

## Reproduce the experiments

```bash
# Stage candidate data only; approved canonical data is not overwritten.
python -m marketbudget.ingest prepare
# Reproduce the original experiment in an isolated, unapproved run directory.
python -m marketbudget.train
# Run the new, protocol-frozen research study separately:
python -m marketbudget.research
python scripts/build.py
python -m pytest -q
node --test tests/*.test.mjs
```

Node.js 20+ is needed only for JavaScript tests and optional browser QA, not the app. Model training runs on CPU. Re-running with identical retained source bytes, implementation and pinned dependencies should reproduce model selection and numerical results; generated timestamps differ. Artifact versions include code hashes, feature declarations, split boundaries and modelling library versions. Existing cached source files are deliberately not overwritten with revised archives. Cached bytes require their original URL, hash and length manifest; orphaned files fail review rather than acquiring invented provenance. Move a prior file and its manifest aside explicitly if adopting a new upstream version.

| Period | Purpose | Labelled rows | Complete baskets |
| --- | --- | ---: | ---: |
| 2022–2023 | Train models | 1,205 | 401 |
| Jan–Jun 2024 | Select model / baseline | 291 | 97 |
| Jul–Dec 2024 | Calibrate joint range | 315 | 105 |
| 2025 | Final test | 607 | 201 |
| Early 2026 | Later check | 123 | 41 |

Targets crossing each split's end date are purged. Methods are compared on the same eligible rows within each period. The source-report schedule, withheld input dates and unscored dates appear in `operating_coverage` in the evaluation file. Overlapping targets mean these are not independent weekly trials. A 14-day calendar-block bootstrap is included for selected-versus-baseline basket error; because the selected method is the baseline, this difference is exactly zero.

Weather-candidate eligibility uses only training/development availability. A fixed common complete-input rule applies to later comparisons, with weather exclusions reported. Tuning-period point errors remain available, but no tuning interval is constructed from later calibration residuals. Browser and Python exports use the same versioned contract ID encoding; legacy saved IDs are retained.

## New research study — separate from the approved replay

`python -m marketbudget.research` writes its protocol before fitting and evaluates 20 fixed candidates across six quarterly development folds, 2023 Q1 through 2024 Q2. Each uses earlier 2022+ training data and the immediately preceding quarter for calibration; seven-day labels are purged at every boundary. The candidates include the three existing baselines, seven-calendar-day EWMA, and four existing LightGBM families blended with the latest price at weights 0.25/0.50/0.75/1.0. Tree complexity remains fixed.

The best observed blend reduced development basket MAE by **6.60%**, with a 95% block gain interval of **−2.84% to 15.72%**. It did not reach the required 10% gain. No learned candidate passed all point-error guards; the research selection remains latest price. Relative nominal-80% development coverage was **71.67%**, versus **67.67%** for additive residuals. Neither met the fixed 75% coverage floor. These failures are shown in the research panel, not hidden by replacing the release.

The study reports all candidates, guard decisions, quarter/volatility diagnostics, 2,000-draw shared 14-day block intervals, exploratory historical checks and final model text artifacts. Previously inspected 2025 and early-2026 outcomes are explicitly exploratory; new uninspected outcomes and a new frozen protocol are required before promotion. The original approved 2025 metrics above remain unchanged.

Run `python scripts/research_report.py` with the optional report dependencies to generate the standalone research PDF, Markdown and figure. The research panel is under Model performance. Research does not alter basket forecasts.

## CLI and API

```bash
python -m marketbudget --date 2026-03-10 --beans 20 --carrot 30 --tomato 20 --budget 20000
# Correctly returns a withheld response for an old contract:
python -m marketbudget --current
```

The example basket costs LKR 14,750 at the 10 March 2026 point quotes. Its next-week baseline point estimate is also LKR 14,750 because persistence is the selected method. This is not an observed next-week outcome.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/forecast \
  -H 'Content-Type: application/json' \
  -d '{"issue_date":"2026-03-10","quantities":{"beans":20,"carrot":30,"tomato":20},"budget":20000,"replay":true}'
```

| Endpoint | Behavior |
| --- | --- |
| `GET /runtime.json` | Explicit API/browser storage mode and approved snapshot digest |
| `GET /api/v1/research/latest` | Separate research-only comparison; no model promotion |
| `GET /api/v1/health` | Mode, persistence and source freshness |
| `GET /api/v1/snapshot` | Approved frozen research contracts |
| `POST /api/v1/forecast` | Basket arithmetic and freshness enforcement |
| `GET, POST /api/v1/baskets` | List/save immutable dated records |
| `POST /api/v1/baskets/import` | Atomically restore a validated JSON backup; preserve legacy records |
| `GET, DELETE /api/v1/baskets/{id}` | Retrieve/delete a saved record |
| `GET /api/v1/baskets/{id}/comparison` | Benchmark outcome or explicit unavailable status |
| `GET /api/v1/baskets/{id}/export.csv` | Dated, source-versioned export |
| `GET /api/v1/evaluation` | Full experiment metrics |

Restoration payload: `{"schema_version":"1.0","baskets":[...exported records...]}`. Outcome comparisons are withheld when the saved source hash differs from the current snapshot. Current-day checks use `Asia/Colombo`; export timestamps remain UTC.

## Refreshing sources

`python -m marketbudget.ingest refresh` fetches the real CBSL index and discovers actual linked English report PDFs. Recognized rows are staged separately. Failed downloads and unknown layouts go to `data/processed/review_queue.jsonl`. No scheduled background process is configured and no automatic daily freshness is claimed. `ingest prepare` writes `data/candidates/<id>` and retains approved corrections during primary-source outages. Record a reviewed `review_decision: approved` in candidate.json before `python -m marketbudget.datasets /absolute/candidate/directory` can approve a complete candidate. Dataset approval uses a verified immutable directory and switches only `data/approved.json`. The bundled approved inputs remain the existing historical research dataset.

Before an operational release: confirm source rights, inspect and approve the continuous extension, merge only validated canonical rows, rerun the chronological experiment under a new version, check new-period drift and interval behavior, and release a current-day contract. Changing price files or running training does not change an approved snapshot. The API and builder read the verified `artifacts/approved.json` release pointer; sealing an explicitly reviewed set of compatibility snapshot/report/model-card files uses `python -m marketbudget.releases`. A failed seal leaves the prior pointer intact. The original experiment now writes `artifacts/experiments/<run>/` rather than replacing approved files. New research studies write `reports/research/<run>/` and cannot promote themselves. Do not treat isolated fresh quotes as a complete new model history.

## Data and attribution

- **vegetablesSriLanka 1.1.0**, by Thiyanga S. Talagala, Thisuri Jayarathne and Priyanga Dilini Talagala: <https://thiyangtdata.r-universe.dev/vegetablesSriLanka>. Package declares GPL-3. Full archive: 125,576 records; selected three-series all-year slice: 6,660 rows with 157 missing prices. Retained 2022+ slice: 2,958 rows, 2,926 valid prices.
- **Central Bank of Sri Lanka** daily price reports: <https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report>. Fifteen primary quotes were checked across 2023–2026, including three October reference-only quotes. Three 11 July 2024 values were corrected to beans 375, carrot 345 and tomato 190 LKR/kg. The 2022 sample retrieval returned 404; that year's primary audit remains incomplete. This is a sample audit, not independent validation of the complete source archive.
- **NASA POWER**: <https://power.larc.nasa.gov/docs/services/api/temporal/daily/>. Three proxy grids, five daily parameters, 1 November 2021 through 10 March 2026, Local Solar Time. NASA POWER is acknowledged; historical archive vintages are unavailable.
- **decimal.js 10.6.0**, MikeMcl, MIT license, locally bundled with its license in `web/vendor/`. No CDN is required.
- **DM Sans** by its font authors, SIL Open Font License, retained in `web/fonts/OFL.txt`.
- **LightGBM**, pandas, NumPy, FastAPI, Uvicorn, HTTPX, PyMuPDF and pyreadr retain their respective licenses. Project code is distributed under GPL-3.0-or-later; third-party source rights are separate.

Upstream CBSL model-training and redistribution terms remain unconfirmed. The private research demo does not resolve those terms. A production rollout and broader data redistribution require review. The participant recruitment and four-to-eight-week pilot described in the proposal have not occurred.

## Project layout

```text
marketbudget/       Data collector, feature contract, training, basket math, API, CLI
web/                Original HTML/CSS/JS browser source
dist/               Ready-to-serve browser app and research snapshot
data/raw/           Source bytes and SHA-256 manifests
data/processed/     Retained compatibility research tables and audit log
data/approved/      Immutable approved datasets; data/approved.json selects one
artifacts/releases/ Immutable approved forecast bundles; approved.json selects one
artifacts/          LightGBM text artifacts, model card and frozen contracts
reports/            Numerical evaluation and per-date basket outcomes
tests/              Forecast/data/API tests and browser-math tests
docs/               Technical report, summary, demonstration and operational notes
scripts/            Build, report, package and optional browser verification
```

## Changes from the proposal

The custom responsive dashboard replaces Streamlit while retaining Python/FastAPI for local persistence. Runtime storage is explicit; an API outage never silently switches to browser storage. Snapshot digests and structure are verified in both editions. The hosted edition is a static research replay and needs no paid inference API. All pre-2022 prices are excluded because the proposal's local audit pack was not attached. Raw weather was independently re-acquired. Saved plans, source correction visibility, explicit baseline-release criteria, protected CSV exports and browser/API numerical consistency improve traceability. No fabricated observations, model scores, testimonials or pilot outcomes are included.

AI assistance: OpenAI Codex assisted in implementation, source recovery, experimentation, tests and documentation. The original submission team should review and own the final submission and retain this disclosure.
