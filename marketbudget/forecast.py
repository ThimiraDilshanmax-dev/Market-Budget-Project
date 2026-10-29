"""Shared basket arithmetic for the CLI, API and exported browser contract."""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import struct
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .config import COMMODITIES, MAX_PRICE_AGE, NAMES
from .money import ledger, amount, decimal, CALCULATION_VERSION


def validate_quantities(quantities: dict[str, float]) -> dict[str, float]:
    if set(quantities) != set(COMMODITIES):
        raise ValueError("Provide kilograms for beans, carrot and tomato; use zero to omit an item")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           or value < 0 or value > 10000 for value in quantities.values()):
        raise ValueError("Kilograms must be finite numbers between 0 and 10,000")
    if sum(quantities.values()) == 0:
        raise ValueError("Add at least one vegetable to the basket")
    return {key: float(quantities[key]) for key in COMMODITIES}


def scenario_costs(point: np.ndarray, quantities: np.ndarray, residuals: np.ndarray) -> np.ndarray:
    """Rows are aligned same-date residual triplets, preserving market co-movement."""
    return np.maximum(0, point[None, :] * (1 + residuals)) @ quantities


def interval(values: np.ndarray, point: float) -> tuple[float, float]:
    if len(values) < 30 or not np.isfinite(values).all() or not math.isfinite(point):
        raise ValueError("At least 30 complete calibration baskets are required")
    # Conservative order statistics and center inclusion, frozen before test.
    ordered = np.sort(values)
    n = len(ordered)
    low_index = max(0, math.floor(.1 * (n + 1)) - 1)
    high_index = min(n - 1, math.ceil(.9 * (n + 1)) - 1)
    return float(min(point, ordered[low_index])), float(max(point, ordered[high_index]))


def contract_id(contract: dict[str, Any]) -> str:
    """Identical IEEE-754 input encoding in Python and JavaScript, including mode.

    Stored legacy IDs are retained. New IDs ignore export time and basket name.
    Numeric zero is normalized so -0 and 0 identify the same quantities.
    """
    def bits(value):
        return struct.pack(">d", 0.0 if value == 0 else float(value)).hex()
    modern=contract.get("calculation_version")==CALCULATION_VERSION
    identity = ["marketbudget-contract-v3" if modern else "marketbudget-contract-v2", contract["issue_date"], contract["status"],
                contract["model_version"], contract["source_hash"],
                [bits(contract["quantities"][c]) for c in COMMODITIES],
                None if contract["budget"] is None else bits(contract["budget"])]
    if modern:identity.append(CALCULATION_VERSION)
    return ("mb3-" if modern else "mb2-") + sha256(json.dumps(identity, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:16]


def basket_forecast(snapshot: dict[str, Any], issue_date: str, quantities: dict[str, float],
                    budget: float | None = None, *, replay: bool = True,
                    as_of: date | None = None) -> dict[str, Any]:
    q = validate_quantities(quantities)
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0 or budget > 1e9):
        raise ValueError("Budget must be positive, finite and at most LKR 1 billion")
    row = next((entry for entry in snapshot["forecasts"] if entry["date"] == issue_date), None)
    if row is None:
        raise ValueError("No approved forecast contract exists for this issue date")
    effective_date = pd.Timestamp(issue_date).date() if replay else (as_of or datetime.now(ZoneInfo("Asia/Colombo")).date())
    if not replay and pd.Timestamp(issue_date).date() != effective_date:
        return {"status": "withheld", "reason": "A current issue-date contract is required for an actionable forecast.",
                "last_issue_date": issue_date, "last_price_dates": row["last_price_dates"]}
    ages = {c: (effective_date - date.fromisoformat(row["last_price_dates"][c])).days for c in COMMODITIES}
    if any(age < 0 or age > MAX_PRICE_AGE for age in ages.values()):
        return {"status": "withheld", "reason": "A required quote is more than three calendar days old or dated in the future.",
                "price_ages": ages, "last_price_dates": row["last_price_dates"]}
    point = np.array([row["point"][c] for c in COMMODITIES], dtype=float)
    latest_prices = np.array([row["latest"][c] for c in COMMODITIES], dtype=float)
    if not np.isfinite(point).all() or (point < 0).any() or not np.isfinite(latest_prices).all() or (latest_prices <= 0).any():
        raise ValueError("Forecast prices must be finite and nonnegative; source quotes must be positive")
    weights = np.array([q[c] for c in COMMODITIES])
    residuals = np.array(snapshot["residual_scenarios"], dtype=float)
    if residuals.ndim != 2 or residuals.shape[1] != 3 or not np.isfinite(residuals).all():
        raise ValueError("Malformed joint calibration scenarios")
    calculated=ledger(point,weights,residuals)
    total=calculated["total"]
    lower, upper = calculated["interval"]
    lines = []
    for i, commodity in enumerate(COMMODITIES):
        lo, hi = calculated["marginal"][i]
        latest = row["latest"][commodity]
        lines.append({"commodity": commodity, "name": NAMES[commodity], "kg": q[commodity],
                      "price_per_kg": calculated["prices"][i], "latest_price": latest,
                      "change_percent": amount((decimal(calculated["prices"][i])/decimal(latest)-1)*100),
                      "line_total": calculated["lines"][i],
                      "price_interval": [round(lo, 2), round(hi, 2)], "last_price_date": row["last_price_dates"][commodity]})
    now = datetime.now(timezone.utc).isoformat()
    result = {"schema_version": "1.1", "calculation_version":CALCULATION_VERSION,"status": "historical_replay" if replay else "forecast",
              "issue_date": issue_date, "target_start": (pd.Timestamp(issue_date) + pd.Timedelta(days=1)).date().isoformat(),
              "target_end": (pd.Timestamp(issue_date) + pd.Timedelta(days=7)).date().isoformat(),
              "exported_at": now, "issue_timing": "Historical replay after assumed report availability; original publication times unknown." if replay else "Current issue-date contract; quote freshness evaluated in Asia/Colombo.",
              "market": "Dambulla", "price_type": "Wholesale benchmark", "currency": "LKR", "quantities": q,
              "budget": budget, "estimate": round(total, 2), "interval": [round(lower, 2), round(upper, 2)],
              "nominal_coverage": .8, "calibration_n": len(residuals), "lines": lines,
              "model_version": snapshot["model"]["version"], "method": snapshot["model"]["selected"],
              "budget_difference": amount(decimal(budget)-decimal(total)) if budget is not None else None,
              "upper_budget_difference": amount(decimal(budget)-decimal(upper)) if budget is not None else None,
              "price_ages": ages, "weather_status": snapshot["model"]["weather_status"],
              "disclaimer": "Weekly average reference cost, excluding delivery and supplier terms. Nominal 80% range is empirical, not a guarantee.",
              "source_hash": snapshot["source_hash"]}
    result["contract_id"] = contract_id(result)
    return result
