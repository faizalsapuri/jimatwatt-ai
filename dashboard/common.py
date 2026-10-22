"""
common.py
Shared settings for the two dashboard pages. ALL DATA IS SIMULATED.

  page_demo.py       Live demo. Picture of the site, demo control, time control
  page_dashboard.py  Dashboard. Device status, maintenance list, carbon, reports

Importing this file also lets the pages import code from edge/ and simulator/.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for folder in ("edge", "simulator"):
    path = os.path.abspath(os.path.join(HERE, "..", folder))
    if path not in sys.path:
        sys.path.insert(0, path)

REFRESH_SECONDS = 3   # how often the live part of each page updates
SKIP_DAY_HOURS = 24   # "Skip 1 day" button, the main button for the demo
SKIP_HALF_HOURS = 12  # "Skip 12 hours" button, e.g. to jump from night to day

NAMES = {"chiller": "Chiller", "ahu": "AHU fan", "solar": "Rooftop solar",
         "pump": "Chilled water pump"}
SIZES = {"chiller": "500 RT, about 325 kW (example size)",
         "ahu": "30 kW fan (example size)",
         "solar": "200 kWp (example size)",
         "pump": "37 kW with speed drive (example size)"}
# Rated power in kW (example sizes). Used to set how fast the power flows
# in the Live demo picture.
RATED_KW = {"chiller": 325.0, "ahu": 30.0, "solar": 200.0, "pump": 37.0}

# Streamlit colour tags for each status.
COLOURS = {"OK": "green", "WATCH": "orange", "FAULT": "red", "WAITING": "gray"}

# Faults the simulator knows (same names as simulator/faults.py).
FAULT_CHOICES = {
    "chiller": {"Dirty cooling tower (gradual)": "dirty_cooling_tower"},
    "ahu": {"Stuck damper (sudden)": "stuck_damper"},
    "solar": {"Dust on panels (gradual)": "dust",
              "Inverter failure (shutdown)": "inverter_failure"},
    "pump": {"Clogged strainer (gradual)": "clogged_strainer",
             "Speed drive stuck at full speed (sudden)": "vsd_stuck_full"},
}
# Short names for the faults, for the picture.
FAULT_NAMES = {code: label.split(" (")[0]
               for faults in FAULT_CHOICES.values()
               for label, code in faults.items()}

SIMULATED_BANNER = ("SIMULATED DATA. All readings come from a software simulator "
                    "on this laptop, not from real sensors. Device sizes are "
                    "example values.")
