# MarketBudget — project summary

MarketBudget helps a small Sri Lankan caterer or canteen reserve cash for beans, carrots and tomatoes bought through Dambulla. Enter kilograms and an optional budget to obtain a dated seven-day weekly-average benchmark estimate and a nominal 80% joint cost range. Purchasing decisions remain with the buyer.

## Delivered

A responsive browser app, FastAPI service, SQLite saved baskets, validated backup restoration, dated CSV/JSON exports, price explorer, source audit, chronological forecasting experiments, versioned model artifacts, tests and reproducible instructions. The private hosted app is a historical replay; the full local project persists records in SQLite. No paid forecast API is required.

## Real-data foundation

Recovered vegetablesSriLanka 1.1.0 data provides 2,926 valid 2022+ quotes in 2,958 rows through 10 March 2026. Three primary-verified July 2024 corrections preserve originals and provenance. Fifteen quotes were checked across 2023–2026; the 2022 sample audit remains incomplete. NASA POWER supplies three regional weather proxies with a seven-day availability buffer. A separate October reference report is not appended across the historical gap.

## Method and actual result

Targets average valid observations on issue+1 through issue+7 with at least four quotes per commodity. Models use only past features. Train 2022–2023, select Jan–Jun 2024, calibrate Jul–Dec 2024, test 2025, then check early 2026; crossing labels are purged. Three simple baselines compete against four restricted LightGBM quantile variants.

The strongest development model improved basket MAE **16.96%**, but exceeded the tomato regression guard. The release selected **Latest-price baseline** with an empirical joint range from 105 aligned residual scenarios.

For the fixed 20/30/20 kg basket on **201 complete 2025 issue dates**: **LKR 2,674.05 MAE**, **LKR -52.11 signed bias**, **78.11% observed coverage** for the nominal 80% range, and **LKR 8,855.59 average range width**. These are benchmark metrics, not paid-cost performance or verified savings.

## Reliability and remaining work

Unknown PDF layouts enter a review queue; missing targets remain missing. Current mode withholds old contracts and quotes older than three calendar days. Baskets preserve dates, source hash and model version. Source-rights clarification, a continuous audited recent extension and a prospective buyer pilot remain necessary. Historical publication times, weather revisions, partial source audit and overlapping calibration targets limit claims. Upstream CBSL rights are not resolved by the package's GPL declaration.

## Run and demonstrate

Install with `python -m pip install -e '.[dev]'`, build with `python scripts/build.py`, and run `python -m marketbudget.api`; open http://127.0.0.1:8000. The included artifacts run without downloading or training. README gives full reproduction commands; DEMO_SCRIPT.md provides a three-minute walkthrough.

Sources: Talagala, Jayarathne and Talagala, vegetablesSriLanka 1.1.0; CBSL Daily Price Reports; NASA POWER. New code GPL-3.0-or-later; other source rights remain separate. OpenAI Codex assisted in implementation and documentation; the submission team should review and own the final work.

## Separate research and application 1.2

A separate six-fold study of 20 fixed candidates found a best observed 6.60% development gain. Selected nominal-80% development coverage was 71.67%. Research promotion remains disabled. See the standalone research report for guard decisions and uncertainty.
The application now uses immutable approvals, decimal arithmetic, transactional browser storage and explicit recovery.
