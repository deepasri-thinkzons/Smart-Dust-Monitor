# MQ-135 + DHT11 + ESP32 + SQLite/SQLAlchemy + Ollama Premium Local Dashboard

## Architecture
ESP32 -> HTTP POST -> Python Flask -> SQLite (SQLAlchemy) -> minute/hour/day aggregation -> Ollama -> dashboard.

The ESP32 keeps Blynk, LCD, buzzer, MQ-135 and DHT11. The PC is the local server/AI machine.

## 1. Install Ollama
Install Ollama for Windows from https://ollama.com/download/windows then in PowerShell:

    ollama pull gemma3:1b
    ollama run gemma3:1b

The Python application expects Ollama at http://127.0.0.1:11434.

## 2. Python
Open PowerShell in the `python` folder:

    py -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python app.py

Open http://127.0.0.1:5000

## 3. ESP32
Before flashing, replace `YOUR_BLYNK_AUTH_TOKEN`, `YOUR_WIFI_SSID`,
`YOUR_WIFI_PASSWORD` and `YOUR_PC_IP` in
`esp32/MQ135_ESP32_LocalAI/MQ135_ESP32_LocalAI.ino` with your local values.
Do not commit real credentials. Rotate any credentials that were previously
embedded in a shared sketch.
Install these Arduino libraries:
- Blynk
- DHT sensor library
- Adafruit Unified Sensor
- LiquidCrystal_I2C

The ESP32 posts one sample per second to the Python server. Blynk continues to update every 2 seconds.

## 4. Existing CSV
Put your existing `sensorData.csv` in `data/` and run:

    python import_csv.py

The importer accepts the existing header:
`timestamp_ms,adc,voltage,rs,r0,rs_r0,ppm,temperature,humidity,status`

Imported rows are deduplicated by a hash.

## 5. AI
The AI is intentionally not called for every second. It runs:
- when a minute is abnormal (POOR/CRITICAL or strong change),
- once per hour,
- on demand from the dashboard.

The dashboard's **Analyze Workbook** action reads
`data/MQ135_5_Locations_1Hour_Analytics.xlsx`. It analyzes the workbook's
per-location summary, one-hour summary, and latest 12 minute comparisons.
Replace that file to analyze another workbook with the same sheet names and
columns; install `python/requirements.txt` to include the Excel reader.

Python calculates statistics. Ollama interprets them and recommends inspection/modification. It must not directly control the buzzer or other safety hardware.

## Important MQ-135 note
PPM is treated as estimated/project-calibrated data. MQ-135 is broad-spectrum; do not interpret its output as exact gas identification without gas-specific calibration/reference data.

## Database
SQLite file: `data/sensor.db`
Tables:
- raw_samples
- minute_stats
- hourly_stats
- daily_stats
- ai_insights

CSV export endpoints are provided by the dashboard; CSV is not the primary database, avoiding the previous Windows file-lock problem.
