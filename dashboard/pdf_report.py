"""
pdf_report.py
Makes the DAILY REPORT as a PDF file, for the dashboard download button.
ALL DATA IS SIMULATED, and the PDF says so on every page.

It shows the same facts as the .txt report
  1. Device status for the latest full day
  2. Maintenance list, ranked by RM wasted per day
  3. Notes on likely cause, future waste, tariff and CO2 factor

Uses fpdf2 (pip install fpdf2). Built in Helvetica font, so text must be
plain English letters (no special symbols).
"""

from fpdf import FPDF
from fpdf.fonts import FontFace

from detector import DEVICES, LIMIT_PCT
from projection import GRID_KG_CO2_PER_KWH, TARIFF_RM_PER_KWH

# Colours (red, green, blue from 0 to 255)
STATUS_RGB = {"OK": (34, 139, 34), "WATCH": (230, 140, 0),
              "FAULT": (200, 30, 30), "WAITING": (120, 120, 120)}
HEADER_FILL = (40, 60, 90)       # dark blue table header
BANNER_FILL = (255, 236, 179)    # light yellow "simulated" banner


def range_text(low, high, before="", after=""):
    """One number if low and high are equal, else 'low to high'."""
    if low == high:
        return "%s%s%s" % (before, f"{low:,}", after)
    return "%s%s to %s%s" % (before, f"{low:,}", f"{high:,}", after)


class ReportPDF(FPDF):
    """A4 page with a SIMULATED footer on every page."""

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, "SIMULATED DATA. Prototype for SDP University Hackathon 2026. "
                        "Page %d" % self.page_no(), align="C")


def section_title(pdf, text):
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


def make_pdf(results, latest_time, names):
    """
    results      output of detector.check_all()
    latest_time  latest simulated timestamp (pandas Timestamp)
    names        nice device names, e.g. {"ahu": "AHU fan"}
    Returns the PDF as bytes, ready for st.download_button.
    """
    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Daily Energy Fault Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Site. Elmina Lakeside Mall (example site)", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Simulated time of report. %s" % latest_time.strftime("%a %d %b %Y, %H:%M"),
             new_x="LMARGIN", new_y="NEXT")

    # Simulated banner, always at the top
    pdf.ln(2)
    pdf.set_fill_color(*BANNER_FILL)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 6, "SIMULATED DATA. All readings come from a software simulator, "
                         "not from real sensors. Device sizes are example values.",
                   border=1, fill=True, padding=2, align="L",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(255, 255, 255)   # back to white so tables are not yellow

    # 1. Device status
    section_title(pdf, "1. Device status (latest full day)")
    pdf.set_font("Helvetica", "", 9)
    head_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=HEADER_FILL)
    with pdf.table(col_widths=(30, 20, 22, 26, 26, 20, 16, 20),
                   headings_style=head_style, text_align="CENTER",
                   line_height=6) as table:
        table.row(["Device", "Status", "Day", "Actual kWh", "Expected kWh",
                   "Waste %", "Limit %", "Days above"])
        for dev in DEVICES:
            r = results[dev]
            day = r["daily"]
            full = day[day["full_day"]] if not day.empty else day
            row = table.row()
            row.cell(names[dev])
            row.cell(r["status"], style=FontFace(emphasis="BOLD",
                                                 color=STATUS_RGB[r["status"]]))
            if full.empty:
                for _ in range(6):
                    row.cell("-")
                continue
            last = full.iloc[-1]
            row.cell(full.index[-1].strftime("%d %b"))
            row.cell("%.1f" % last["actual_kwh"])
            row.cell("%.1f" % last["expected_kwh"])
            row.cell("%.1f" % last["waste_pct"])
            row.cell("%.0f" % LIMIT_PCT[dev])
            row.cell(str(r["days_above"]))

    # 2. Maintenance list
    section_title(pdf, "2. Maintenance list (ranked by RM wasted per day)")
    flagged = [(dev, r) for dev, r in results.items()
               if r["status"] in ("WATCH", "FAULT") and r["projection"]]
    flagged.sort(key=lambda x: x[1]["projection"]["rm_per_day_now"], reverse=True)

    pdf.set_font("Helvetica", "", 9)
    if not flagged:
        pdf.set_text_color(*STATUS_RGB["OK"])
        pdf.cell(0, 7, "No action needed. All devices are within their normal range.",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(20, 20, 20)
    else:
        with pdf.table(col_widths=(10, 24, 18, 22, 20, 32, 34, 60),
                       headings_style=head_style, text_align="LEFT",
                       line_height=5) as table:
            table.row(["#", "Device", "Status", "Waste kWh/day", "RM/day",
                       "Next 30 days RM", "Next 30 days kg CO2", "Likely cause"])
            for rank, (dev, r) in enumerate(flagged, start=1):
                p = r["projection"]
                row = table.row()
                row.cell(str(rank))
                row.cell(names[dev])
                row.cell(r["status"], style=FontFace(emphasis="BOLD",
                                                     color=STATUS_RGB[r["status"]]))
                row.cell("%.1f" % p["kwh_per_day_now"])
                row.cell("RM %.2f" % p["rm_per_day_now"])
                row.cell(range_text(p["rm_low"], p["rm_high"], "RM "))
                row.cell(range_text(p["co2_kg_low"], p["co2_kg_high"]))
                row.cell(r["likely_cause"])

    # 3. Notes
    section_title(pdf, "3. Notes")
    pdf.set_font("Helvetica", "", 9)
    notes = [
        "Likely cause is a hint to check first. Power data alone cannot confirm the cause.",
        "Future waste is the energy, money and CO2 lost if nobody fixes the fault. "
        "It is not a prediction of when the machine will break. Low means waste stays "
        "at today's level. High means a gradual fault keeps growing (capped).",
        "RM uses the TNB Medium Voltage General energy charge of %.2f sen/kWh. The "
        "tariff is assumed and covers the energy charge only, so the real cost is "
        "likely higher." % (TARIFF_RM_PER_KWH * 100),
        "CO2 uses %.3f kg per kWh (Energy Commission, Peninsular grid 2023, "
        "provisional)." % GRID_KG_CO2_PER_KWH,
        "Detection limits are tuned for simulated data. Real buildings would need a "
        "few months of history first.",
    ]
    for n in notes:
        pdf.multi_cell(0, 5, "- " + n, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    return bytes(pdf.output())
