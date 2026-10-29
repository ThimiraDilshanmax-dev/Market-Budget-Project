"""Reproducible chronological experiments and a versioned replay contract.

Run: python -m marketbudget.train
Model and features are selected on Jan-Jun 2024 only. Jul-Dec 2024 is used
only for intervals. 2025 is evaluated once after decisions are fixed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from importlib.metadata import version as package_version

from .config import COMMODITIES, REFERENCE_BASKET, ROOT
from .features import PRICE_FEATURES, make_features, split
from .forecast import interval, scenario_costs
from . import __version__
from .datasets import dataset_directory

PARAMETERS = dict(n_estimators=180, learning_rate=.04, num_leaves=9, max_depth=4,
                  min_child_samples=30, reg_lambda=2.0, verbosity=-1,
                  random_state=42, n_jobs=2, deterministic=True, force_col_wise=True)
BASELINES = ("latest_price", "mean_28d", "prior_year")
SPLITS = {"train": ("2022-01-01", "2023-12-31"),
          "tuning": ("2024-01-01", "2024-06-30"),
          "calibration": ("2024-07-01", "2024-12-31"),
          "test_2025": ("2025-01-01", "2025-12-31"),
          "later_2026": ("2026-01-01", "2026-03-10")}


def fit_models(training: pd.DataFrame, features: list[str], pooled: bool) -> dict:
    models = {}
    for commodity in (["pooled"] if pooled else COMMODITIES):
        rows = training if pooled else training[training.commodity == commodity]
        for alpha in (.1, .5, .9):
            model = lgb.LGBMRegressor(objective="quantile", alpha=alpha, **PARAMETERS)
            model.fit(rows[features], rows.target_ratio)
            models[(commodity, alpha)] = model
    return {"models": models, "features": features, "pooled": pooled}


def learned_predict(bundle: dict, frame: pd.DataFrame) -> np.ndarray:
    output = np.zeros((len(frame), 3))
    for commodity in (["pooled"] if bundle["pooled"] else COMMODITIES):
        mask = np.ones(len(frame), dtype=bool) if bundle["pooled"] else (frame.commodity == commodity).to_numpy()
        if not mask.any():
            continue
        for i, alpha in enumerate((.1, .5, .9)):
            ratio = bundle["models"][(commodity, alpha)].predict(frame.loc[mask, bundle["features"]])
            output[mask, i] = np.maximum(0, frame.loc[mask, "latest"].to_numpy() * (1 + ratio))
    # Frozen crossing rule. Label quantiles are never presented as basket quantiles.
    return np.sort(output, axis=1)


def predict(method: str, frame: pd.DataFrame, models: dict) -> np.ndarray:
    if method in BASELINES:
        column = {"latest_price": "latest", "mean_28d": "mean28", "prior_year": "seasonal"}[method]
        return np.repeat(frame[column].to_numpy()[:, None], 3, axis=1)
    return learned_predict(models[method], frame)


def development_weather_available(sets: dict, columns: list[str]) -> bool:
    """Candidate selection cannot depend on calibration/test input availability."""
    return bool(columns) and all(sets[name][columns].notna().all().all() for name in ("train", "tuning"))


def complete_matrix(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return frame.pivot(index="date", columns="commodity", values=column).reindex(columns=COMMODITIES).dropna()


def score(frame: pd.DataFrame, point: np.ndarray) -> dict:
    frame = frame.copy()
    frame["prediction"] = point
    actual = complete_matrix(frame, "target")
    predicted = complete_matrix(frame, "prediction").reindex(actual.index)
    weights = np.array([REFERENCE_BASKET[c] for c in COMMODITIES])
    error = (predicted.to_numpy() - actual.to_numpy()) @ weights
    per = {}
    for commodity in COMMODITIES:
        rows = frame[frame.commodity == commodity]
        residual = rows.prediction - rows.target
        per[commodity] = {"mae": float(np.abs(residual).mean()), "bias": float(residual.mean()), "n": len(rows)}
    return {"basket_mae": float(np.abs(error).mean()), "basket_bias": float(error.mean()),
            "complete_baskets": len(error), "commodities": per}


def bootstrap_difference(errors: pd.DataFrame, left: str, right: str) -> list[float]:
    """Shared calendar blocks reduce the false precision of overlapping labels."""
    paired = errors[[left, right]].dropna().copy()
    difference = paired[left].abs() - paired[right].abs()
    # Blocks based on absolute calendar weeks, preserving cross-commodity dependence.
    block_ids = ((paired.index - pd.Timestamp("2025-01-01")).days // 14).to_numpy()
    groups = [difference.to_numpy()[block_ids == value] for value in np.unique(block_ids)]
    if len(groups) < 3:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(42)
    means = [np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))]).mean() for _ in range(1000)]
    return [float(x) for x in np.quantile(means, [.025, .975])]


def run(root: Path = ROOT) -> dict:
    inputs=dataset_directory(root)
    run_id="legacy-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    output=root/"artifacts/experiments"/run_id
    for folder in ("artifacts","reports","data/processed"):(output/folder).mkdir(parents=True,exist_ok=True)
    prices = pd.read_csv(inputs / "prices.csv", parse_dates=["date"])
    weather_path = inputs / "weather.csv"
    weather = pd.read_csv(weather_path, index_col="date", parse_dates=True) if weather_path.exists() else None
    features = make_features(prices, weather)
    wx = [c for c in features.columns if c.startswith("wx_")]
    sets = {name: split(features, *boundaries) for name, boundaries in SPLITS.items()}
    # Freeze candidate availability using development inputs only. A predeclared
    # complete-input rule keeps later comparisons on identical rows, without
    # changing candidate selection after looking at test-period missingness.
    weather_complete = development_weather_available(sets, wx)
    missing_weather_exclusions = {}
    for period in sets:
        if weather_complete:
            ready = sets[period][wx].notna().all(axis=1)
            missing_weather_exclusions[period] = int((~ready).sum())
            sets[period] = sets[period].loc[ready].copy()
        else:
            missing_weather_exclusions[period] = 0
    models = {}
    for scope, pooled in (("pooled", True), ("individual", False)):
        models[f"price_{scope}"] = fit_models(sets["train"], PRICE_FEATURES, pooled)
        if weather_complete:
            models[f"weather_{scope}"] = fit_models(sets["train"], PRICE_FEATURES + wx, pooled)
    methods = list(BASELINES) + list(models)
    tuning = {method: score(sets["tuning"], predict(method, sets["tuning"], models)[:, 1]) for method in methods}
    baseline = min(BASELINES, key=lambda method: tuning[method]["basket_mae"])
    learned = min(models, key=lambda method: tuning[method]["basket_mae"])
    improvement = 1 - tuning[learned]["basket_mae"] / tuning[baseline]["basket_mae"]
    per_crop_ok = all(tuning[learned]["commodities"][c]["mae"] <= 1.05 * tuning[baseline]["commodities"][c]["mae"] for c in COMMODITIES)
    selected = learned if improvement >= .1 and per_crop_ok else baseline
    selection = {"best_baseline": baseline, "best_learned": learned, "learned_improvement": float(improvement),
                 "per_commodity_guard_passed": bool(per_crop_ok), "selected": selected,
                 "rule": "Deploy learned model only if tuning basket MAE improves by at least 10% and no commodity MAE regresses by more than 5%. Otherwise use strongest tuning baseline."}
    cal = sets["calibration"].copy()
    cal["prediction"] = predict(selected, cal, models)[:, 1]
    cal_actual = complete_matrix(cal, "target")
    cal_point = complete_matrix(cal, "prediction").reindex(cal_actual.index)
    residuals = (cal_actual.to_numpy() / cal_point.to_numpy() - 1)
    if len(residuals) < 30 or not np.isfinite(residuals).all():
        raise ValueError("Insufficient or invalid aligned calibration residuals")
    all_metrics, predictions, interval_metrics = {}, [], {}
    for period in ("tuning", "test_2025", "later_2026"):
        frame = sets[period].copy()
        period_metrics = {}
        error_series = {}
        for method in methods:
            quantiles = predict(method, frame, models)
            point = quantiles[:, 1]
            period_metrics[method] = score(frame, point)
            if method in models:
                target = frame.target.to_numpy()[:, None]
                loss = np.maximum(np.array([.1, .5, .9]) * (target - quantiles), (np.array([.1, .5, .9]) - 1) * (target - quantiles))
                period_metrics[method]["pinball_mean"] = float(loss.mean())
                period_metrics[method]["raw_quantile_coverage"] = float(((target[:, 0] >= quantiles[:, 0]) & (target[:, 0] <= quantiles[:, 2])).mean())
            temp = frame.assign(prediction=point)
            actual = complete_matrix(temp, "target")
            central = complete_matrix(temp, "prediction").reindex(actual.index)
            weights = np.array([REFERENCE_BASKET[c] for c in COMMODITIES])
            error_series[method] = pd.Series((central.to_numpy() - actual.to_numpy()) @ weights, index=actual.index)
            # Calibration happens after tuning: never draw a retrospective tuning
            # interval using residuals that had not yet occurred at those issues.
            if method == selected and period != "tuning":
                intervals = [interval(scenario_costs(p, weights, residuals), float(p @ weights)) for p in central.to_numpy()]
                actual_basket = actual.to_numpy() @ weights
                covered = [(lo <= y <= hi) for (lo, hi), y in zip(intervals, actual_basket)]
                interval_metrics[period] = {"nominal": .8, "observed_coverage": float(np.mean(covered)),
                                            "mean_width": float(np.mean([hi - lo for lo, hi in intervals])),
                                            "n": len(covered), "calibration_n": len(residuals),
                                            "overlapping_targets": True}
                for i, date in enumerate(actual.index):
                    predictions.append({"period": period, "date": date.date().isoformat(),
                                        "actual": float(actual_basket[i]), "prediction": float(central.to_numpy()[i] @ weights),
                                        "lower": intervals[i][0], "upper": intervals[i][1]})
        all_metrics[period] = period_metrics
        if period == "test_2025":
            all_metrics["test_block_bootstrap"] = {"statistic": "Selected minus strongest development baseline absolute basket error",
                                                    "block_calendar_days": 14, "draws": 1000,
                                                    "interval_95": bootstrap_difference(pd.DataFrame(error_series), selected, baseline)}
    # Additional earlier development fold; never uses the final test.
    early_train = split(features, "2022-01-01", "2022-12-31")
    early_valid = split(features, "2023-01-01", "2023-12-31")
    early_model = fit_models(early_train, PRICE_FEATURES, True)
    rolling = {"train_2022_validate_2023": {"price_pooled": score(early_valid, learned_predict(early_model, early_valid)[:, 1]),
                                          "latest_price": score(early_valid, predict("latest_price", early_valid, {})[:, 1])}}
    input_hash = sha256((inputs / "prices.csv").read_bytes() +
                        (weather_path.read_bytes() if weather_path.exists() else b"") +
                        json.dumps(PARAMETERS, sort_keys=True).encode()).hexdigest()
    version = "mb1-" + input_hash[:10]
    implementation = {"application_version": __version__, "splits": SPLITS,
                      "price_features": PRICE_FEATURES, "weather_features": wx if weather_complete else [],
                      "packages": {name: package_version(name) for name in ("lightgbm", "numpy", "pandas")},
                      "code_sha256": {name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                                      for name in ("train.py", "features.py", "forecast.py", "config.py")}}
    artifact_hash = sha256(input_hash.encode() + json.dumps(implementation, sort_keys=True).encode()).hexdigest()
    version = "mb1.1-" + artifact_hash[:10]
    artifacts = output / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for method, bundle in models.items():
        for (commodity, alpha), model in bundle["models"].items():
            model.booster_.save_model(str(artifacts / f"{method}_{commodity}_{alpha:.1f}.txt"))
    model_info = {"version": version, "artifact_hash": artifact_hash, "provenance": implementation,
                  "selected": selected, "train_end": "2023-12-31", "selection_end": "2024-06-30",
                  "calibration_end": "2024-12-31", "weather_status": "Included with seven-day buffer" if selected.startswith("weather") else "Not used by selected method",
                  "parameters": PARAMETERS, "features": models[selected]["features"] if selected in models else [],
                  "selection": selection, "released_for": "Private research replay; operational deployment requires source-rights and freshness review"}
    operating_coverage = {}
    for name, (start, end) in SPLITS.items():
        scheduled = features[features.date.between(start, end)].copy()
        dates_n = scheduled.date.nunique()
        full = scheduled.groupby("date").eligible.agg(lambda values: len(values) == 3 and values.all())
        ineligible = scheduled[~scheduled.eligible]
        labelled = len(complete_matrix(sets[name], "target"))
        operating_coverage[name] = {"scheduled_report_dates": int(dates_n),
                                    "complete_input_dates": int(full.sum()),
                                    "withheld_input_dates": int((~full).sum()),
                                    "stale_or_missing_price_rows": int(((ineligible.age > 3) | ineligible.age.isna()).sum()),
                                    "complete_evaluated_baskets": labelled,
                                    "missing_weather_labels_excluded": missing_weather_exclusions[name],
                                    "scheduled_dates_not_scored": int(dates_n - labelled),
                                    "note": "Not scored includes incomplete targets, insufficient history and purged boundary windows. Schedule is source-report dates, not every calendar day."}
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": model_info,
              "splits": {name: {"start": start, "end": end, "labelled_rows": len(sets[name]),
                                "complete_baskets": len(complete_matrix(sets[name], "target"))} for name, (start, end) in SPLITS.items()},
              "metrics": all_metrics, "tuning": tuning, "intervals": interval_metrics, "rolling_development": rolling,
              "reference_basket": REFERENCE_BASKET, "weather_available": weather_complete,
              "operating_coverage": operating_coverage,
              "coverage": json.loads((inputs / "coverage.json").read_text()),
              "limitations": ["Historical source publication times and weather vintages are unavailable.",
                              "Overlapping seven-day labels and one calibration period limit independent evidence.",
                              "No completed buyer pilot, verified savings or invoice-cost validation.",
                              "Price-source upstream reuse terms are not confirmed; private research demonstration only.",
                              "Sample source audit is not a full archive audit. Data before 2022 excluded.",
                              "2026 values are a later-period check, not inputs for selection or calibration."]}
    # Predictions are frozen; changing basket quantities only performs documented
    # arithmetic over these contracts, never an undocumented client-side model.
    replay_frame = features[(features.date >= "2025-01-01") & features.eligible].copy()
    if selected.startswith("weather"):
        replay_frame = replay_frame.loc[replay_frame[models[selected]["features"]].notna().all(axis=1)].copy()
    replay_frame["prediction"] = predict(selected, replay_frame, models)[:, 1]
    forecast_rows = []
    for date, group in replay_frame.groupby("date"):
        if set(group.commodity) != set(COMMODITIES):
            continue
        group = group.set_index("commodity")
        forecast_rows.append({"date": date.date().isoformat(),
                              "point": {c: float(group.loc[c, "prediction"]) for c in COMMODITIES},
                              "latest": {c: float(group.loc[c, "latest"]) for c in COMMODITIES},
                              "last_price_dates": {c: group.loc[c, "last_price_date"].date().isoformat() for c in COMMODITIES},
                              "actual": {c: float(group.loc[c, "target"]) if pd.notna(group.loc[c, "target"]) else None for c in COMMODITIES},
                              "label_counts": {c: int(group.loc[c, "label_count"]) for c in COMMODITIES}})
    history = [{"date": date.date().isoformat(), **{c: (float(row[c]) if pd.notna(row[c]) else None) for c in COMMODITIES}}
               for date, row in prices.pivot(index="date", columns="commodity", values="price").iterrows() if date >= pd.Timestamp("2024-11-01")]
    snapshot = {"schema_version": "1.0", "generated_at": report["generated_at"], "source_hash": input_hash,
                "mode": "historical_replay", "model": model_info, "coverage": report["coverage"],
                "residual_scenarios": residuals.tolist(), "calibration_dates": [d.date().isoformat() for d in cal_actual.index],
                "forecasts": forecast_rows, "history": history, "evaluation": report,
                "test_predictions": [p for p in predictions if p["period"] == "test_2025"],
                "source_audit": json.loads((inputs / "source_audit.json").read_text()),
                "corrections": json.loads((inputs / "corrections.json").read_text())}
    (artifacts / "model_card.json").write_text(json.dumps(model_info, indent=2))
    (artifacts / "snapshot.json").write_text(json.dumps(snapshot, separators=(",", ":"), allow_nan=False))
    (output / "reports/evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    pd.DataFrame(predictions).to_csv(output / "reports/basket_predictions.csv", index=False)
    features.to_csv(output / "data/processed/features.csv", index=False, date_format="%Y-%m-%d")
    print(json.dumps({"selection": selection, "test": all_metrics["test_2025"][selected],
                      "intervals": interval_metrics["test_2025"], "version": version}, indent=2))
    return snapshot


if __name__ == "__main__":
    run()
