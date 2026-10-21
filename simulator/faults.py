"""
faults.py
SIMULATED faults that can be switched on for each device.

Each fault changes the healthy power reading in a simple, explainable way.
These are made-up fault shapes for the demo, not measured fault data.

  Device   Fault                What it does to the reading
  -------  -------------------  ---------------------------------------------
  chiller  dirty_cooling_tower  Power slowly creeps up, +1.5% per day, up to +25%
  ahu      stuck_damper         Fan power jumps up 35% and stays high
  solar    dust                 Output slowly drops, -1% per day, down to -30%
  solar    inverter_failure     Output falls to 0 kW straight away
  pump     clogged_strainer     Power slowly creeps up, +2% per day, up to +25%
  pump     vsd_stuck_full       Drive stuck at full speed, power jumps to 95% of rated

A fault is a small dict, for example
    {"type": "dirty_cooling_tower", "start": pd.Timestamp("2026-10-23 00:00")}

Run a quick test from the project folder:
    python simulator\\faults.py
"""

import pandas as pd

from pump import RATED_KW as PUMP_RATED_KW

FAULT_TYPES = {
    "chiller": ["dirty_cooling_tower"],
    "ahu": ["stuck_damper"],
    "solar": ["dust", "inverter_failure"],
    "pump": ["clogged_strainer", "vsd_stuck_full"],
}


def days_since(ts, start):
    """How many days (with fractions) the fault has been active."""
    return max((ts - start).total_seconds() / 86400.0, 0.0)


def apply_fault(device, kw, ts, fault):
    """
    Return the reading after the fault is applied.
    If there is no fault, or it has not started yet, return the healthy reading.
    """
    if fault is None or ts < fault["start"] or kw == 0.0:
        return kw

    d = days_since(ts, fault["start"])
    ftype = fault["type"]

    if device == "chiller" and ftype == "dirty_cooling_tower":
        extra = min(0.015 * d, 0.25)
        return round(kw * (1 + extra), 2)

    if device == "ahu" and ftype == "stuck_damper":
        return round(kw * 1.35, 2)

    if device == "solar" and ftype == "dust":
        loss = min(0.01 * d, 0.30)
        return round(kw * (1 - loss), 2)

    if device == "solar" and ftype == "inverter_failure":
        return 0.0

    if device == "pump" and ftype == "clogged_strainer":
        extra = min(0.02 * d, 0.25)
        return round(kw * (1 + extra), 2)

    if device == "pump" and ftype == "vsd_stuck_full":
        # The drive no longer slows the pump down, so it runs near full power.
        return round(PUMP_RATED_KW * 0.95, 2)

    raise ValueError("Unknown fault %s for device %s" % (ftype, device))


if __name__ == "__main__":
    import numpy as np

    from ahu import ahu_power_kw
    from chiller import chiller_power_kw
    from environment import make_weather
    from pump import pump_power_kw
    from solar import solar_power_kw

    # 60 healthy days, then 20 days with a fault switched on.
    rng = np.random.default_rng(42)
    weather = make_weather(start="2026-08-24", days=80, rng=rng)
    fault_start = weather.index[0] + pd.Timedelta(days=60)

    tests = [
        ("chiller", "dirty_cooling_tower"),
        ("ahu", "stuck_damper"),
        ("solar", "dust"),
        ("solar", "inverter_failure"),
        ("pump", "clogged_strainer"),
        ("pump", "vsd_stuck_full"),
    ]

    print("SIMULATED fault test. Fault starts on", fault_start.date())
    for device, ftype in tests:
        fault = {"type": ftype, "start": fault_start}
        rng = np.random.default_rng(7)  # same noise for healthy and faulty runs
        healthy, faulty = [], []
        for ts, row in weather.iterrows():
            if device == "chiller":
                kw = chiller_power_kw(ts, row["temp_c"], rng)
            elif device == "ahu":
                kw = ahu_power_kw(ts, row["temp_c"], rng)
            elif device == "pump":
                kw = pump_power_kw(ts, row["temp_c"], rng)
            else:
                kw = solar_power_kw(ts, row["temp_c"], row["cloud"], rng)
            healthy.append(kw)
            faulty.append(apply_fault(device, kw, ts, fault))

        df = pd.DataFrame({"healthy": healthy, "faulty": faulty}, index=weather.index)
        daily = (df * 0.25).resample("D").sum()  # kWh per day
        before = daily["faulty"].iloc[50:60].mean()
        after_5 = daily["faulty"].iloc[60:65].mean()
        after_last = daily["faulty"].iloc[75:80].mean()

        print("\n%s / %s" % (device, ftype))
        print("  Avg kWh per day, 10 days before fault : %.0f" % before)
        print("  Avg kWh per day, first 5 fault days   : %.0f" % after_5)
        print("  Avg kWh per day, last 5 fault days    : %.0f" % after_last)
