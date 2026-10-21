"""
app.py
The DASHBOARD for the maintenance team. ALL DATA IS SIMULATED.

It reads the same SQLite database that edge/subscriber.py fills, runs the
edge detector, and shows the status of the 4 devices. The page refreshes
itself every few seconds, so you can watch the demo live.

What it shows
  Step 1  Live status of the 4 devices (OK, WATCH, FAULT, WAITING)
          "Simulated data" label always on screen
  Step 2  Maintenance list, flagged devices ranked by RM wasted per day,
          with future waste over 30 days in RM and kg CO2
  Step 3  Demo control in the sidebar to inject or clear a SIMULATED fault
  Step 4  Daily report download (.txt) and daily data download (.csv)
  Extra   Time control button that skips 6 SIMULATED hours per click
  Extra   Daily report as PDF (dashboard/pdf_report.py, needs fpdf2)
  Extra   Carbon and savings summary for all flagged devices (edge/carbon.py)

Run from the project folder (publisher and subscriber must be running):
    streamlit run dashboard\\app.py
"""

import os
import sys

import pandas as pd
import streamlit as st

# Let us import the edge code (detector.py and its helpers) from edge/.
EDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "edge")
sys.path.insert(0, os.path.abspath(EDGE_DIR))

from detector import DB_PATH, DEVICES, LIMIT_PCT, check_all, load_readings  # noqa: E402
from projection import GRID_KG_CO2_PER_KWH, TARIFF_RM_PER_KWH  # noqa: E402
from carbon import carbon_summary  # noqa: E402
from pdf_report import make_pdf  # noqa: E402  (dashboard/pdf_report.py)

# Let us import send_fault() from simulator/ for the demo button.
SIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "simulator")
sys.path.insert(0, os.path.abspath(SIM_DIR))
from send_fault import send_fault, send_skip  # noqa: E402

SKIP_HOURS = 6   # simulated hours per click of the "Skip" button

REFRESH_SECONDS = 3   # how often the live part of the page updates

NAMES = {"chiller": "Chiller", "ahu": "AHU fan", "solar": "Rooftop solar",
         "pump": "Chilled water pump"}
SIZES = {"chiller": "500 RT, about 325 kW (example size)",
         "ahu": "30 kW fan (example size)",
         "solar": "200 kWp (example size)",
         "pump": "37 kW with speed drive (example size)"}
# Streamlit colour tags for each status.
COLOURS = {"OK": "green", "WATCH": "orange", "FAULT": "red", "WAITING": "gray"}

st.set_page_config(page_title="Energy Fault Monitor", layout="wide")

st.title("Energy Fault Monitor")
st.caption("Example site. Elmina Lakeside Mall. One edge engine watching many devices.")

# The simulated label stays at the top of the page at all times.
st.warning("SIMULATED DATA. All readings come from a software simulator on this "
           "laptop, not from real sensors. Device sizes are example values.")


@st.fragment(run_every=REFRESH_SECONDS)
def live_status():
    """The live part of the page. Only this part reruns every few seconds."""
    if not os.path.exists(DB_PATH):
        st.info("No data yet. Start publisher.py and subscriber.py first.")
        return

    try:
        readings = load_readings()
    except Exception:
        st.info("Waiting for the first readings from subscriber.py ...")
        return
    if readings.empty:
        st.info("Waiting for the first readings from subscriber.py ...")
        return

    results = check_all()
    latest_time = readings["timestamp"].max()
    st.markdown("**Simulated time now** %s" % latest_time.strftime("%a %d %b %Y, %H:%M"))

    cols = st.columns(len(DEVICES))
    for col, dev in zip(cols, DEVICES):
        r = results[dev]
        dev_rows = readings[readings["device"] == dev]
        with col.container(border=True):
            st.subheader(NAMES[dev])
            st.caption(SIZES[dev])
            st.markdown("### :%s[%s]" % (COLOURS[r["status"]], r["status"]))

            # Latest power reading. For solar this is power produced.
            label = "Power produced now" if dev == "solar" else "Power used now"
            st.metric(label, "%.1f kW" % dev_rows["kw"].iloc[-1])

            # Waste on the latest full day, against this device's limit.
            if r["latest_waste_pct"] is None:
                st.metric("Waste on latest full day", "waiting")
            else:
                st.metric("Waste on latest full day",
                          "%.1f%%" % r["latest_waste_pct"],
                          help="Limit for this device is %.0f%%" % LIMIT_PCT[dev])
            st.caption("Days above the %.0f%% limit in a row: %d"
                       % (LIMIT_PCT[dev], r["days_above"]))

            # Likely cause, only when something is flagged. Never "confirmed".
            if r["likely_cause"]:
                st.write(r["likely_cause"])

            # Small chart of the last 2 simulated days of power.
            last = dev_rows.set_index("timestamp")["kw"]
            last = last[last.index >= latest_time - pd.Timedelta(days=2)]
            st.line_chart(last, height=150)

    st.caption("Status rules. WATCH after 1 full day above the limit. FAULT after "
               "2 full days in a row, or 50% or more on 1 full day. Limits are "
               "tuned for simulated data.")

    maintenance_list(results)
    carbon_panel(results)
    report_downloads(results, latest_time)


def report_text(results, latest_time):
    """Build a plain text daily report that the team can save or print."""
    lines = ["DAILY ENERGY FAULT REPORT",
             "SIMULATED DATA. Not from real sensors. Device sizes are example values.",
             "",
             "Site. Elmina Lakeside Mall (example site)",
             "Simulated time of report. %s" % latest_time.strftime("%a %d %b %Y, %H:%M"),
             ""]

    lines.append("DEVICE STATUS (latest full day)")
    for dev in DEVICES:
        r = results[dev]
        day = r["daily"]
        full = day[day["full_day"]] if not day.empty else day
        if full.empty:
            lines.append("- %s. WAITING, no full day of data yet." % NAMES[dev])
            continue
        last = full.iloc[-1]
        lines.append("- %s. %s. Day %s. Actual %.1f kWh, expected %.1f kWh, "
                     "waste %.1f%% (limit %.0f%%). Days above limit in a row %d." % (
                         NAMES[dev], r["status"], full.index[-1].strftime("%d %b %Y"),
                         last["actual_kwh"], last["expected_kwh"], last["waste_pct"],
                         LIMIT_PCT[dev], r["days_above"]))
    lines.append("")

    lines.append("MAINTENANCE LIST (ranked by RM wasted per day)")
    flagged = [(dev, r) for dev, r in results.items()
               if r["status"] in ("WATCH", "FAULT") and r["projection"]]
    flagged.sort(key=lambda x: x[1]["projection"]["rm_per_day_now"], reverse=True)
    if not flagged:
        lines.append("No action needed. All devices are within their normal range.")
    for rank, (dev, r) in enumerate(flagged, start=1):
        p = r["projection"]
        lines.append("%d. %s, %s. Waste now %.1f kWh/day, RM %.2f/day." % (
            rank, NAMES[dev], r["status"], p["kwh_per_day_now"], p["rm_per_day_now"]))
        lines.append("   Next %d days if not fixed. %s, %s kg CO2." % (
            p["days"], range_text(p["rm_low"], p["rm_high"], "RM "),
            range_text(p["co2_kg_low"], p["co2_kg_high"])))
        lines.append("   %s" % r["likely_cause"])
    lines.append("")

    lines.append("CARBON AND SAVINGS SUMMARY (all flagged devices)")
    s = carbon_summary(results)
    if s is None:
        lines.append("No waste detected. All devices are within their normal range.")
    else:
        lines.append("- Devices needing action. %d" % s["devices_flagged"])
        lines.append("- Wasted so far. %s kWh, RM %s, %s kg CO2." % (
            f"{s['so_far_kwh']:,}", f"{s['so_far_rm']:,}", f"{s['so_far_co2_kg']:,}"))
        lines.append("- Waste now. %.1f kWh/day, RM %.2f/day, %.1f kg CO2/day." % (
            s["now_kwh_per_day"], s["now_rm_per_day"], s["now_co2_kg_per_day"]))
        lines.append("- Can be avoided in the next %d days by fixing now. %s kWh, %s, %s kg CO2." % (
            s["days_ahead"], range_text(s["next_kwh_low"], s["next_kwh_high"]),
            range_text(s["next_rm_low"], s["next_rm_high"], "RM "),
            range_text(s["next_co2_kg_low"], s["next_co2_kg_high"])))
    lines.append("")

    lines += ["NOTES",
              "- Likely cause is a hint to check first. Power data alone cannot "
              "confirm the cause.",
              "- Future waste is energy, money and CO2 lost if nobody fixes the fault. "
              "It is not a prediction of when the machine will break.",
              "- RM uses TNB Medium Voltage General energy charge %.2f sen/kWh. "
              "The tariff is assumed and covers the energy charge only, so the real "
              "cost is likely higher." % (TARIFF_RM_PER_KWH * 100),
              "- CO2 uses %.3f kg per kWh (Energy Commission, Peninsular grid 2023, "
              "provisional)." % GRID_KG_CO2_PER_KWH]
    return "\n".join(lines)


def daily_csv(results):
    """Actual vs expected kWh per day for every device, as CSV text."""
    parts = []
    for dev in DEVICES:
        day = results[dev]["daily"]
        if day.empty:
            continue
        t = day[day["full_day"]][["actual_kwh", "expected_kwh", "waste_kwh", "waste_pct"]].copy()
        t.insert(0, "device", dev)
        t["limit_pct"] = LIMIT_PCT[dev]
        t["above_limit"] = t["waste_pct"] > LIMIT_PCT[dev]   # True or False for that day
        t["simulated"] = True
        parts.append(t)
    if not parts:
        return "device,date,simulated\n"
    table = pd.concat(parts)
    table.index = table.index.strftime("%Y-%m-%d")
    table.index.name = "date"
    return table.to_csv()


def report_downloads(results, latest_time):
    """Download buttons, the daily report (PDF and text) and the daily data (CSV)."""
    st.header("Daily report")
    stamp = latest_time.strftime("%Y-%m-%d")
    col0, col1, col2 = st.columns(3)
    # on_click="ignore" so the page does not reload when you download.
    col0.download_button("Download daily report (.pdf)", make_pdf(results, latest_time, NAMES),
                         file_name="daily_report_%s_SIMULATED.pdf" % stamp,
                         mime="application/pdf", on_click="ignore", width="stretch",
                         type="primary")
    col1.download_button("Download daily report (.txt)", report_text(results, latest_time),
                         file_name="daily_report_%s_SIMULATED.txt" % stamp,
                         mime="text/plain", on_click="ignore", width="stretch")
    col2.download_button("Download daily data (.csv)", daily_csv(results),
                         file_name="daily_data_%s_SIMULATED.csv" % stamp,
                         mime="text/csv", on_click="ignore", width="stretch")
    st.caption("Both files are marked SIMULATED in the file name and inside the file.")


def range_text(low, high, unit_before="", unit_after=""):
    """Show one number if low and high are the same, else 'low to high'."""
    if low == high:
        return "%s%s%s" % (unit_before, f"{low:,}", unit_after)
    return "%s%s to %s%s" % (unit_before, f"{low:,}", f"{high:,}", unit_after)


def maintenance_list(results):
    """Table of flagged devices, the one wasting the most RM per day on top."""
    st.header("Maintenance list")
    st.caption("Ranked by money wasted per day. Fix the top one first. SIMULATED DATA.")

    rows = []
    for dev, r in results.items():
        p = r["projection"]
        if r["status"] not in ("WATCH", "FAULT") or p is None:
            continue
        rows.append({
            "Device": NAMES[dev],
            "Status": r["status"],
            "Waste now (kWh/day)": p["kwh_per_day_now"],
            "Waste now (RM/day)": p["rm_per_day_now"],
            "Next %d days if not fixed (RM)" % p["days"]: range_text(p["rm_low"], p["rm_high"], "RM "),
            "Next %d days if not fixed (kg CO2)" % p["days"]: range_text(p["co2_kg_low"], p["co2_kg_high"]),
            "Likely cause": r["likely_cause"],
        })

    if not rows:
        st.success("No action needed. All devices are within their normal range.")
        return

    table = pd.DataFrame(rows).sort_values("Waste now (RM/day)", ascending=False)
    table.insert(0, "Rank", range(1, len(table) + 1))
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={
                     "Waste now (RM/day)": st.column_config.NumberColumn(format="RM %.2f"),
                     "Likely cause": st.column_config.TextColumn(width="large"),
                 })

    st.caption("Future waste is an estimate of energy, money and CO2 lost if nobody "
               "fixes the fault. It is not a prediction of when the machine will "
               "break. Low means waste stays at today's level. High means a gradual "
               "fault keeps growing (capped). RM uses the TNB Medium Voltage General "
               "energy charge of %.2f sen/kWh, an assumed tariff, energy charge only, "
               "so the real cost is likely higher. CO2 uses %.3f kg per kWh "
               "(Energy Commission, Peninsular grid 2023, provisional)."
               % (TARIFF_RM_PER_KWH * 100, GRID_KG_CO2_PER_KWH))


def carbon_panel(results):
    """Building totals for all flagged devices, for facilities and sustainability teams."""
    st.header("Carbon and savings summary")
    st.caption("All flagged devices added together. SIMULATED DATA.")

    s = carbon_summary(results)
    if s is None:
        st.success("No waste detected. All devices are within their normal range.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Devices needing action", s["devices_flagged"])
    c2.metric("Wasted so far", "RM %s" % f"{s['so_far_rm']:,}",
              help="Waste on the flagged full days already seen")
    c2.caption("%s kWh, %s kg CO2" % (f"{s['so_far_kwh']:,}", f"{s['so_far_co2_kg']:,}"))
    c3.metric("Waste now, per day", "RM %.2f" % s["now_rm_per_day"])
    c3.caption("%.1f kWh, %.1f kg CO2 per day" % (s["now_kwh_per_day"], s["now_co2_kg_per_day"]))
    c4.metric("Avoidable in next %d days" % s["days_ahead"],
              range_text(s["next_rm_low"], s["next_rm_high"], "RM "),
              help="Energy, money and CO2 that fixing the faults now could avoid")
    c4.caption("%s kWh, %s kg CO2" % (range_text(s["next_kwh_low"], s["next_kwh_high"]),
                                     range_text(s["next_co2_kg_low"], s["next_co2_kg_high"])))

    table = pd.DataFrame([{
        "Device": NAMES[x["device"]],
        "Status": x["status"],
        "Flagged days": x["days"],
        "Wasted so far (kg CO2)": x["so_far_co2_kg"],
        "Waste now (kg CO2/day)": x["now_co2_kg_per_day"],
        "Avoidable next %d days (kg CO2)" % s["days_ahead"]:
            range_text(x["next_co2_kg_low"], x["next_co2_kg_high"]),
    } for x in s["rows"]])
    st.dataframe(table, hide_index=True, width="stretch")

    st.caption("For solar, waste is energy the panels failed to make, which the "
               "building then buys from the grid. CO2 uses %.3f kg per kWh "
               "(Energy Commission, Peninsular grid 2023, provisional). RM uses an "
               "assumed tariff, energy charge only." % GRID_KG_CO2_PER_KWH)


# Faults the simulator knows (same names as simulator/faults.py).
FAULT_CHOICES = {
    "chiller": {"Dirty cooling tower (gradual)": "dirty_cooling_tower"},
    "ahu": {"Stuck damper (sudden)": "stuck_damper"},
    "solar": {"Dust on panels (gradual)": "dust",
              "Inverter failure (shutdown)": "inverter_failure"},
    "pump": {"Clogged strainer (gradual)": "clogged_strainer",
             "Speed drive stuck at full speed (sudden)": "vsd_stuck_full"},
}


def demo_control():
    """Sidebar buttons that switch a SIMULATED fault on or off in publisher.py."""
    with st.sidebar:
        st.header("Demo control")
        st.caption("For the demo only. This tells the SIMULATOR to start or stop a "
                   "fault. In a real building, faults happen on their own.")

        dev = st.selectbox("Device", DEVICES, format_func=lambda d: NAMES[d])
        label = st.selectbox("Fault", list(FAULT_CHOICES[dev]))

        col1, col2 = st.columns(2)
        if col1.button("Inject fault", type="primary", width="stretch"):
            try:
                send_fault(dev, FAULT_CHOICES[dev][label])
                st.session_state["last_action"] = "Injected %s on %s" % (label, NAMES[dev])
            except OSError:
                st.session_state["last_action"] = "Could not reach the MQTT broker"
        if col2.button("Clear fault", width="stretch"):
            try:
                send_fault(dev, "none")
                st.session_state["last_action"] = "Cleared fault on %s" % NAMES[dev]
            except OSError:
                st.session_state["last_action"] = "Could not reach the MQTT broker"

        if "last_action" in st.session_state:
            st.info(st.session_state["last_action"])
        st.caption("Detection needs full simulated days, so the status changes "
                   "after about 1 to 4 minutes.")

        # Time control. The simulator sends the next readings at once,
        # so no data is lost, the demo just gets there faster.
        st.header("Time control")
        if st.button("Skip %d hours" % SKIP_HOURS, width="stretch"):
            try:
                send_skip(SKIP_HOURS)
                st.session_state["last_skip"] = "Skipped %d simulated hours" % SKIP_HOURS
            except OSError:
                st.session_state["last_skip"] = "Could not reach the MQTT broker"
        if "last_skip" in st.session_state:
            st.info(st.session_state["last_skip"])
        st.caption("Jumps SIMULATED time ahead. 4 clicks = 1 simulated day. "
                   "All readings in between are still sent and saved.")


demo_control()
live_status()
