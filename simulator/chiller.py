"""
chiller.py
SIMULATED power sensor for the mall chiller (healthy behaviour only for now).

Healthy rule (simulated):
  - The chiller runs from 9 AM (pre-cooling) until the mall closes at 10 PM.
  - When running, power goes up with outdoor temperature.
  - Weekends are a bit busier, so the cooling load is a bit higher.
  - Outside running hours the chiller is off (0 kW).

The chiller size below is an EXAMPLE value, not the real mall chiller.

Run a quick test from the project folder:
    python simulator\\chiller.py
"""

import numpy as np
import pandas as pd

from environment import CLOSE_HOUR, make_weather

# Example chiller (simulated). 500 refrigeration tons at about 0.65 kW per ton.
RATED_KW = 325.0
START_HOUR = 9  # pre-cooling starts 1 hour before the mall opens


def chiller_power_kw(ts, temp_c, rng):
    """Healthy chiller power in kW for one 15 minute reading."""
    if not (START_HOUR <= ts.hour < CLOSE_HOUR):
        return 0.0

    # Part load. About 35% at 26 C, rising 4% for every extra degree.
    load = 0.35 + 0.04 * (temp_c - 26.0)

    # Weekend (Saturday=5, Sunday=6) has more shoppers.
    if ts.dayofweek >= 5:
        load += 0.05

    # Pre-cooling hour runs a bit harder to cool the empty mall.
    if ts.hour == START_HOUR:
        load += 0.10

    load = min(max(load, 0.20), 0.95)

    # Small random noise, like a real sensor (about 3%).
    kw = RATED_KW * load * (1 + rng.normal(0, 0.03))
    return round(max(kw, 0.0), 2)


def make_chiller_history(weather, rng):
    """Add a chiller_kw column to a weather table."""
    df = weather.copy()
    df["chiller_kw"] = [
        chiller_power_kw(ts, t, rng) for ts, t in zip(df.index, df["temp_c"])
    ]
    return df


if __name__ == "__main__":
    rng = np.random.default_rng(42)  # fixed seed, so results repeat
    weather = make_weather(start="2026-08-24", days=60, rng=rng)
    df = make_chiller_history(weather, rng)

    out = "data/chiller_healthy_test.csv"
    df.to_csv(out, index_label="timestamp")

    daily_kwh = (df["chiller_kw"] * 0.25).resample("D").sum()  # 15 min = 0.25 hour

    print("SIMULATED chiller data, healthy only")
    print("Rows:", len(df))
    print("From", df.index[0], "to", df.index[-1])
    print("Power kW  min %.1f  mean %.1f  max %.1f" % (
        df["chiller_kw"].min(), df["chiller_kw"].mean(), df["chiller_kw"].max()))
    print("Daily energy kWh  min %.0f  mean %.0f  max %.0f" % (
        daily_kwh.min(), daily_kwh.mean(), daily_kwh.max()))
    print("Average kW by hour of day:")
    print(df.groupby(df.index.hour)["chiller_kw"].mean().round(1).to_string())
    print("Saved to", out)
