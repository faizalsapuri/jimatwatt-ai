# Energy Fault Monitoring System

SDP University Hackathon 2026, "Township of Tomorrow" (Planet focus).

One edge AI system that watches different equipment in one building, spots faulty or worn out devices early, and shows how much energy, money and carbon each fault will waste if nobody fixes it.

> **Note on data.** All data in this prototype is **simulated** on one laptop. Elmina Lakeside Mall is used only as an example site. No real building data is used. Device sizes are example values.

## The problem

Faulty or worn out equipment in a building silently wastes electricity, and nobody notices until the bill rises or something breaks.

## What the system does

1. **Monitor.** Reads the power of 4 devices every 15 minutes. A chiller, an air handling unit (AHU) fan, a chilled water pump and a rooftop solar system. The same engine handles every device type, so adding a new device needs a simulator (or a real sensor) and one trained model, with no new AI code.
2. **Detect.** Compares each day's actual energy with what a trained model expected. Flags a device only when the gap lasts, not on a single odd reading.
3. **Predict future waste.** Estimates how much energy (kWh), money (RM) and carbon (kg CO2) the fault will waste over the next 30 days if it is not fixed. It does **not** predict when a machine will break.
4. **Report.** Shows a maintenance list ranked by RM wasted per day, a carbon and savings summary for the whole building, and a daily report as PDF, TXT and CSV.

Each flagged device also gets a **likely cause** hint. Power data alone cannot prove the exact fault, so the hint is never shown as a confirmed cause.

## How it works

```
Simulated IoT sensors  ->  MQTT broker  ->  Edge AI     ->  Database  ->  Dashboard and report
(Python)                   (Mosquitto)      (XGBoost)       (SQLite)      (Streamlit)
```

| Part | Plays the role of | Tool |
|---|---|---|
| `simulator/publisher.py` | Clamp-on power sensors on the 4 devices | Python, paho-mqtt |
| Mosquitto | The network carrying sensor data | Mosquitto 2.1.2 |
| `edge/subscriber.py`, `edge/detector.py` | The edge computer in the plant room | Python, XGBoost |
| `data/readings.db` | Storage on the edge computer | SQLite |
| `dashboard/app.py` | What the maintenance team sees | Streamlit |

The AI runs on the edge, so it can work without internet and keeps building data on site. For this demo, one laptop plays the sensors, the network and the edge computer.

## Folders

| Folder | What is inside |
|---|---|
| `simulator/` | Simulated sensors, weather, fault injection, 60 day history generator, MQTT publisher |
| `edge/` | MQTT subscriber, model features, training, fault detection, likely cause rules, waste projection, carbon summary |
| `dashboard/` | Streamlit dashboard and PDF report |
| `models/` | Trained XGBoost models (one per device) and accuracy scores |
| `data/` | SQLite database and generated CSV files (not stored in Git, created when you run the code) |

## Setup (Windows)

1. Install Python 3.13, Git and Mosquitto 2.1.2.
2. Make sure Mosquitto is running on `localhost` port `1883`. The Windows installer sets it up as a service that starts automatically.
3. Clone the repo, create the virtual environment and install the libraries.

```powershell
git clone https://github.com/faizalsapuri/sdp-energy-fault-monitor.git
cd sdp-energy-fault-monitor
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The trained models are already in `models/`, so you do not need to train before running the demo.

## Run the demo

Open **3 PowerShell windows** in the project folder. Activate the virtual environment in each one with `.\venv\Scripts\Activate.ps1`. Run every script from the project folder.

**Window 1. Edge subscriber** (saves readings to SQLite). `--reset` clears old readings.

```powershell
python edge\subscriber.py --reset
```

**Window 2. Simulated sensors** (publish readings through MQTT).

```powershell
python simulator\publisher.py
```

Simulated time starts on 23 Oct 2026 and runs fast. One simulated day takes about 48 seconds. Use `--interval 0.2` to make it faster.

**Window 3. Dashboard.**

```powershell
streamlit run dashboard\app.py
```

The dashboard opens in the browser and refreshes every 3 seconds.

### Demo steps

1. Wait for the first full simulated day, or click **Skip 6 hours** in the sidebar 4 times. All 4 devices should show **OK**.
2. In the sidebar under **Demo control**, choose a device and a fault, then click **Inject fault**.
3. Click **Skip 6 hours** a few more times. The device moves to **WATCH**, then **FAULT**, with a likely cause hint and its future waste over 30 days.
4. Check the maintenance list and the carbon and savings summary, then download the daily report.
5. Click **Clear fault** to switch the fault off.

You can also inject faults from the command line while the publisher is running.

```powershell
python simulator\send_fault.py chiller dirty_cooling_tower
python simulator\send_fault.py ahu stuck_damper
python simulator\send_fault.py solar dust
python simulator\send_fault.py solar inverter_failure
python simulator\send_fault.py pump clogged_strainer
python simulator\send_fault.py pump vsd_stuck_full
python simulator\send_fault.py chiller none
```

To print the detector result in the terminal, run `python edge\detector.py`.

### Simulated faults

| Device | Example size | Fault | What it looks like |
|---|---|---|---|
| Chiller | 500 RT, about 325 kW | Dirty cooling tower | Power creeps up 1.5% per day, up to 25% extra |
| AHU fan | 30 kW | Stuck damper | Fan power jumps up 35% and stays high |
| Rooftop solar | 200 kWp | Dust build-up | Output drops 1% per day, up to 30% loss |
| Rooftop solar | 200 kWp | Inverter failure | Output falls to zero |
| Chilled water pump | 37 kW with speed drive | Clogged strainer | Power creeps up 2% per day, up to 25% extra |
| Chilled water pump | 37 kW with speed drive | Speed drive stuck at full speed | Power jumps to 95% of the motor rating |

## Retrain the models (optional)

```powershell
python simulator\generate_history.py
python edge\train.py
```

This creates 60 days of healthy simulated history in `data/history.csv`, trains one XGBoost model per device, tests it on the last 12 days, then retrains on all 60 days. It saves the models and `models/metrics.json`.

## How detection works

- Each device has one XGBoost model that predicts its normal power from hour, day of week, weekend, mall opening hours, temperature, humidity and cloud level.
- Detection uses **full days**, not single 15 minute readings, to avoid false alarms.
- A device is **WATCH** after 1 full day above its limit.
- A device is **FAULT** after 2 full days in a row above its limit, or 1 full day with 50% or more waste.
- Limits are chiller 2%, AHU 5%, solar 3% and pump 3%. They are tuned for the simulated data.
- The likely cause hint comes from the shape of the waste. Sudden, gradual or solar shutdown.

## How future waste is estimated

- Future waste is shown as a range over 30 days.
- **Low** means waste stays at today's level.
- **High** means a gradual fault keeps getting worse at its current trend, capped at 30% extra use for the chiller, AHU and pump (a demo assumption) and 100% loss for solar.
- RM uses the TNB Medium Voltage General energy charge of 29.83 sen per kWh (from 1 July 2025). We assume the mall is on this tariff. It covers the energy charge only, so the real RM loss is likely higher.
- Carbon uses 0.760 kg CO2 per kWh, the Peninsular Malaysia grid emission factor for 2023 (Energy Commission, provisional).

## Carbon and savings summary

The dashboard adds up all flagged devices into one building total, in kWh, RM and kg CO2.

- **Wasted so far.** Waste on the flagged full days already seen.
- **Waste now.** Per day, at the latest full day's level.
- **Avoidable in the next 30 days.** The future waste range if nobody fixes the faults. This is what fixing them now could avoid.

For solar, waste is energy the panels failed to make, which the building then buys from the grid. The same summary is in the PDF and TXT reports, so the sustainability team can use it for carbon reporting. Run `python edge\carbon.py` to print it in the terminal.

## Model accuracy (simulated data)

Scored on the last 12 days of simulated data, which the model did not see in training.

| Device | Hourly CV(RMSE) | Daily CV(RMSE) | NMBE |
|---|---|---|---|
| Chiller | 2.1% | 0.4% | within 0.2% |
| AHU fan | 1.6% | 0.4% | within 0.2% |
| Rooftop solar | 3.6% | 1.7% | within 0.2% |
| Chilled water pump | 1.5% | 0.2% | within 0.2% |

All pass the ASHRAE Guideline 14 limits. **These scores are very high only because the data is simulated from simple formulas.** They are not real world accuracy. Real buildings will be noisier.

## Honest notes and limits

- All data is simulated. No real sensors or real building data are used.
- Elmina Lakeside Mall is an example pilot site only.
- The system flags a **likely cause**, not a confirmed cause.
- It predicts future **waste**, not the date a machine will break down.
- Detection limits and the 30% cap are tuned for simulated data and would need tuning on a real site.
- The 30 day high estimate for a gradual fault is too big in the first days, because the first flagged day is often only partly faulty. It improves as more days come in.
- The subscriber uses SQLite WAL mode for speed. A sudden power loss could lose the last few seconds of readings. This is fine for a demo.

## Next steps

- Test with public fault datasets from LBNL (chiller plant and AHU).
- Add more device types such as lighting, lifts and EV chargers using the same engine.
- Pilot with real clamp-on power sensors and a small edge computer at one SDP building.

## Tech stack

Python 3.13, Mosquitto 2.1.2, paho-mqtt 2.1.0, XGBoost 3.4.1, pandas 3.0.6, scikit-learn 1.9.1, SQLite, Streamlit 1.66.0, fpdf2 2.8.9. Full list in `requirements.txt`.
