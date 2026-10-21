"""
causes.py
Gives a LIKELY CAUSE hint for a device that the detector flagged.

Power data alone cannot prove which part is broken. So these are hints for the
maintenance team to check first, never a confirmed cause.

The idea is simple. We look at the SHAPE of the waste over the flagged days.
  sudden   waste JUMPED by a lot from one day to the next (3x the limit or more)
  gradual  waste grows a little each day, no big jump
  unclear  only 1 flagged day and no big jump yet, wait one more day
  shutdown (solar only) output close to zero

Why we look at the JUMP and not just the first day.
A fault can start in the middle of a day. Then the first flagged day is only
partly faulty and looks small. The day after shows the full jump.
The day before the first flagged day was below the limit, so we treat it as 0.
"""

SUDDEN_FACTOR = 3.0     # a day-to-day jump >= 3x the limit means "sudden"
SHUTDOWN_PCT = 90.0     # solar producing almost nothing

UNCLEAR_HINT = ("Only 1 day above the limit so far. A likely cause will show "
                "after one more day of data.")

HINTS = {
    "chiller": {
        "gradual": "Power creeping up slowly. Likely cause is a dirty or fouled "
                   "cooling tower or condenser. Check and clean them first.",
        "sudden": "Power jumped up suddenly. Likely cause is a changed setpoint, "
                  "a stuck valve or a chiller running when it should be off.",
        "unclear": UNCLEAR_HINT,
    },
    "ahu": {
        "gradual": "Fan power creeping up slowly. Likely cause is a filter "
                   "getting blocked. Check and replace the filter.",
        "sudden": "Fan power jumped up suddenly and stays high. Likely cause is "
                  "a stuck damper or a fan speed setting changed.",
        "unclear": UNCLEAR_HINT,
    },
    "solar": {
        "gradual": "Output dropping slowly. Likely cause is dust or dirt on the "
                   "panels. Schedule panel cleaning.",
        "sudden": "Output dropped suddenly. Likely cause is part of the array "
                  "offline (a string fault) or new shading.",
        "shutdown": "Output close to zero. Likely cause is an inverter failure "
                    "or a tripped breaker. Check the inverter first.",
        "unclear": UNCLEAR_HINT,
    },
    "pump": {
        "gradual": "Pump power creeping up slowly. Likely cause is a clogged "
                   "strainer or a worn impeller. Check and clean the strainer first.",
        "sudden": "Pump power jumped up suddenly and stays high. Likely cause is "
                  "the speed drive (VSD) stuck at full speed or set to bypass. "
                  "Check the drive settings.",
        "unclear": UNCLEAR_HINT,
    },
}


def likely_cause(device, flagged_pcts, limit_pct):
    """
    device         chiller, ahu, solar or pump
    flagged_pcts   waste % of the flagged full days, oldest first
    limit_pct      the detector limit for this device
    Returns (shape, hint text), or (None, None) if nothing is flagged.
    """
    if not flagged_pcts:
        return None, None

    # Day-to-day change, starting from 0 for the normal day before.
    days = [0.0] + list(flagged_pcts)
    biggest_jump = max(days[i + 1] - days[i] for i in range(len(days) - 1))

    latest = flagged_pcts[-1]
    if device == "solar" and latest >= SHUTDOWN_PCT:
        shape = "shutdown"
    elif biggest_jump >= SUDDEN_FACTOR * limit_pct:
        shape = "sudden"
    elif len(flagged_pcts) >= 2:
        shape = "gradual"
    else:
        shape = "unclear"
    return shape, HINTS[device][shape]
