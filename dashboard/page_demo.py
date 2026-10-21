"""
page_demo.py
LIVE DEMO page. ALL DATA IS SIMULATED.

What it shows
  1  A picture of the example site. TNB grid supply goes into the main
     switchboard, which feeds the chiller, chilled water pump and AHU fan.
     The rooftop solar feeds power back into the switchboard.
     Moving dashes show power flowing. Faster dashes mean more power.
  2  Each power line takes the colour of the AI status of that device.
     green OK, orange WATCH, red FAULT, grey WAITING.
     The colour comes ONLY from the edge detector (edge/detector.py),
     never from the inject button. So the video shows the AI finding the
     fault by itself, a few simulated days after it starts.
  3  A clamp-on power sensor (S) on each line sends its readings over MQTT
     to the edge computer, shown as dotted lines.
  4  A purple "Fault injected" tag shows which SIMULATED faults are on,
     read from the retained MQTT topic sdp/elmina/status/faults.
  5  Demo control (inject or clear a fault) and time control (skip 6 hours).

Opened through dashboard/app.py:
    streamlit run dashboard\\app.py
"""

import json
import os
import random

import paho.mqtt.client as mqtt
import streamlit as st

from common import (FAULT_CHOICES, FAULT_NAMES, NAMES, RATED_KW,
                    REFRESH_SECONDS, SIMULATED_BANNER, SKIP_HOURS)
from detector import DB_PATH, DEVICES, LIMIT_PCT, check_all, load_readings
from send_fault import send_fault, send_skip

BROKER, PORT = "localhost", 1883
TOPIC_STATUS = "sdp/elmina/status/faults"   # same topic as simulator/publisher.py

PICTURE_ORDER = ["chiller", "pump", "ahu", "solar"]   # left to right
# Shorter fault names where the full name does not fit in the picture.
SHORT_FAULT_NAMES = {"vsd_stuck_full": "Drive stuck at full speed"}

# Colours used in the picture (hex codes).
STATUS_HEX = {"OK": "#40c057", "WATCH": "#fd7e14", "FAULT": "#fa5252",
              "WAITING": "#868e96"}
GRID_HEX = "#4dabf7"      # blue, power from the grid
DATA_HEX = "#9fb3c8"      # light grey, sensor data
INJECT_HEX = "#b197fc"    # purple, simulator fault tag
TEXT_HEX = "#e6edf3"
MUTED_HEX = "#8b98a5"
BOX_HEX = "#1b2635"
PANEL_HEX = "#0e1621"


# ---------------------------------------------------------------------------
# 1. Which SIMULATED faults are on? Read from MQTT in the background.
# ---------------------------------------------------------------------------
@st.cache_resource
def fault_listener():
    """
    One small MQTT client for the whole app. It listens to the retained
    fault status that publisher.py sends, and keeps the latest copy in a dict.
    If the broker is down it keeps trying again in the background.
    """
    state = {"connected": False, "faults": {}}

    def on_connect(client, userdata, flags, reason_code, properties):
        state["connected"] = not reason_code.is_failure
        client.subscribe(TOPIC_STATUS)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        state["connected"] = False

    def on_message(client, userdata, msg):
        try:
            state["faults"] = json.loads(msg.payload.decode())
        except ValueError:
            pass   # ignore a bad message

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="sdp-dashboard-%06d" % random.randint(0, 999999))
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(BROKER, PORT)   # does not crash if the broker is down
    client.loop_start()                  # runs in its own thread
    return state


# ---------------------------------------------------------------------------
# 2. The picture, drawn as SVG (a simple vector drawing made of text).
# ---------------------------------------------------------------------------
def flow_seconds(device, kw):
    """Time for the dashes to move along. More power, faster flow."""
    load = min(max(kw / RATED_KW[device], 0.0), 1.0)
    return round(2.2 - 1.6 * load, 2)   # 2.2 s when light, 0.6 s at full power


def power_line(path, colour, kw, seconds):
    """A power line. A faint solid line with moving dashes on top when power flows."""
    base = '<path d="%s" stroke="%s" stroke-width="5" opacity="0.25" fill="none"/>' % (path, colour)
    if kw < 0.5:   # no power, no moving dashes
        return base
    dashes = ('<path d="%s" stroke="%s" stroke-width="5" fill="none" '
              'stroke-dasharray="10 8" class="flow" '
              'style="animation-duration:%ss"/>' % (path, colour, seconds))
    return base + dashes


def device_box(dev, cx, r, kw, injected):
    """Box for one device with its name, power, AI status and simulator tag."""
    status = r["status"]
    colour = STATUS_HEX[status]
    x = cx - 65
    pulse = ' class="pulse"' if status == "FAULT" else ""
    action = "Making" if dev == "solar" else "Using"
    pct = r["latest_waste_pct"]
    if pct is None:
        waste = "Waiting for 1 full day"
    elif pct <= 0:
        waste = "No waste, limit %.0f%%" % LIMIT_PCT[dev]
    else:
        word = "Lost" if dev == "solar" else "Waste"
        waste = "%s %.1f%%, limit %.0f%%" % (word, pct, LIMIT_PCT[dev])

    s = ('<rect x="%d" y="240" width="130" height="100" rx="10" fill="%s" '
         'stroke="%s" stroke-width="3"%s/>' % (x, BOX_HEX, colour, pulse))
    s += '<text x="%d" y="262" class="name">%s</text>' % (cx, NAMES[dev])
    s += '<text x="%d" y="283" class="small">%s %.1f kW</text>' % (cx, action, kw)
    s += ('<rect x="%d" y="292" width="90" height="24" rx="12" fill="%s"/>'
          % (cx - 45, colour))
    s += '<text x="%d" y="309" class="pill">%s</text>' % (cx, status)
    s += '<text x="%d" y="332" class="tiny">%s</text>' % (cx, waste)

    if injected:
        s += ('<rect x="%d" y="350" width="130" height="38" rx="8" fill="#221b33" '
              'stroke="%s" stroke-dasharray="4 3"/>' % (x, INJECT_HEX))
        s += '<text x="%d" y="365" class="tag">Fault injected</text>' % cx
        s += '<text x="%d" y="381" class="tag2">%s</text>' % (
            cx, SHORT_FAULT_NAMES.get(injected, FAULT_NAMES.get(injected, injected)))
    return s


def site_svg(results, kw_now, injected, latest_time):
    """Build the whole picture as one SVG string."""
    css = """
    <style>
      @keyframes flow { to { stroke-dashoffset: -36; } }
      @keyframes data { to { stroke-dashoffset: -18; } }
      @keyframes pulse { 50%% { stroke-opacity: 0.35; } }
      .flow  { animation: flow 1.5s linear infinite; }
      .data  { animation: data 1.2s linear infinite; }
      .pulse { animation: pulse 1.2s ease-in-out infinite; }
      text   { font-family: sans-serif; fill: %(text)s; text-anchor: middle; }
      .name  { font-size: 13px; font-weight: bold; }
      .small { font-size: 12px; }
      .tiny  { font-size: 10px; fill: %(muted)s; }
      .muted { font-size: 11px; fill: %(muted)s; }
      .pill  { font-size: 12px; font-weight: bold; fill: #ffffff; }
      .tag   { font-size: 10px; font-weight: bold; fill: %(inject)s; }
      .tag2  { font-size: 9px; fill: %(inject)s; }
      .left  { text-anchor: start; }
      .end   { text-anchor: end; }
    </style>""" % {"text": TEXT_HEX, "muted": MUTED_HEX, "inject": INJECT_HEX}

    s = ('<svg viewBox="0 0 1000 560" width="100%%" '
         'xmlns="http://www.w3.org/2000/svg">%s' % css)
    s += '<rect x="0" y="0" width="1000" height="560" rx="14" fill="%s"/>' % PANEL_HEX

    # Grid supply, main switchboard and the busbar.
    s += ('<rect x="30" y="45" width="140" height="60" rx="8" fill="%s" '
          'stroke="%s" stroke-width="2"/>' % (BOX_HEX, GRID_HEX))
    s += '<text x="100" y="71" class="name">TNB grid</text>'
    s += '<text x="100" y="91" class="muted">power supply</text>'
    s += power_line("M170,75 H230", GRID_HEX, 1.0, 1.2)
    s += ('<rect x="230" y="45" width="130" height="60" rx="8" fill="%s" '
          'stroke="%s" stroke-width="2"/>' % (BOX_HEX, MUTED_HEX))
    s += '<text x="295" y="71" class="name">Main</text>'
    s += '<text x="295" y="91" class="name">switchboard</text>'
    s += '<path d="M360,75 H940" stroke="#5b6b7d" stroke-width="8" stroke-linecap="round"/>'

    # One power line, sensor, data line and box for each device.
    for i, dev in enumerate(PICTURE_ORDER):
        cx = 450 + 160 * i
        r = results[dev]
        kw = kw_now.get(dev, 0.0)
        colour = STATUS_HEX[r["status"]]
        # Loads take power down from the busbar. Solar pushes power up into it.
        path = "M%d,240 V75" % cx if dev == "solar" else "M%d,75 V240" % cx
        s += power_line(path, colour, kw, flow_seconds(dev, kw))

        # Clamp-on power sensor (S) and its data line to the edge computer.
        s += ('<path d="M%d,160 H%d V430" stroke="%s" stroke-width="2" fill="none" '
              'stroke-dasharray="3 6" class="data"/>' % (cx - 13, cx - 80, DATA_HEX))
        s += ('<circle cx="%d" cy="160" r="13" fill="%s" stroke="%s" stroke-width="2"/>'
              % (cx, BOX_HEX, DATA_HEX))
        s += '<text x="%d" y="165" class="small">S</text>' % cx

        s += device_box(dev, cx, r, kw, injected.get(dev))

    # Data bus to the edge computer, then to the dashboard.
    s += ('<path d="M850,430 H330" stroke="%s" stroke-width="2" fill="none" '
          'stroke-dasharray="3 6" class="data"/>' % DATA_HEX)
    s += ('<rect x="150" y="400" width="180" height="60" rx="8" fill="%s" '
          'stroke="%s" stroke-width="2"/>' % (BOX_HEX, GRID_HEX))
    s += '<text x="240" y="425" class="name">Edge computer</text>'
    s += '<text x="240" y="445" class="muted">MQTT broker + AI models</text>'
    s += ('<path d="M240,460 V490" stroke="%s" stroke-width="2" fill="none" '
          'stroke-dasharray="3 6" class="data"/>' % DATA_HEX)
    s += ('<rect x="150" y="490" width="180" height="50" rx="8" fill="%s" '
          'stroke="%s" stroke-width="2"/>' % (BOX_HEX, MUTED_HEX))
    s += '<text x="240" y="512" class="name">Dashboard</text>'
    s += '<text x="240" y="530" class="muted">maintenance team</text>'

    # Legend and simulated label on the left.
    s += '<rect x="30" y="130" width="120" height="26" rx="6" fill="#ffd43b"/>'
    s += ('<text x="90" y="148" style="font-size:13px;font-weight:bold;fill:#1b1b1b">'
          'SIMULATED</text>')
    s += '<text x="30" y="182" class="muted left">Simulated time</text>'
    s += '<text x="30" y="200" class="small left">%s</text>' % (
        latest_time.strftime("%a %d %b %Y, %H:%M"))
    s += '<text x="30" y="232" class="muted left">Line colour is the AI status</text>'
    legend = [("OK", "OK"), ("WATCH", "WATCH, 1 day above limit"),
              ("FAULT", "FAULT, fix this"), ("WAITING", "WAITING, no full day yet")]
    for j, (status, label) in enumerate(legend):
        y = 252 + 20 * j
        s += ('<path d="M30,%d H60" stroke="%s" stroke-width="5"/>'
              % (y - 4, STATUS_HEX[status]))
        s += '<text x="70" y="%d" class="small left">%s</text>' % (y, label)
    s += ('<path d="M30,348 H60" stroke="%s" stroke-width="2" stroke-dasharray="3 6"/>'
          % DATA_HEX)
    s += '<text x="70" y="352" class="small left">Sensor data (MQTT)</text>'
    s += '<text x="30" y="376" class="muted left">S is a clamp-on power sensor</text>'

    s += ('<text x="985" y="545" class="muted end">The laptop plays the sensors, '
          'the network and the edge computer.</text>')
    return s + "</svg>"


# ---------------------------------------------------------------------------
# 3. The page.
# ---------------------------------------------------------------------------
st.title("Live demo")
st.caption("Example site. Elmina Lakeside Mall. Watch power and data flow, "
           "inject a simulated fault, and see the AI find it.")
st.warning(SIMULATED_BANNER)

listener = fault_listener()


@st.fragment(run_every=REFRESH_SECONDS)
def live_picture():
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

    results = check_all(readings=readings)
    latest_time = readings["timestamp"].max()
    kw_now = {dev: float(readings.loc[readings["device"] == dev, "kw"].iloc[-1])
              for dev in DEVICES if (readings["device"] == dev).any()}
    faults = listener["faults"] or {}
    injected = {dev: f["type"] for dev, f in faults.items() if f}

    # st.image shows the SVG drawing. Its moving parts are CSS animations
    # inside the SVG, so no JavaScript is needed.
    st.image(site_svg(results, kw_now, injected, latest_time), width="stretch")

    # One plain line per injected fault, so the story is easy to follow.
    for dev, f in faults.items():
        if f and dev in NAMES:
            start = f["start"].replace("T", " ")[:16]
            st.markdown("**%s.** Simulated fault *%s* injected at %s. "
                        "AI status now **%s**." % (
                            NAMES[dev], FAULT_NAMES.get(f["type"], f["type"]),
                            start, results[dev]["status"]))
    if not listener["connected"]:
        st.caption("Cannot reach the MQTT broker, so injected faults are not shown.")


def controls():
    """Demo control and time control. They talk to the SIMULATOR over MQTT."""
    col1, col2 = st.columns([2, 1])

    with col1.container(border=True):
        st.subheader("Demo control")
        st.caption("For the demo only. This tells the SIMULATOR to start or stop "
                   "a fault. In a real building, faults happen on their own.")
        c1, c2 = st.columns(2)
        dev = c1.selectbox("Device", DEVICES, format_func=lambda d: NAMES[d])
        label = c2.selectbox("Fault", list(FAULT_CHOICES[dev]))

        b1, b2 = st.columns(2)
        if b1.button("Inject fault", type="primary", width="stretch"):
            try:
                send_fault(dev, FAULT_CHOICES[dev][label], BROKER, PORT)
                st.session_state["last_action"] = "Injected %s on %s" % (label, NAMES[dev])
            except OSError:
                st.session_state["last_action"] = "Could not reach the MQTT broker"
        if b2.button("Clear fault", width="stretch"):
            try:
                send_fault(dev, "none", BROKER, PORT)
                st.session_state["last_action"] = "Cleared fault on %s" % NAMES[dev]
            except OSError:
                st.session_state["last_action"] = "Could not reach the MQTT broker"
        if "last_action" in st.session_state:
            st.info(st.session_state["last_action"])

    with col2.container(border=True):
        st.subheader("Time control")
        st.caption("Jumps SIMULATED time ahead. 4 clicks = 1 simulated day. "
                   "All readings in between are still sent and saved.")
        if st.button("Skip %d hours" % SKIP_HOURS, width="stretch"):
            try:
                send_skip(SKIP_HOURS, BROKER, PORT)
                st.session_state["last_skip"] = "Skipped %d simulated hours" % SKIP_HOURS
            except OSError:
                st.session_state["last_skip"] = "Could not reach the MQTT broker"
        if "last_skip" in st.session_state:
            st.info(st.session_state["last_skip"])

    st.caption("How to demo. 1. Inject a fault. 2. Click Skip a few times. "
               "3. Watch the line turn orange (WATCH), then red (FAULT). The AI "
               "decides the colour, not the button. Detection needs full simulated "
               "days, so it takes 1 to 4 simulated days. 4. Open the Dashboard page "
               "for the likely cause, money and carbon.")


live_picture()
controls()
