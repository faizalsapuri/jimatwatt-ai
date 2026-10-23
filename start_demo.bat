@echo off
REM ==========================================================================
REM start_demo.bat
REM One click start for the demo. ALL DATA IS SIMULATED.
REM Opens 3 windows, in this order
REM   1. Edge subscriber   saves readings to SQLite (--reset clears old data)
REM   2. Simulated sensors publish readings through MQTT
REM   3. Dashboard         Streamlit app, opens in the browser
REM Close the 3 windows to stop the demo.
REM ==========================================================================

REM Always run from the project folder, the folder this file is in.
cd /d "%~dp0"

REM Check the virtual environment exists.
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found. Follow the Setup steps in README.md first.
    pause
    exit /b 1
)

REM Check the Mosquitto MQTT broker service is running. Try to start it if not.
sc query mosquitto | find "RUNNING" >nul
if errorlevel 1 (
    echo Mosquitto is not running. Trying to start it...
    net start mosquitto >nul 2>&1
    sc query mosquitto | find "RUNNING" >nul
    if errorlevel 1 (
        echo [ERROR] Could not start Mosquitto. Start it as administrator with
        echo         net start mosquitto
        pause
        exit /b 1
    )
)
echo Mosquitto broker is running on localhost port 1883.

echo Starting the edge subscriber (old readings are cleared)...
start "1. Edge subscriber" cmd /k "call venv\Scripts\activate.bat && python edge\subscriber.py --reset"
timeout /t 3 /nobreak >nul

echo Starting the simulated sensors...
start "2. Simulated sensors" cmd /k "call venv\Scripts\activate.bat && python simulator\publisher.py"
timeout /t 2 /nobreak >nul

echo Starting the dashboard...
start "3. Dashboard" cmd /k "call venv\Scripts\activate.bat && streamlit run dashboard\app.py"

echo.
echo Demo started. The dashboard opens in your browser in a few seconds.
echo Close the 3 windows to stop the demo.
timeout /t 5 >nul
