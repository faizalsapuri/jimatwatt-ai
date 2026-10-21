"""
detector.py
Part of the EDGE COMPUTER. Finds devices that drift away from their normal
behaviour over SEVERAL DAYS. ALL READINGS ARE SIMULATED.

How it works
  1. Read the live readings that subscriber.py saved in data/readings.db.
  2. Ask each trained model "what should this device use (or produce) now?"
  3. Add up actual and expected energy for each full day (kWh per day).
  4. Waste per day
       chiller, ahu  actual - expected   (extra energy used)
       solar         expected - actual   (energy we failed to produce)
  5. Flag a fault only when waste stays above the limit for several days
     in a row. One odd day (a sales event, a holiday) is not enough.

Status for each device
  OK     no recent day above the limit
  WATCH  latest full day is above the limit, waiting for more days
  FAULT  limit passed for DAYS_IN_A_ROW full days in a row,
         or a very big gap (SEVERE_PCT) on the latest full day

The limits below suit our SIMULATED data. With real building data they
would be tuned on a few months of history first.

Run from the project folder (publisher and subscriber can keep running):
    python edge\\detector.py
"""

import os
import sqlite3

import numpy as np
import pandas as pd
import xgboost as xgb

from causes import likely_cause
from features import make_features
from projection import project_waste

DB_PATH = os.path.join("data", "readings.db")
MODEL_DIR = "models"
DEVICES = ["chiller", "ahu", "solar"]

# Limits per device, as % of expected kWh per day.
LIMIT_PCT = {"chiller": 2.0, "ahu": 5.0, "solar": 3.0}
DAYS_IN_A_ROW = 2      # full days above the limit before we say FAULT
SEVERE_PCT = 50.0      # e.g. inverter failure. FAULT after just 1 full day

_models = {}


def load_model(device):
    """Load a trained model once and keep it in memory."""
    if device not in _models:
        m = xgb.XGBRegressor()
        m.load_model(os.path.join(MODEL_DIR, device + ".json"))
        _models[device] = m
    return _models[device]


def load_readings(db_path=DB_PATH):
    """All saved readings as one table, one row per device per 15 minutes."""
    db = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM readings ORDER BY timestamp", db)
    db.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def daily_table(readings, device):
    """
    Actual vs expected kWh for each day of one device.
    Columns: actual_kwh, expected_kwh, waste_kwh, waste_pct, full_day
    """
    d = readings[readings["device"] == device].set_index("timestamp").sort_index()
    if d.empty:
        return pd.DataFrame()

    expected_kw = np.clip(load_model(device).predict(make_features(d)), 0, None)
    d["expected_kw"] = expected_kw

    # A 15 minute reading in kW x 0.25 hours = kWh.
    day = (d[["kw", "expected_kw"]] * 0.25).resample("D").sum()
    day.columns = ["actual_kwh", "expected_kwh"]
    day["readings"] = d["kw"].resample("D").count()
    day["full_day"] = day["readings"] == 96      # 96 x 15 min = 24 hours

    if device == "solar":
        day["waste_kwh"] = day["expected_kwh"] - day["actual_kwh"]
    else:
        day["waste_kwh"] = day["actual_kwh"] - day["expected_kwh"]
    # % only makes sense when we expected a fair amount of energy.
    # (Just after midnight a new day has almost nothing yet.)
    day["waste_pct"] = 100 * day["waste_kwh"] / day["expected_kwh"].where(day["expected_kwh"] >= 1)
    nums = ["actual_kwh", "expected_kwh", "waste_kwh", "waste_pct"]
    day[nums] = day[nums].astype(float).round(1)   # plain numbers, 1 decimal
    return day


def check_device(readings, device):
    """Return a small summary dict with the status of one device."""
    day = daily_table(readings, device)
    full = day[day["full_day"]] if not day.empty else day
    result = {"device": device, "status": "OK", "days_above": 0,
              "latest_waste_pct": None, "shape": None, "likely_cause": None,
              "projection": None, "daily": day}
    if full.empty:
        result["status"] = "WAITING"   # not one full day of live data yet
        return result

    above = full["waste_pct"] > LIMIT_PCT[device]

    # Count full days above the limit, going back from the latest day.
    days_above = 0
    for flag in above[::-1]:
        if not flag:
            break
        days_above += 1

    latest = float(full["waste_pct"].iloc[-1])
    result["days_above"] = days_above
    result["latest_waste_pct"] = latest

    if days_above >= DAYS_IN_A_ROW or latest >= SEVERE_PCT:
        result["status"] = "FAULT"
    elif days_above >= 1:
        result["status"] = "WATCH"

    # Likely cause hint, only when something is flagged.
    if result["status"] in ("WATCH", "FAULT"):
        n = max(days_above, 1)
        flagged = list(full["waste_pct"].iloc[-n:])
        result["shape"], result["likely_cause"] = likely_cause(
            device, flagged, LIMIT_PCT[device])

        # Future waste over the next 30 days if nobody fixes it.
        result["projection"] = project_waste(
            device,
            list(full["waste_kwh"].iloc[-n:]),
            list(full["expected_kwh"].iloc[-n:]),
            result["shape"])
    return result


def check_all(db_path=DB_PATH):
    readings = load_readings(db_path)
    return {dev: check_device(readings, dev) for dev in DEVICES}


def main():
    results = check_all()
    print("SIMULATED data. Daily check of actual vs expected energy\n")
    for dev, r in results.items():
        print("=== %s  status %s  (days above %.0f%% limit in a row: %d)" % (
            dev.upper(), r["status"], LIMIT_PCT[dev], r["days_above"]))
        if r["likely_cause"]:
            print("Likely cause hint (%s):" % r["shape"], r["likely_cause"])
        p = r["projection"]
        if p:
            print("Waste now  %.1f kWh/day = RM %.2f/day" % (
                p["kwh_per_day_now"], p["rm_per_day_now"]))
            if p["kwh_low"] == p["kwh_high"]:   # flat fault, one number is enough
                print("Next %d days if not fixed  %s kWh | RM %s | %s kg CO2" % (
                    p["days"], p["kwh_low"], p["rm_low"], p["co2_kg_low"]))
            else:
                print("Next %d days if not fixed  %s to %s kWh | RM %s to %s | %s to %s kg CO2" % (
                    p["days"], p["kwh_low"], p["kwh_high"], p["rm_low"], p["rm_high"],
                    p["co2_kg_low"], p["co2_kg_high"]))
        if not r["daily"].empty:
            print(r["daily"][["actual_kwh", "expected_kwh", "waste_kwh",
                              "waste_pct", "full_day"]].to_string())
        print()
    print("RM uses TNB MV General energy charge 29.83 sen/kWh (assumed tariff). "
          "CO2 uses 0.760 kg/kWh (Energy Commission, Peninsular 2023, provisional).")


if __name__ == "__main__":
    main()
