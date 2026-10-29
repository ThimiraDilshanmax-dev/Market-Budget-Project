from datetime import date
import json
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from marketbudget.config import COMMODITIES, ROOT
from marketbudget.features import PRICE_FEATURES, make_features, split
from marketbudget.forecast import basket_forecast, interval, scenario_costs, validate_quantities
from marketbudget.ingest import discover_reports, parse_cbsl


@pytest.fixture(scope="module")
def snapshot():
    return json.loads((ROOT / "artifacts/snapshot.json").read_text())


def fixture_prices():
    dates = pd.date_range("2023-01-01", periods=100)
    return pd.DataFrame([{"date": day, "commodity": c, "price": 100 + i + j * 10}
                         for i, day in enumerate(dates) for j, c in enumerate(COMMODITIES)])


def test_precise_target_excludes_issue_day():
    frame = make_features(fixture_prices())
    row = frame[(frame.date == "2023-02-01") & (frame.commodity == "beans")].iloc[0]
    assert row.target == pytest.approx(np.mean(np.arange(132, 139)))
    assert row.label_count == 7


def test_future_labels_never_filled_and_tail_is_unlabelled():
    data = fixture_prices()
    data.loc[(data.date.between("2023-02-02", "2023-02-05")) & (data.commodity == "beans"), "price"] = np.nan
    frame = make_features(data)
    row = frame[(frame.date == "2023-02-01") & (frame.commodity == "beans")].iloc[0]
    assert row.label_count == 3
    assert pd.isna(row.target)
    assert frame[frame.date > "2023-04-03"].target.isna().all()


def test_price_features_do_not_see_future_values():
    original = fixture_prices()
    changed = original.copy()
    changed.loc[changed.date > "2023-02-15", "price"] = 99999
    left, right = make_features(original), make_features(changed)
    pd.testing.assert_frame_equal(left.loc[left.date <= "2023-02-15", PRICE_FEATURES],
                                  right.loc[right.date <= "2023-02-15", PRICE_FEATURES])


def test_weather_ends_seven_days_before_issue():
    data = fixture_prices()
    weather = pd.DataFrame({"proxy_prectotcorr": 1., "proxy_t2m": 20.}, index=pd.date_range("2023-01-01", periods=100))
    changed = weather.copy()
    changed.loc[changed.index > "2023-02-08"] = 9999
    left, right = make_features(data, weather), make_features(data, changed)
    cols = [c for c in left if c.startswith("wx_")]
    pd.testing.assert_frame_equal(left.loc[left.date <= "2023-02-15", cols], right.loc[right.date <= "2023-02-15", cols])
    row = left[left.date == "2023-02-15"].iloc[0]
    assert row.wx_proxy_prectotcorr_7 == 7
    assert row.wx_proxy_t2m_14 == 20


def test_split_purges_cross_boundary_labels():
    frame = make_features(fixture_prices())
    selected = split(frame, "2023-02-01", "2023-02-28")
    assert selected.date.max() == pd.Timestamp("2023-02-21")
    assert (selected.target_end <= "2023-02-28").all()


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), 10001, True, "20"])
def test_invalid_quantities_rejected(value):
    with pytest.raises(ValueError):
        validate_quantities({"beans": value, "carrot": 30, "tomato": 20})


def test_zero_basket_rejected_and_zero_line_allowed():
    with pytest.raises(ValueError):
        validate_quantities(dict.fromkeys(COMMODITIES, 0))
    assert validate_quantities({"beans": 1, "carrot": 0, "tomato": 0})["carrot"] == 0


def test_joint_scenarios_preserve_offsetting_market_moves():
    residuals = np.tile([[.5, -.5, 0], [-.5, .5, 0]], (30, 1))
    costs = scenario_costs(np.array([100,100,100]), np.array([1,1,0]), residuals)
    np.testing.assert_allclose(costs, 200)
    assert interval(costs, 200) == (200,200)
    # Summed marginal endpoints would incorrectly produce [100, 300].


def test_replay_arithmetic_and_export_dates(snapshot):
    result = basket_forecast(snapshot, "2026-03-10", {"beans":20,"carrot":30,"tomato":20}, 20000)
    assert result["estimate"] == 14750
    assert result["target_start"] == "2026-03-11"
    assert result["target_end"] == "2026-03-17"
    assert result["calibration_n"] == 105
    assert result["interval"][0] <= result["estimate"] <= result["interval"][1]
    assert result["contract_id"] == basket_forecast(snapshot, "2026-03-10", {"beans":20,"carrot":30,"tomato":20}, 20000)["contract_id"]


def test_current_forecast_withheld_for_historical_contract(snapshot):
    result = basket_forecast(snapshot, "2026-03-10", {"beans":20,"carrot":30,"tomato":20}, replay=False, as_of=date(2026,10,26))
    assert result["status"] == "withheld"
    assert "estimate" not in result


def test_three_day_freshness_boundary(snapshot):
    row = json.loads(json.dumps(snapshot["forecasts"][-1]))
    row["date"] = "2026-03-13"
    isolated = {**snapshot, "forecasts": [row]}
    assert basket_forecast(isolated, row["date"], {"beans":20,"carrot":30,"tomato":20})["status"] == "historical_replay"
    row["date"] = "2026-03-14"
    assert basket_forecast(isolated, row["date"], {"beans":20,"carrot":30,"tomato":20})["status"] == "withheld"


def test_parser_reads_wholesale_not_retail():
    records = parse_cbsl(ROOT / "data/raw/cbsl_20240711.pdf", "2024-07-11")
    assert {r["commodity"]:r["price"] for r in records} == {"beans":375,"carrot":345,"tomato":190}
    assert parse_cbsl(ROOT / "data/raw/cbsl_20260310.pdf", "2026-03-10")[1]["price"] == 225


def test_parser_rejects_mismatched_printed_date():
    with pytest.raises(ValueError, match="date"):
        parse_cbsl(ROOT / "data/raw/cbsl_20240711.pdf", "2024-07-12")


def test_archive_discovers_only_actual_english_links():
    html = '<a href="/sites/default/files/price_report_20261016_e.pdf">one</a><a href="https://evil.example/price_report_20261017_e.pdf">bad</a><a href="/price_report_20261016_s.pdf">Sinhala</a>'
    assert discover_reports(html) == [("2026-10-16", "https://www.cbsl.gov.lk/sites/default/files/price_report_20261016_e.pdf")]


def test_calibration_and_final_test_are_separated(snapshot):
    assert max(snapshot["calibration_dates"]) <= "2024-12-24"
    assert min(row["date"] for row in snapshot["test_predictions"]) >= "2025-01-01"
    assert len(snapshot["residual_scenarios"]) == len(snapshot["calibration_dates"])
    assert len(snapshot["corrections"]) == 3
    assert snapshot["coverage"]["primary_quotes_checked"] >= 9


def test_model_release_rule_matches_development_only(snapshot):
    selection = snapshot["model"]["selection"]
    expected = selection["best_learned"] if selection["learned_improvement"] >= .1 and selection["per_commodity_guard_passed"] else selection["best_baseline"]
    assert selection["selected"] == expected
    assert snapshot["model"]["selection_end"] < snapshot["model"]["calibration_end"] < "2025-01-01"


@pytest.mark.skipif(not shutil.which("node"), reason="Node is optional for cross-language verification")
def test_browser_api_arithmetic_matches_for_varied_baskets(snapshot):
    rng = np.random.default_rng(42)
    baskets = [{c: float(rng.uniform(0,100)) for c in COMMODITIES} for _ in range(20)]
    script = """
      import fs from 'node:fs';
      import {calculateBasket,identifyContract} from './web/math.mjs';
      const input=JSON.parse(fs.readFileSync(0,'utf8'));
      console.log(JSON.stringify(await Promise.all(input.baskets.map(q=>identifyContract(calculateBasket(input.snapshot,'2026-03-10',q,25000))))));
    """
    run = subprocess.run(["node","--input-type=module","-e",script],input=json.dumps({"snapshot":snapshot,"baskets":baskets}),
                         text=True,capture_output=True,cwd=ROOT,check=True)
    javascript = json.loads(run.stdout)
    for quantities, browser in zip(baskets, javascript):
        python = basket_forecast(snapshot,"2026-03-10",quantities,25000)
        assert python["estimate"] == pytest.approx(browser["estimate"],abs=.011)
        assert python["interval"] == pytest.approx(browser["interval"],abs=.011)
        assert python["upper_budget_difference"] == pytest.approx(browser["upper_budget_difference"],abs=.011)
        assert python["contract_id"] == browser["contract_id"]


def test_current_day_uses_sri_lankan_civil_date(snapshot,monkeypatch):
    from datetime import datetime, timezone
    import importlib
    module=importlib.import_module("marketbudget.forecast")
    instant=datetime(2026,3,9,20,0,tzinfo=timezone.utc)
    class Clock:
        @staticmethod
        def now(tz):
            return instant.astimezone(tz)
    monkeypatch.setattr(module,"datetime",Clock)
    args=(snapshot,"2026-03-10",{"beans":20,"carrot":30,"tomato":20})
    current=basket_forecast(*args,replay=False)
    replay=basket_forecast(*args,replay=True)
    assert current["status"] == "forecast"
    assert current["contract_id"] != replay["contract_id"]
    assert "Asia/Colombo" in current["issue_timing"]


def test_weather_candidate_gate_ignores_heldout_missingness():
    from marketbudget.train import development_weather_available
    valid=pd.DataFrame({"wx_rain":[1.,2.]})
    sets={name:valid.copy() for name in ("train","tuning","calibration","test_2025","later_2026")}
    assert development_weather_available(sets,["wx_rain"])
    sets["test_2025"].iloc[:]=np.nan
    assert development_weather_available(sets,["wx_rain"])
    sets["tuning"].iloc[:]=np.nan
    assert not development_weather_available(sets,["wx_rain"])
