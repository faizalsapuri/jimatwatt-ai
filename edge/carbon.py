"""
carbon.py
CARBON AND SAVINGS SUMMARY for all flagged devices together. ALL DATA IS SIMULATED.

The maintenance list shows each device on its own. This adds them up, so the
facilities and sustainability teams see one total for the whole building.

Three totals, in kWh, RM and kg CO2
  wasted so far   waste on the flagged full days already seen (in a row, up to
                  the latest full day). This already happened.
  waste now       per day, at the latest full day's level
  next 30 days    the low to high range from projection.py, if nobody fixes the
                  faults. This is the amount that fixing them now could avoid.

For solar, "waste" is energy the panels failed to make. The building then buys
that energy from the grid, so it costs the same RM and CO2 per kWh.

Uses the same tariff and CO2 factor as projection.py.
"""

from projection import GRID_KG_CO2_PER_KWH, TARIFF_RM_PER_KWH


def wasted_so_far_kwh(r):
    """kWh wasted on the flagged full days in a row, up to the latest full day."""
    day = r["daily"]
    if day.empty:
        return 0.0
    full = day[day["full_day"]]
    n = max(r["days_above"], 1)
    return float(full["waste_kwh"].iloc[-n:].clip(lower=0).sum())


def carbon_summary(results):
    """
    results   output of detector.check_all()
    Returns a dict with building totals and one row per flagged device,
    biggest CO2 first. Returns None if no device is flagged.
    """
    rows = []
    for dev, r in results.items():
        p = r["projection"]
        if r["status"] not in ("WATCH", "FAULT") or p is None:
            continue
        so_far = wasted_so_far_kwh(r)
        rows.append({
            "device": dev,
            "status": r["status"],
            "days": max(r["days_above"], 1),
            "so_far_kwh": round(so_far),
            "so_far_rm": round(so_far * TARIFF_RM_PER_KWH),
            "so_far_co2_kg": round(so_far * GRID_KG_CO2_PER_KWH),
            "now_kwh_per_day": p["kwh_per_day_now"],
            "now_rm_per_day": p["rm_per_day_now"],
            "now_co2_kg_per_day": round(p["kwh_per_day_now"] * GRID_KG_CO2_PER_KWH, 1),
            "next_kwh_low": p["kwh_low"], "next_kwh_high": p["kwh_high"],
            "next_rm_low": p["rm_low"], "next_rm_high": p["rm_high"],
            "next_co2_kg_low": p["co2_kg_low"], "next_co2_kg_high": p["co2_kg_high"],
        })

    if not rows:
        return None

    rows.sort(key=lambda x: x["next_co2_kg_low"], reverse=True)

    def total(key):
        return sum(x[key] for x in rows)

    return {
        "devices_flagged": len(rows),
        "so_far_kwh": total("so_far_kwh"),
        "so_far_rm": total("so_far_rm"),
        "so_far_co2_kg": total("so_far_co2_kg"),
        "now_kwh_per_day": round(total("now_kwh_per_day"), 1),
        "now_rm_per_day": round(total("now_rm_per_day"), 2),
        "now_co2_kg_per_day": round(total("now_co2_kg_per_day"), 1),
        "next_kwh_low": total("next_kwh_low"), "next_kwh_high": total("next_kwh_high"),
        "next_rm_low": total("next_rm_low"), "next_rm_high": total("next_rm_high"),
        "next_co2_kg_low": total("next_co2_kg_low"), "next_co2_kg_high": total("next_co2_kg_high"),
        "days_ahead": 30,
        "rows": rows,
    }


if __name__ == "__main__":
    # Quick check from the project folder:  python edge\carbon.py
    from detector import check_all
    s = carbon_summary(check_all())
    print("SIMULATED data. Carbon and savings summary")
    if s is None:
        print("No device flagged. Nothing wasted.")
    else:
        print("Devices flagged:", s["devices_flagged"])
        print("Wasted so far   %s kWh | RM %s | %s kg CO2" % (
            s["so_far_kwh"], s["so_far_rm"], s["so_far_co2_kg"]))
        print("Waste now       %s kWh/day | RM %s/day | %s kg CO2/day" % (
            s["now_kwh_per_day"], s["now_rm_per_day"], s["now_co2_kg_per_day"]))
        print("Next 30 days    %s to %s kWh | RM %s to %s | %s to %s kg CO2" % (
            s["next_kwh_low"], s["next_kwh_high"], s["next_rm_low"], s["next_rm_high"],
            s["next_co2_kg_low"], s["next_co2_kg_high"]))
