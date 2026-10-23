"""
environment.py
Shared SIMULATED conditions for the example site (KL East Mall).

Gives every device the same weather and the same mall opening hours,
so the chiller, AHU and solar all react to the same "day".

ALL VALUES HERE ARE SIMULATED. They are rough Malaysian-style patterns,
not real measurements from the mall.
"""

import numpy as np
import pandas as pd

# Mall opening hours (simulated example). 10 AM to 10 PM every day.
OPEN_HOUR = 10
CLOSE_HOUR = 22


def is_mall_open(ts):
    """True if the mall is open at this timestamp."""
    return OPEN_HOUR <= ts.hour < CLOSE_HOUR


def make_weather(start, days, rng, freq="15min"):
    """
    Build a simulated weather table, one row per 15 minutes.

    Columns:
      temp_c    outdoor temperature in Celsius (about 24 at night, 32 to 34 in the afternoon)
      humidity  relative humidity in % (higher when it is cooler)
      cloud     cloud level from 0 (clear sky) to 1 (fully cloudy)
    """
    idx = pd.date_range(start=start, periods=days * 24 * 4, freq=freq)
    hours = idx.hour + idx.minute / 60.0

    # One random value per day, so some days are hotter or cloudier than others.
    n_days = days
    day_temp_offset = rng.normal(0.0, 1.0, n_days)      # hotter or cooler day
    day_cloud = rng.uniform(0.1, 0.5, n_days)           # base cloud level
    rainy_day = rng.random(n_days) < 0.35               # about 1 in 3 days has afternoon rain

    day_no = (idx.normalize() - idx[0].normalize()).days

    # Daily temperature curve. Lowest about 3 AM, highest about 3 PM.
    temp = 28.0 + 4.0 * np.sin(2 * np.pi * (hours - 9) / 24)
    temp = temp + day_temp_offset[day_no]

    # Afternoon rain (2 PM to 6 PM) cools things down and adds cloud.
    afternoon = (hours >= 14) & (hours < 18)
    rain_now = rainy_day[day_no] & afternoon
    temp = np.where(rain_now, temp - 2.5, temp)

    cloud = day_cloud[day_no] + np.where(rain_now, 0.45, 0.0)
    cloud = np.clip(cloud + rng.normal(0, 0.05, len(idx)), 0.0, 1.0)

    # Small reading-to-reading noise on temperature.
    temp = temp + rng.normal(0, 0.3, len(idx))

    # Humidity goes up when it is cooler, typical of Malaysia.
    humidity = np.clip(95 - 2.5 * (temp - 24) + rng.normal(0, 2, len(idx)), 55, 99)

    return pd.DataFrame(
        {"temp_c": temp.round(2), "humidity": humidity.round(1), "cloud": cloud.round(2)},
        index=idx,
    )
