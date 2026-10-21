# Energy Fault Monitoring System

SDP University Hackathon 2026, "Township of Tomorrow" (Planet focus).

One system that watches different equipment in one building, spots faulty or worn out devices early, and shows how much energy, money and carbon they will waste if not fixed.

> **Note on data.** All data in this prototype is **simulated** on one laptop. Elmina Lakeside Mall is used only as an example site. No real building data is used.

## How it works

Fake IoT sensors (Python) → MQTT broker (Mosquitto) → Edge AI (XGBoost) → Database (SQLite) → Dashboard (Streamlit)

## Folders

| Folder | What is inside |
|---|---|
| `simulator/` | Fake power sensors for chiller, AHU and rooftop solar |
| `edge/` | MQTT subscriber, baseline models, fault detection, waste projection |
| `dashboard/` | Streamlit dashboard and daily report |
| `models/` | Trained XGBoost models |
| `data/` | SQLite database and generated data (not stored in Git) |

## Setup (Windows)

1. Install Python 3.13, Git and Mosquitto 2.1.2.
2. Create the virtual environment and install libraries.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

More run steps will be added as the build progresses.
