"""
send_fault.py
Small helper to switch a SIMULATED fault on or off while publisher.py is running.
The dashboard "Inject fault" button will use the same send_fault() function.

Examples, from the project folder:
    python simulator\\send_fault.py chiller dirty_cooling_tower
    python simulator\\send_fault.py ahu stuck_damper
    python simulator\\send_fault.py solar dust
    python simulator\\send_fault.py solar inverter_failure
    python simulator\\send_fault.py pump clogged_strainer
    python simulator\\send_fault.py pump vsd_stuck_full
    python simulator\\send_fault.py chiller none          (switch off)
"""

import json
import sys

import paho.mqtt.publish as publish

TOPIC_CONTROL = "sdp/elmina/control/fault"
TOPIC_SKIP = "sdp/elmina/control/skip"


def send_fault(device, fault_type, broker="localhost", port=1883):
    """Publish one fault command to the simulator."""
    payload = json.dumps({"device": device, "type": fault_type})
    publish.single(TOPIC_CONTROL, payload, hostname=broker, port=port)


def send_skip(hours, broker="localhost", port=1883):
    """Ask the simulator to jump ahead in SIMULATED time (used by the dashboard)."""
    payload = json.dumps({"hours": hours})
    publish.single(TOPIC_SKIP, payload, hostname=broker, port=port)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    send_fault(sys.argv[1], sys.argv[2])
    print("Sent:", sys.argv[1], sys.argv[2])
