"""
causes.py
Gives a LIKELY CAUSE hint for a device that the detector flagged.

Power data alone cannot prove which part is broken. So these are hints for the
maintenance team to check first, never a confirmed cause.

The idea is simple. We look at the SHAPE of the waste over the flagged days.
  sudden   the first flagged day is already far above the limit (3x or more)
  gradual  the waste starts small and grows day by day
Each device has its own short list of likely causes for each shape.
"""

SUDDEN_FACTOR = 3.0     # first flagged day >= 3x the limit means "sudden"
SHUTDOWN_PCT = 90.0     # solar producing almost nothing

HINTS = {
    "chiller": {
        "gradual": "Power creeping up slowly. Likely cause is a dirty or fouled "
                   "cooling tower or condenser. Check and clean them first.",
        "sudden": "Power jumped up suddenly. Likely cause is a changed setpoint, "
                  "a stuck valve or a chiller running when it should be off.",
    },
    "ahu": {
        "gradual": "Fan power creeping up slowly. Likely cause is a filter "
                   "getting blocked. Check and replace the filter.",
        "sudden": "Fan power jumped up suddenly and stays high. Likely cause is "
                  "a stuck damper or a fan speed setting changed.",
    },
    "solar": {
        "gradual": "Output dropping slowly. Likely cause is dust or dirt on the "
                   "panels. Schedule panel cleaning.",
        "sudden": "Output dropped suddenly. Likely cause is part of the array "
                  "offline (a string fault) or new shading.",
        "shutdown": "Output close to zero. Likely cause is an inverter failure "
                    "or a tripped breaker. Check the inverter first.",
    },
}


def likely_cause(device, flagged_pcts, limit_pct):
    """
    device         chiller, ahu or solar
    flagged_pcts   waste % of the flagged full days, oldest first
    limit_pct      the detector limit for this device
    Returns (shape, hint text), or (None, None) if nothing is flagged.
    """
    if not flagged_pcts:
        return None, None

    latest = flagged_pcts[-1]
    if device == "solar" and latest >= SHUTDOWN_PCT:
        shape = "shutdown"
    elif flagged_pcts[0] >= SUDDEN_FACTOR * limit_pct:
        shape = "sudden"
    else:
        shape = "gradual"
    return shape, HINTS[device][shape]
