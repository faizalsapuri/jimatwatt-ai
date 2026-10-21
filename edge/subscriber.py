"""
subscriber.py
Part of the EDGE COMPUTER. It listens to the 3 simulated sensors on the MQTT
broker and saves every reading into a local SQLite database.
ALL READINGS ARE SIMULATED.

Database file   data/readings.db
Table           readings
  device     chiller, ahu or solar
  timestamp  start of the 15 minute reading, for example 2026-10-23T09:15:00
  kw         power in kW (for solar this is power produced)
  temp_c, humidity, cloud   simulated weather at that time
  simulated  1 means simulated data

The publisher always restarts at 23 Oct 2026 00:00. So the same device and
timestamp can arrive again. We keep only the newest copy (INSERT OR REPLACE).

Run from the project folder:
    python edge\\subscriber.py            keep old readings
    python edge\\subscriber.py --reset    clear old readings first (use before a demo)
"""

import argparse
import json
import os
import sqlite3

import paho.mqtt.client as mqtt

DB_PATH = os.path.join("data", "readings.db")
TOPIC_READINGS = "sdp/elmina/+"   # + matches chiller, ahu and solar only
DEVICES = ("chiller", "ahu", "solar")

saved_count = 0


def open_db(reset):
    """Open the database and make sure the readings table exists."""
    os.makedirs("data", exist_ok=True)
    # check_same_thread=False because MQTT calls us from its own thread.
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Faster saving. WAL mode lets the dashboard read while we write, and
    # synchronous=NORMAL skips the slow disk flush after every single reading.
    # This matters during a time skip, when many readings arrive at once.
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    if reset:
        db.execute("DROP TABLE IF EXISTS readings")
    db.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            device    TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            kw        REAL,
            temp_c    REAL,
            humidity  REAL,
            cloud     REAL,
            simulated INTEGER,
            PRIMARY KEY (device, timestamp)
        )
    """)
    db.commit()
    return db


def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected to MQTT broker:", reason_code)
    client.subscribe(TOPIC_READINGS)


def on_message(client, userdata, msg):
    """Save one reading into SQLite."""
    global saved_count
    db = userdata["db"]

    try:
        r = json.loads(msg.payload.decode())
    except ValueError:
        print("Ignored bad message on", msg.topic)
        return

    if r.get("device") not in DEVICES:
        return  # not a sensor reading

    db.execute(
        "INSERT OR REPLACE INTO readings VALUES (?, ?, ?, ?, ?, ?, ?)",
        (r["device"], r["timestamp"], r["kw"], r["temp_c"],
         r["humidity"], r["cloud"], int(r.get("simulated", True))),
    )
    db.commit()
    saved_count += 1

    # Print once per simulated hour (3 devices per tick) so the screen stays calm.
    if r["device"] == "solar" and r["timestamp"].endswith(":00:00"):
        print("Saved up to", r["timestamp"], "| total rows saved this run:", saved_count)


def main():
    parser = argparse.ArgumentParser(description="Edge subscriber, MQTT to SQLite")
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--reset", action="store_true",
                        help="delete old readings before starting")
    args = parser.parse_args()

    db = open_db(args.reset)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="sdp-edge-subscriber",
                         userdata={"db": db})
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port)

    print("Edge subscriber running. Saving SIMULATED readings to", DB_PATH)
    print("Press Ctrl+C to stop.")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        client.disconnect()
        db.close()


if __name__ == "__main__":
    main()
