"""
projection.py
Estimates the FUTURE WASTE of a flagged device over the next 30 days,
if nobody fixes it. It does NOT predict when a machine will break down.

We give two numbers, a range
  low   waste stays at today's level (average of the flagged days)
  high  waste keeps growing at the same speed as during the flagged days
        (only for "gradual" faults, a sudden or shutdown fault stays flat)
The high case stops growing at a limit. Solar cannot lose more than 100% of
its output. For chiller, AHU and pump we ASSUME extra use stops at 30% of expected.

Units
  kWh     energy wasted (or, for solar, energy not produced)
  RM      kWh x TARIFF_RM_PER_KWH
  kg CO2  kWh x GRID_KG_CO2_PER_KWH

Settings and where they come from
  TARIFF_RM_PER_KWH = 0.2983
      TNB Medium Voltage General energy charge, 29.83 sen/kWh, from 1 July 2025.
      ASSUMPTION that the mall is on this tariff. Energy charge only, it leaves
      out capacity, network, AFA, KWTBB and SST, so the real RM is likely higher.
  GRID_KG_CO2_PER_KWH = 0.760
      Energy Commission, Peninsular Malaysia grid emission factor 2023
      (provisional), 0.760 tCO2e per MWh.
"""

import numpy as np

TARIFF_RM_PER_KWH = 0.2983
GRID_KG_CO2_PER_KWH = 0.760
DAYS_AHEAD = 30
MAX_EXTRA_FRACTION = 0.30   # demo assumption, see the high case below


def project_waste(device, flagged_waste_kwh, flagged_expected_kwh, shape, days=DAYS_AHEAD):
    """
    device                chiller, ahu, solar or pump
    flagged_waste_kwh     waste kWh of each flagged full day, oldest first
    flagged_expected_kwh  expected kWh of the same days
    shape                 "gradual", "sudden" or "shutdown" (from causes.py)
    Returns a dict with today's waste per day and the 30 day low and high totals.
    """
    waste = np.array(flagged_waste_kwh, dtype=float)
    expected_per_day = float(np.mean(flagged_expected_kwh))
    if len(waste) == 0 or expected_per_day <= 0:
        return None

    now_per_day = float(waste[-1])          # latest full day

    # Low case. Waste stays where it is now.
    low_daily = np.full(days, now_per_day)

    # High case. Keep the trend going, only for gradual faults with 2+ days.
    slope = 0.0
    if shape == "gradual" and len(waste) >= 2:
        slope = max(float(np.polyfit(np.arange(len(waste)), waste, 1)[0]), 0.0)
    high_daily = now_per_day + slope * np.arange(1, days + 1)

    # Upper limit per day, so a trend cannot grow without end.
    #   solar  cannot lose more than 100% of its expected output
    #   others ASSUMPTION for the demo, extra use stops growing at 30% of
    #          expected (or today's level if already higher)
    if device == "solar":
        cap = expected_per_day
    else:
        cap = max(MAX_EXTRA_FRACTION * expected_per_day, now_per_day)
    low_daily = np.clip(low_daily, 0, cap)
    high_daily = np.clip(high_daily, 0, cap)

    low_kwh, high_kwh = float(low_daily.sum()), float(high_daily.sum())
    return {
        "kwh_per_day_now": round(now_per_day, 1),
        "rm_per_day_now": round(now_per_day * TARIFF_RM_PER_KWH, 2),
        "trend_kwh_per_day": round(slope, 2),
        "days": days,
        "kwh_low": round(low_kwh),
        "kwh_high": round(high_kwh),
        "rm_low": round(low_kwh * TARIFF_RM_PER_KWH),
        "rm_high": round(high_kwh * TARIFF_RM_PER_KWH),
        "co2_kg_low": round(low_kwh * GRID_KG_CO2_PER_KWH),
        "co2_kg_high": round(high_kwh * GRID_KG_CO2_PER_KWH),
    }
