"""
publisher.py
Plays the role of the 4 clamp-on IoT power sensors. ALL READINGS ARE SIMULATED.

Every tick it creates one 15 minute reading per device and publishes it to the
MQTT broker (Mosquitto). Simulated time starts where the 60 day history ends,
23 Oct 2026 00:00, and moves 15 minutes per tick. By default 1 tick is 0.5 seconds,
so 1 simulated day passes in about 48 seconds. This makes the demo fast.

MQTT topics
  sdp/elmina/chiller        reading from the chiller sensor
  sdp/elmina/ahu            reading from the AHU fan sensor
  sdp/elmina/solar          reading from the rooftop solar meter
  sdp/elmina/pump           reading from the chilled water pump sensor
  sdp/elmina/control/fault  (we listen) switch a fault on or off
  sdp/elmina/control/skip   (we listen) jump simulated time ahead, for the demo
  sdp/elmina/status/faults  (we publish, retained) faults that are currently on

Reading payload (JSON)
  {"device": "chiller", "timestamp": "2026-10-23T09:15:00", "kw": 182.4,
   "temp_c": 29.1, "humidity": 82.3, "cloud": 0.31, "simulated": true}

Fault control payload (JSON)
  {"device": "chiller", "type": "dirty_cooling_tower"}   switch on, starts now
  {"device": "chiller", "type": "none"}                  switch off

Time skip payload (JSON)
  {"hours": 6}   send the next 6 hours of readings at once, with no waiting.
                 Every reading is still published and saved, nothing is lost.

Run from the project folder:
    python simulator\\publisher.py
    python simulator\\publisher.py --interval 0.2     (faster)
"""

import argparse
import json
import time

import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt

from ahu import ahu_power_kw
from chiller import chiller_power_kw
from environment import make_weather
from faults import FAULT_TYPES, apply_fault
from pump import pump_power_kw
from solar import solar_power_kw

LIVE_START = pd.Timestamp("2026-10-23 00:00")  # right after the 60 day history
LIVE_DAYS = 365                                # plenty of simulated days for a demo
SEED = 2026                                    # different seed from the history
PUMP_SEED = 2126                               # own seed for the pump (4th device)

TOPIC_BASE = "sdp/elmina"
TOPIC_CONTROL = TOPIC_BASE + "/control/fault"
TOPIC_SKIP = TOPIC_BASE + "/control/skip"
TOPIC_STATUS = TOPIC_BASE + "/status/faults"

SKIP_PAUSE = 0.001  # tiny pause between skipped readings so MQTT is not flooded

# Faults that are currently switched on, one per device at most.
active_faults = {"chiller": None, "ahu": None, "solar": None, "pump": None}
current_ts = LIVE_START
skip_ticks = 0      # readings still to send fast because of a time skip


def publish_fault_status(client):
    """Tell everyone which faults are on. Retained, so a new dashboard sees it straight away."""
    status = {
        dev: (None if f is None else {"type": f["type"], "start": f["start"].isoformat()})
        for dev, f in active_faults.items()
    }
    client.publish(TOPIC_STATUS, json.dumps(status), retain=True)


def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected to MQTT broker:", reason_code)
    client.subscribe(TOPIC_CONTROL)
    client.subscribe(TOPIC_SKIP)
    publish_fault_status(client)


def handle_skip(msg):
    """Add a time skip. 1 hour = 4 readings of 15 minutes."""
    global skip_ticks
    try:
        hours = float(json.loads(msg.payload.decode())["hours"])
    except (ValueError, KeyError, TypeError):
        print("Ignored bad skip message:", msg.payload)
        return
    if 0 < hours <= 72:
        skip_ticks += int(hours * 4)
        print(">>> Skipping ahead %g simulated hours from %s" % (hours, current_ts))


def on_message(client, userdata, msg):
    """Handle a fault on or off command, or a time skip."""
    if msg.topic == TOPIC_SKIP:
        handle_skip(msg)
        return

    try:
        cmd = json.loads(msg.payload.decode())
        device, ftype = cmd["device"], cmd["type"]
    except (ValueError, KeyError):
        print("Ignored bad control message:", msg.payload)
        return

    if device not in active_faults:
        print("Ignored unknown device:", device)
        return

    if ftype in (None, "none"):
        active_faults[device] = None
        print(">>> Fault cleared on", device, "at", current_ts)
    elif ftype in FAULT_TYPES[device]:
        active_faults[device] = {"type": ftype, "start": current_ts}
        print(">>> Fault", ftype, "switched ON for", device, "at", current_ts)
    else:
        print("Ignored unknown fault", ftype, "for", device)
        return

    publish_fault_status(client)


def main():
    global current_ts, skip_ticks

    parser = argparse.ArgumentParser(description="Simulated IoT power sensors")
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--interval", type=float, default=0.5,
                        help="real seconds per 15 minute reading")
    args = parser.parse_args()

    rng = np.random.default_rng(SEED)
    pump_rng = np.random.default_rng(PUMP_SEED)  # keeps the first 3 devices unchanged
    weather = make_weather(start=LIVE_START, days=LIVE_DAYS, rng=rng)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sdp-sensor-simulator")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port)
    client.loop_start()  # handles MQTT in the background

    print("SIMULATED sensors running. Press Ctrl+C to stop.")
    try:
        for ts, row in weather.iterrows():
            current_ts = ts
            healthy = {
                "chiller": chiller_power_kw(ts, row["temp_c"], rng),
                "ahu": ahu_power_kw(ts, row["temp_c"], rng),
                "solar": solar_power_kw(ts, row["temp_c"], row["cloud"], rng),
                "pump": pump_power_kw(ts, row["temp_c"], pump_rng),
            }
            sent = {}
            for device, kw in healthy.items():
                kw = apply_fault(device, kw, ts, active_faults[device])
                sent[device] = kw
                payload = {
                    "device": device,
                    "timestamp": ts.isoformat(),
                    "kw": kw,
                    "temp_c": float(row["temp_c"]),
                    "humidity": float(row["humidity"]),
                    "cloud": float(row["cloud"]),
                    "simulated": True,
                }
                client.publish(TOPIC_BASE + "/" + device, json.dumps(payload))

            # Print once per simulated hour so the screen is not flooded.
            if ts.minute == 0:
                print(ts, " chiller %.1f kW  ahu %.1f kW  solar %.1f kW  pump %.1f kW" % (
                    sent["chiller"], sent["ahu"], sent["solar"], sent["pump"]))

            # Normal speed waits args.interval. During a time skip we hardly wait.
            if skip_ticks > 0:
                skip_ticks -= 1
                time.sleep(SKIP_PAUSE)
            else:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
