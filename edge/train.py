"""
train.py
Trains one XGBoost "normal behaviour" model per device. Runs on the LAPTOP.
The edge part only loads these saved models later.

Data   data/history.csv, about 60 days of SIMULATED healthy readings
Output models/chiller.json, models/ahu.json, models/solar.json
       models/metrics.json  (accuracy numbers, shown later on the dashboard)

How we check accuracy
  1. Train on the first 48 days, test on the last 12 days the model never saw.
  2. Score with CV(RMSE) and NMBE, the two numbers ASHRAE Guideline 14 uses.
       Hourly limits   CV(RMSE) up to 30%, NMBE within +/- 10%
       Daily limits    we use the stricter monthly limits, 15% and +/- 5%
  3. If it looks good, retrain on all 60 days and save the model.

Run from the project folder:
    python edge\\train.py
"""

import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb

from features import make_features

HISTORY_FILE = os.path.join("data", "history.csv")
MODEL_DIR = "models"
DEVICES = ["chiller", "ahu", "solar"]
TEST_DAYS = 12

# Small, simple settings. Enough for this data and fast to train.
PARAMS = dict(n_estimators=400, max_depth=5, learning_rate=0.05,
              subsample=0.9, random_state=42)


def cv_rmse(actual, predicted):
    """Typical size of the error, as % of the average reading. Lower is better."""
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))
    return 100 * rmse / np.mean(actual)


def nmbe(actual, predicted):
    """Average bias, as % of the average reading. Near 0 is best."""
    return 100 * np.sum(actual - predicted) / (len(actual) * np.mean(actual))


def score(actual, predicted):
    """Score at hourly and daily level (energy in kWh, 15 min kW x 0.25 h)."""
    df = pd.DataFrame({"a": actual * 0.25, "p": predicted * 0.25})
    hourly = df.resample("h").sum()
    daily = df.resample("D").sum()
    # Night hours where both are 0 kWh tell us nothing, so skip them.
    hourly = hourly[(hourly["a"] > 0) | (hourly["p"] > 0)]
    # float() turns numpy numbers into plain Python numbers, so JSON can save them.
    return {
        "hourly_cv_rmse": round(float(cv_rmse(hourly["a"], hourly["p"])), 1),
        "hourly_nmbe": round(float(nmbe(hourly["a"], hourly["p"])), 1),
        "daily_cv_rmse": round(float(cv_rmse(daily["a"], daily["p"])), 1),
        "daily_nmbe": round(float(nmbe(daily["a"], daily["p"])), 1),
    }


def passes(m):
    return bool(m["hourly_cv_rmse"] <= 30 and abs(m["hourly_nmbe"]) <= 10 and
                m["daily_cv_rmse"] <= 15 and abs(m["daily_nmbe"]) <= 5)


def main():
    df = pd.read_csv(HISTORY_FILE, index_col="timestamp", parse_dates=True)
    X = make_features(df)

    split = df.index[-1].normalize() - pd.Timedelta(days=TEST_DAYS - 1)
    train_mask = df.index < split

    os.makedirs(MODEL_DIR, exist_ok=True)
    all_metrics = {}
    print("Training on SIMULATED healthy history,", len(df), "rows")
    print("Test period", split.date(), "to", df.index[-1].date(), "\n")

    for device in DEVICES:
        y = df[device + "_kw"]

        # 1 and 2. Train on early days, score on unseen later days.
        model = xgb.XGBRegressor(**PARAMS)
        model.fit(X[train_mask], y[train_mask])
        pred = np.clip(model.predict(X[~train_mask]), 0, None)
        m = score(y[~train_mask], pd.Series(pred, index=y[~train_mask].index))
        m["pass"] = passes(m)
        all_metrics[device] = m

        print("%-8s hourly CV(RMSE) %5.1f%%  NMBE %5.1f%% | daily CV(RMSE) %5.1f%%  NMBE %5.1f%% | %s" % (
            device, m["hourly_cv_rmse"], m["hourly_nmbe"],
            m["daily_cv_rmse"], m["daily_nmbe"], "PASS" if m["pass"] else "CHECK"))

        # 3. Retrain on all 60 days and save.
        final = xgb.XGBRegressor(**PARAMS)
        final.fit(X, y)
        final.save_model(os.path.join(MODEL_DIR, device + ".json"))

    all_metrics["note"] = "Scored on SIMULATED data, last %d days held out" % TEST_DAYS
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(all_metrics, f, indent=2)

    print("\nModels saved to", MODEL_DIR + "/")
    print("Metrics saved to", os.path.join(MODEL_DIR, "metrics.json"))


if __name__ == "__main__":
    main()
