"""
pump.py
SIMULATED power sensor for the chilled water pump (healthy behaviour only).

The pump pushes cold water from the chiller to the AHUs. It has a variable
speed drive (VSD), so it slows down when less cooling is needed.

Healthy rule (simulated):
  - The pump runs with the chiller, from 9 AM (pre-cooling) until 10 PM.
  - Pump power goes up a little with outdoor temperature (more cooling needed).
  - Weekends are a bit busier, so the pump works a bit harder.
  - The pre-cooling hour runs a bit harder, like the chiller.
  - Outside running hours the pump is off (0 kW).

The pump size below is an EXAMPLE value, not the real mall pump.

This 4th device shows that the SAME edge engine (one XGBoost model per device,
same detector, same report) can watch a new device type with no new AI code.

Run a quick test from the project folder:
    python simulator\\pump.py
"""

import numpy as np

from environment import CLOSE_HOUR, make_weather

# Example chilled water pump (simulated). 37 kW motor with a VSD,
# normally runs around half power.
RATED_KW = 37.0
START_HOUR = 9  # starts with the chiller


def pump_power_kw(ts, temp_c, rng):
    """Healthy chilled water pump power in kW for one 15 minute reading."""
    if not (START_HOUR <= ts.hour < CLOSE_HOUR):
        return 0.0

    # Base level about 50% at 28 C, plus 1.5% for every extra degree.
    level = 0.50 + 0.015 * (temp_c - 28.0)

    # Weekend (Saturday=5, Sunday=6) has more shoppers.
    if ts.dayofweek >= 5:
        level += 0.03

    # Pre-cooling hour runs a bit harder, like the chiller.
    if ts.hour == START_HOUR:
        level += 0.05

    level = min(max(level, 0.35), 0.75)

    # Small random noise, like a real sensor (about 2%).
    kw = RATED_KW * level * (1 + rng.normal(0, 0.02))
    return round(max(kw, 0.0), 2)


def make_pump_history(weather, rng):
    """Add a pump_kw column to a weather table."""
    df = weather.copy()
    df["pump_kw"] = [pump_power_kw(ts, t, rng) for ts, t in zip(df.index, df["temp_c"])]
    return df


if __name__ == "__main__":
    rng = np.random.default_rng(42)  # fixed seed, so results repeat
    weather = make_weather(start="2026-08-24", days=60, rng=rng)
    df = make_pump_history(weather, rng)

    out = "data/pump_healthy_test.csv"
    df.to_csv(out, index_label="timestamp")

    daily_kwh = (df["pump_kw"] * 0.25).resample("D").sum()  # 15 min = 0.25 hour

    print("SIMULATED chilled water pump data, healthy only")
    print("Rows:", len(df))
    print("From", df.index[0], "to", df.index[-1])
    print("Power kW  min %.1f  mean %.1f  max %.1f" % (
        df["pump_kw"].min(), df["pump_kw"].mean(), df["pump_kw"].max()))
    print("Daily energy kWh  min %.0f  mean %.0f  max %.0f" % (
        daily_kwh.min(), daily_kwh.mean(), daily_kwh.max()))
    print("Average kW by hour of day:")
    print(df.groupby(df.index.hour)["pump_kw"].mean().round(1).to_string())
    print("Saved to", out)
