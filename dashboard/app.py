"""
app.py
Starts the web app and links its two pages. ALL DATA IS SIMULATED.

  Live demo   page_demo.py       Picture of the site with power and data flow,
                                 demo control (inject or clear a SIMULATED
                                 fault) and time control (skip 1 day or 12 hours)
  Dashboard   page_dashboard.py  What the maintenance team sees. Device status,
                                 maintenance list, carbon summary, reports

Run from the project folder (publisher and subscriber must be running):
    streamlit run dashboard\\app.py
"""

import streamlit as st

import common  # noqa: F401  (lets the pages import code from edge/ and simulator/)

st.set_page_config(page_title="JimatWatt AI", layout="wide")

pages = [
    st.Page("page_demo.py", title="Live demo", icon=":material/bolt:",
            default=True),   # the default page opens at the main address
    st.Page("page_dashboard.py", title="Dashboard", icon=":material/monitoring:",
            url_path="dashboard"),
]
st.navigation(pages, position="top").run()
