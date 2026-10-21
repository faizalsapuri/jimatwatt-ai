"""
generate_history.py
Creates about 60 days of SIMULATED healthy history for all 3 devices.

This is the "normal behaviour" the edge AI learns from before the live demo starts.
No faults are switched on here.

Output file: data/history.csv
  timestamp, temp_c, humidity, cloud, chiller_kw, ahu_kw, solar_kw, simulated

Run from the project folder:
    python simulator\\generate_history.py
"""

import numpy as np
import pandas as pd

from ahu import ahu_power_kw
from chiller import chiller_power_kw
from environment import make_weather
from solar import solar_power_kw

HISTORY_DAYS = 60
HISTORY_END = pd.Timestamp("2026-10-23 00:00")   # live demo data starts from here
OUT_FILE = "data/history.csv"
SEED = 42  # fixed seed, so every team member gets the same history


def main():
    rng = np.random.default_rng(SEED)
    start = HISTORY_END - pd.Timedelta(days=HISTORY_DAYS)
    df = make_weather(start=start, days=HISTORY_DAYS, rng=rng)

    chiller, ahu, solar = [], [], []
    for ts, row in df.iterrows():
        chiller.append(chiller_power_kw(ts, row["temp_c"], rng))
        ahu.append(ahu_power_kw(ts, row["temp_c"], rng))
        solar.append(solar_power_kw(ts, row["temp_c"], row["cloud"], rng))

    df["chiller_kw"] = chiller
    df["ahu_kw"] = ahu
    df["solar_kw"] = solar
    df["simulated"] = True  # honest label carried with every row

    df.to_csv(OUT_FILE, index_label="timestamp")

    daily = (df[["chiller_kw", "ahu_kw", "solar_kw"]] * 0.25).resample("D").sum()
    print("SIMULATED healthy history created")
    print("Rows:", len(df), " Days:", len(daily))
    print("From", df.index[0], "to", df.index[-1])
    print("Average kWh per day")
    print(daily.mean().round(0).to_string())
    print("Saved to", OUT_FILE)


if __name__ == "__main__":
    main()
