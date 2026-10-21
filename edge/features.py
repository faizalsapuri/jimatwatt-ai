"""
features.py
Turns a table of readings into the inputs (features) the XGBoost models use.

Training (train.py) and live detection both call make_features(), so the
model always sees the inputs in exactly the same way.

Inputs used
  hour        hour of day with fractions, 9.25 means 9.15 AM
  dayofweek   0 is Monday, 6 is Sunday
  is_weekend  1 on Saturday and Sunday
  mall_open   1 between 10 AM and 10 PM (simulated mall hours)
  temp_c, humidity, cloud   weather at that time (SIMULATED)
"""

import pandas as pd

OPEN_HOUR = 10    # same simulated mall hours as simulator/environment.py
CLOSE_HOUR = 22

FEATURES = ["hour", "dayofweek", "is_weekend", "mall_open",
            "temp_c", "humidity", "cloud"]


def make_features(df):
    """df must have a DatetimeIndex and the columns temp_c, humidity and cloud."""
    X = pd.DataFrame(index=df.index)
    X["hour"] = df.index.hour + df.index.minute / 60.0
    X["dayofweek"] = df.index.dayofweek
    X["is_weekend"] = (df.index.dayofweek >= 5).astype(int)
    X["mall_open"] = ((df.index.hour >= OPEN_HOUR) &
                      (df.index.hour < CLOSE_HOUR)).astype(int)
    X["temp_c"] = df["temp_c"]
    X["humidity"] = df["humidity"]
    X["cloud"] = df["cloud"]
    return X[FEATURES]
