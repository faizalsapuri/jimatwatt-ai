"""
ahu.py
SIMULATED power sensor for one air handling unit (AHU) fan (healthy behaviour only for now).

Healthy rule (simulated):
  - The AHU fan runs from 9 AM (pre-cooling) until the mall closes at 10 PM.
  - Fan power is fairly steady while running.
  - On hotter afternoons the fan speeds up a little to push more cool air.
  - Weekends are a bit busier, so the fan works a bit harder.
  - Outside running hours the fan is off (0 kW).

The fan size below is an EXAMPLE value, not the real mall AHU.

Run a quick test from the project folder:
    python simulator\\ahu.py
"""

import numpy as np

from environment import CLOSE_HOUR, make_weather

# Example AHU supply fan (simulated). 30 kW motor, normally runs around 60% power.
RATED_KW = 30.0
START_HOUR = 9  # starts with the chiller


def ahu_power_kw(ts, temp_c, rng):
    """Healthy AHU fan power in kW for one 15 minute reading."""
    if not (START_HOUR <= ts.hour < CLOSE_HOUR):
        return 0.0

    # Base fan level about 60%, plus 1% for every degree above 28 C.
    level = 0.60 + 0.01 * (temp_c - 28.0)

    # Weekend (Saturday=5, Sunday=6) has more shoppers.
    if ts.dayofweek >= 5:
        level += 0.03

    level = min(max(level, 0.45), 0.80)

    # Small random noise, like a real sensor (about 2%).
    kw = RATED_KW * level * (1 + rng.normal(0, 0.02))
    return round(max(kw, 0.0), 2)


def make_ahu_history(weather, rng):
    """Add an ahu_kw column to a weather table."""
    df = weather.copy()
    df["ahu_kw"] = [ahu_power_kw(ts, t, rng) for ts, t in zip(df.index, df["temp_c"])]
    return df


if __name__ == "__main__":
    rng = np.random.default_rng(42)  # fixed seed, so results repeat
    weather = make_weather(start="2026-08-24", days=60, rng=rng)
    df = make_ahu_history(weather, rng)

    out = "data/ahu_healthy_test.csv"
    df.to_csv(out, index_label="timestamp")

    daily_kwh = (df["ahu_kw"] * 0.25).resample("D").sum()  # 15 min = 0.25 hour

    print("SIMULATED AHU fan data, healthy only")
    print("Rows:", len(df))
    print("From", df.index[0], "to", df.index[-1])
    print("Power kW  min %.1f  mean %.1f  max %.1f" % (
        df["ahu_kw"].min(), df["ahu_kw"].mean(), df["ahu_kw"].max()))
    print("Daily energy kWh  min %.0f  mean %.0f  max %.0f" % (
        daily_kwh.min(), daily_kwh.mean(), daily_kwh.max()))
    print("Average kW by hour of day:")
    print(df.groupby(df.index.hour)["ahu_kw"].mean().round(1).to_string())
    print("Saved to", out)
