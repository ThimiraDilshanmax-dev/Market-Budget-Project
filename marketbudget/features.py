"""Calendar-aligned as-of features and unfilled seven-day target labels."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import COMMODITIES, HORIZON_DAYS, MAX_PRICE_AGE, MIN_OBSERVATIONS, WEATHER_BUFFER

PRICE_FEATURES = ["commodity_id", "latest", "age", "lag7", "lag14", "lag28",
                  "mean7", "mean14", "mean28", "count7", "count14", "count28",
                  "vol7", "vol28", "momentum7", "momentum28", "annual_sin", "annual_cos", "weekday"]


def make_features(prices: pd.DataFrame, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    source = prices.copy()
    source["date"] = pd.to_datetime(source.date)
    if source.duplicated(["date", "commodity"]).any():
        raise ValueError("Duplicate canonical prices")
    if ((source.price <= 0) | np.isinf(source.price)).any():
        raise ValueError("Prices must be positive or missing")
    dates = pd.date_range(source.date.min(), source.date.max(), freq="D")
    # Schedule only dates that occur in the price source, including missing quotes.
    schedule = pd.DatetimeIndex(sorted(source.date.unique()))
    frames = []
    for code, commodity in enumerate(COMMODITIES):
        series = source[source.commodity == commodity].set_index("date").price.reindex(dates)
        frame = pd.DataFrame(index=dates)
        frame.index.name = "date"
        frame["commodity"] = commodity
        frame["commodity_id"] = code
        frame["observed"] = series
        frame["latest"] = series.ffill()
        last_dates = pd.Series(dates, index=dates).where(series.notna()).ffill()
        frame["last_price_date"] = last_dates
        frame["age"] = (pd.Series(dates, index=dates) - last_dates).dt.days
        for lag in (7, 14, 28):
            frame[f"lag{lag}"] = series.ffill().shift(lag)
        for window in (7, 14, 28):
            frame[f"mean{window}"] = series.rolling(window, min_periods=1).mean()
            frame[f"count{window}"] = series.rolling(window, min_periods=1).count()
        frame["vol7"] = series.rolling(7, min_periods=2).std().fillna(0) / frame.latest
        frame["vol28"] = series.rolling(28, min_periods=2).std().fillna(0) / frame.latest
        frame["momentum7"] = frame.latest / frame.lag7 - 1
        frame["momentum28"] = frame.latest / frame.lag28 - 1
        frame["annual_sin"] = np.sin(2 * np.pi * dates.dayofyear / 365.25)
        frame["annual_cos"] = np.cos(2 * np.pi * dates.dayofyear / 365.25)
        frame["weekday"] = dates.dayofweek
        # Reverse rolling: at d this covers precisely d+1,...,d+7.
        future = pd.concat([series.shift(-i) for i in range(1, HORIZON_DAYS + 1)], axis=1)
        frame["label_count"] = future.count(axis=1)
        frame["target_end"] = dates + pd.Timedelta(days=HORIZON_DAYS)
        frame["target"] = future.mean(axis=1).where(
            (frame.label_count >= MIN_OBSERVATIONS) & (frame.target_end <= dates.max()))
        frame["target_ratio"] = frame.target / frame.latest - 1
        # Prior-year weekly labels are legal only when their entire window precedes issue.
        previous = dates - pd.DateOffset(years=1)
        frame["seasonal"] = pd.Series(frame.target.reindex(previous).to_numpy(), index=dates)
        frame["seasonal"] = frame.seasonal.fillna(frame.latest)
        frame["eligible"] = (frame.age <= MAX_PRICE_AGE) & (frame.count28 >= 5) & frame.lag28.notna()
        frames.append(frame.loc[schedule])
    result = pd.concat(frames).rename_axis("date").reset_index()
    if weather is not None and not weather.empty:
        weather = weather.copy()
        weather.index = pd.to_datetime(weather.index)
        weather = weather.reindex(dates)
        engineered = {}
        for column in weather.columns:
            for window in (7, 14):
                values = weather[column].rolling(window, min_periods=window)
                # d-7 is the newest allowed weather day. Never use a future vintage.
                feature = values.sum() if "prectot" in column else values.mean()
                engineered[f"wx_{column}_{window}"] = feature.shift(WEATHER_BUFFER)
        result = result.merge(pd.DataFrame(engineered, index=dates), left_on="date", right_index=True, how="left")
    return result.sort_values(["date", "commodity"]).reset_index(drop=True)


def split(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Purge every row whose label extends beyond its split's calendar boundary."""
    return frame[(frame.date >= pd.Timestamp(start)) & (frame.target_end <= pd.Timestamp(end)) &
                 frame.eligible & frame.target.notna()].copy()

