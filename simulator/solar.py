"""
solar.py
SIMULATED power meter for the mall rooftop solar system (healthy behaviour only for now).

Healthy rule (simulated):
  - Output follows the sun. Starts after about 7 AM, peaks around 1 PM, ends about 7.30 PM.
  - Clouds and afternoon rain cut the output.
  - Very hot panels lose a little efficiency.
  - At night output is 0 kW.

The system size below is an EXAMPLE value, not a real rooftop at the mall.

Run a quick test from the project folder:
    python simulator\\solar.py
"""

import numpy as np

from environment import make_weather

# Example rooftop (simulated). 200 kWp of panels.
RATED_KWP = 200.0
SUNRISE = 7.2    # about 7.10 AM, typical for Malaysia
SUNSET = 19.4    # about 7.25 PM
PERFORMANCE_RATIO = 0.75  # normal losses in wiring, inverter and dirt


def sun_level(ts):
    """How strong the sun is, from 0 (night) to 1 (midday clear sky)."""
    h = ts.hour + ts.minute / 60.0
    if not (SUNRISE < h < SUNSET):
        return 0.0
    return float(np.sin(np.pi * (h - SUNRISE) / (SUNSET - SUNRISE)))


def solar_power_kw(ts, temp_c, cloud, rng):
    """Healthy solar output in kW for one 15 minute reading."""
    sun = sun_level(ts)
    if sun == 0.0:
        return 0.0

    # Clouds block up to 80% of the sunlight.
    light = sun * (1 - 0.80 * cloud)

    # Panels get hotter than the air in strong sun. They lose 0.4% per degree above 25 C.
    panel_temp = temp_c + 20 * light
    heat_loss = 1 - 0.004 * max(panel_temp - 25, 0)

    # Small random noise, like a real meter (about 3%).
    kw = RATED_KWP * light * PERFORMANCE_RATIO * heat_loss * (1 + rng.normal(0, 0.03))
    return round(max(kw, 0.0), 2)


def make_solar_history(weather, rng):
    """Add a solar_kw column to a weather table."""
    df = weather.copy()
    df["solar_kw"] = [
        solar_power_kw(ts, t, c, rng)
        for ts, t, c in zip(df.index, df["temp_c"], df["cloud"])
    ]
    return df


if __name__ == "__main__":
    rng = np.random.default_rng(42)  # fixed seed, so results repeat
    weather = make_weather(start="2026-08-24", days=60, rng=rng)
    df = make_solar_history(weather, rng)

    out = "data/solar_healthy_test.csv"
    df.to_csv(out, index_label="timestamp")

    daily_kwh = (df["solar_kw"] * 0.25).resample("D").sum()  # 15 min = 0.25 hour

    print("SIMULATED rooftop solar data, healthy only")
    print("Rows:", len(df))
    print("From", df.index[0], "to", df.index[-1])
    print("Power kW  min %.1f  mean %.1f  max %.1f" % (
        df["solar_kw"].min(), df["solar_kw"].mean(), df["solar_kw"].max()))
    print("Daily energy kWh  min %.0f  mean %.0f  max %.0f" % (
        daily_kwh.min(), daily_kwh.mean(), daily_kwh.max()))
    print("Average kWh per kWp per day: %.2f" % (daily_kwh.mean() / RATED_KWP))
    print("Average kW by hour of day:")
    print(df.groupby(df.index.hour)["solar_kw"].mean().round(1).to_string())
    print("Saved to", out)
