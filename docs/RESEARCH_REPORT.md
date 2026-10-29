# MarketBudget 1.2 research study

**Research only. No model promotion.** Run `study-a172c38095d77efd`; frozen protocol SHA-256 `a172c38095d77efdeecdddcdd83aa4dfe60b01dcdeb4a241784802d90f5b2aca`.

Six chronological validation quarters (2023 Q1–2024 Q2) evaluated 20 fixed candidates on 300 complete reference baskets. Earlier 2022+ observations train each fold, the immediately preceding quarter calibrates intervals, and crossing seven-day targets are purged.

The best observed candidate, **weather_individual@0.5**, reduced development basket MAE by **6.60%**. Its 95% gain interval is **-2.84% to 15.72%**. It did not meet the 10% improvement guard. No learned candidate passed every guard; the research selection is **latest_price**.

The relative nominal 80% range covered **71.67%** of development outcomes; the additive range covered **67.67%**. Neither met the 75% minimum. The approved application's original replay and evaluation are unchanged.

| Candidate | Basket MAE (LKR) | Crop guard | Improved folds |
| --- | ---: | --- | ---: |
| weather_individual@0.5 | 2,398.23 | pass | 5 |
| price_individual@0.5 | 2,410.89 | pass | 4 |
| price_individual@0.75 | 2,431.55 | pass | 2 |
| weather_individual@0.75 | 2,433.42 | fail | 5 |
| price_pooled@0.5 | 2,436.13 | pass | 3 |
| price_pooled@0.75 | 2,438.70 | pass | 2 |
| weather_individual@0.25 | 2,448.38 | pass | 5 |
| price_individual@0.25 | 2,457.95 | pass | 4 |
| price_pooled@1 | 2,473.70 | fail | 2 |
| price_pooled@0.25 | 2,475.00 | pass | 5 |
| weather_pooled@0.5 | 2,479.25 | pass | 4 |
| weather_pooled@0.25 | 2,491.47 | pass | 4 |
| weather_pooled@0.75 | 2,511.22 | fail | 4 |
| price_individual@1 | 2,524.52 | fail | 2 |
| weather_individual@1 | 2,539.52 | fail | 4 |
| latest_price | 2,567.62 | baseline | — |
| weather_pooled@1 | 2,626.41 | fail | 4 |
| ewma_7d | 3,817.57 | baseline | — |
| mean_28d | 4,992.70 | baseline | — |
| prior_year | 8,111.51 | baseline | — |

The 2025/early-2026 comparisons are previously inspected exploratory checks. New uninspected outcomes and a separately frozen study are required before promotion. Full quarter/volatility diagnostics, 2,000-draw block uncertainty intervals and all settings are in results.json. Reproduce with `python -m marketbudget.research`. No paid inference API or automated model promotion is involved.
