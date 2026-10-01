# ============================================================
# MQ-135 AI ENGINE
# Local Ollama + Gemma 3
# ============================================================

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from models import (
    MinuteStat,
    HourlyStat,
    DailyStat
)

from queries import (
    latest_stats,
    save_ai
)


# ============================================================
# OLLAMA CONFIGURATION
# ============================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

MODEL = "gemma3:1b"
WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "data" / "MQ135_5_Locations_1Hour_Analytics.xlsx"
WORKBOOK_SHEETS = (
    "Analytics_Summary",
    "Hour_Summary",
    "Minute_Averages",
    "Minute_PPM_Comparison",
    "Raw_Second_Data"
)


# ============================================================
# PERIOD -> SQLALCHEMY MODEL
#
# IMPORTANT:
# Do NOT use:
#
# latest_stats("minute", 3)
#
# because SQLAlchemy expects a model.
# ============================================================

MODEL_MAP = {

    "minute": MinuteStat,

    "hour": HourlyStat,

    "day": DailyStat

}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """

You are a local AI analyst for an indoor air-quality
monitoring system.

The system uses:

- MQ-135
- DHT11
- ESP32
- SQLite
- statistical aggregation

The MQ-135 value is an estimated/project-calibrated
pollution value.

IMPORTANT RULES:

1. Do not identify a specific gas unless the supplied
   data explicitly contains gas-specific calibration.

2. Do not invent measurements.

3. Analyze only the supplied data.

4. Use the statistical values such as:
   average,
   minimum,
   maximum,
   standard deviation,
   temperature,
   humidity,
   trend,
   sample count.

5. Explain what the data suggests.

6. Give practical environmental modifications.

7. Recommendations may include:
   ventilation,
   checking pollution sources,
   checking sensor placement,
   checking HVAC/air circulation,
   checking doors/windows,
   checking unusual spikes.

8. Do not directly control hardware.

9. Do not claim the MQ-135 is a certified safety instrument.

10. Keep the answer concise and useful.

Return ONLY valid JSON.

Required JSON structure:

{
    "overall_status": "EXCELLENT",
    "priority": "INFORMATION",
    "problem": "Short description",
    "evidence": "Evidence from the supplied data",
    "possible_causes": "Possible causes",
    "recommendation": "Specific recommended modification",
    "verification": "How to verify whether the modification helped"
}

Priority must be exactly one of:

INFORMATION
OBSERVE
ACTION
CRITICAL

"""


# ============================================================
# CHECK OLLAMA
# ============================================================

def check_ollama():

    try:

        response = requests.get(
            "http://127.0.0.1:11434/api/version",
            timeout=5
        )

        response.raise_for_status()

        return {
            "running": True,
            "version": response.json().get(
                "version",
                "unknown"
            )
        }

    except Exception as e:

        return {
            "running": False,
            "error": str(e)
        }


# ============================================================
# GET AI INPUT DATA
# ============================================================

def get_analysis_data(period_type):

    if period_type not in MODEL_MAP:

        raise ValueError(
            f"Invalid period type: {period_type}"
        )


    # IMPORTANT FIX
    #
    # Get the actual SQLAlchemy model.
    model = MODEL_MAP[period_type]


    # Get the latest 3 completed statistical periods.
    rows = latest_stats(
        model,
        3
    )


    if not rows:

        return None, []


    # latest_stats() returns newest-first.
    #
    # Reverse it so AI sees:
    #
    # oldest -> newest
    #
    rows = list(reversed(rows))


    statistics = []


    for row in rows:

        item = {

            "period_start":
                row.period_start.isoformat()
                if row.period_start
                else None,

            "sample_count":
                getattr(
                    row,
                    "sample_count",
                    None
                ),

            "minute_count":
                getattr(
                    row,
                    "minute_count",
                    None
                ),

            "hour_count":
                getattr(
                    row,
                    "hour_count",
                    None
                ),

            "ppm_avg":
                getattr(
                    row,
                    "ppm_avg",
                    None
                ),

            "ppm_min":
                getattr(
                    row,
                    "ppm_min",
                    None
                ),

            "ppm_max":
                getattr(
                    row,
                    "ppm_max",
                    None
                ),

            "ppm_std":
                getattr(
                    row,
                    "ppm_std",
                    None
                ),

            "temperature_avg":
                getattr(
                    row,
                    "temp_avg",
                    None
                ),

            "humidity_avg":
                getattr(
                    row,
                    "humidity_avg",
                    None
                ),

            "poor_count":
                getattr(
                    row,
                    "poor_count",
                    getattr(
                        row,
                        "poor_minutes",
                        getattr(
                            row,
                            "poor_hours",
                            None
                        )
                    )
                ),

            "critical_count":
                getattr(
                    row,
                    "critical_count",
                    getattr(
                        row,
                        "critical_minutes",
                        getattr(
                            row,
                            "critical_hours",
                            None
                        )
                    )
                ),

            "trend":
                getattr(
                    row,
                    "trend",
                    "UNKNOWN"
                )

        }


        statistics.append(item)


    return rows, statistics


# ============================================================
# BUILD PROMPT
# ============================================================

def build_prompt(
    period_type,
    statistics
):

    data = {

        "system": "MQ-135 indoor air monitoring",

        "period": period_type,

        "statistics": statistics

    }


    return f"""

Analyze the following MQ-135 sensor statistics.

The data represents aggregated measurements from
a single ESP32.

Period:
{period_type}

Sensor statistics:

{json.dumps(
    data,
    indent=2,
    default=str
)}

Provide:

1. Overall status
2. Priority
3. Problem detected
4. Evidence from the measurements
5. Possible causes
6. A practical specific modification
7. A verification procedure

Remember:

- Do not invent sensor readings.
- MQ-135 PPM is an estimated/project-calibrated value.
- Do not claim exact gas identification.
- Do not directly control hardware.
- Base your answer on the supplied statistics.

Return ONLY JSON.
"""


def get_workbook_analysis_data():

    if not WORKBOOK_PATH.is_file():
        raise FileNotFoundError(
            f"Analysis workbook was not found: {WORKBOOK_PATH}"
        )

    analytics = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Analytics_Summary"
    )
    hourly = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Hour_Summary"
    )
    comparison = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name="Minute_PPM_Comparison"
    )

    required_columns = {
        "Analytics_Summary": {
            "Location", "Mean_PPM", "Median_PPM", "Min_PPM",
            "Max_PPM", "StdDev_PPM", "Mean_Temperature_C",
            "Mean_Humidity_pct"
        },
        "Hour_Summary": {
            "Location", "Samples", "Hour_Avg_PPM", "Hour_Min_PPM",
            "Hour_Max_PPM", "Hour_StdDev_PPM",
            "Hour_Avg_Temperature_C", "Hour_Avg_Humidity_pct"
        },
        "Minute_PPM_Comparison": {"Minute"}
    }

    for sheet_name, frame in (
        ("Analytics_Summary", analytics),
        ("Hour_Summary", hourly),
        ("Minute_PPM_Comparison", comparison)
    ):
        missing = required_columns[sheet_name] - set(frame.columns)
        if missing:
            raise ValueError(
                f"Workbook sheet {sheet_name} is missing columns: "
                f"{', '.join(sorted(missing))}"
            )

    if analytics.empty or hourly.empty or comparison.empty:
        raise ValueError("The workbook's analysis sheets must contain data.")

    comparison["Minute"] = pd.to_datetime(
        comparison["Minute"],
        errors="coerce"
    )
    comparison = comparison.dropna(subset=["Minute"]).sort_values("Minute")
    if comparison.empty:
        raise ValueError("The workbook has no valid minute timestamps.")

    def records(frame):
        return json.loads(
            frame.to_json(
                orient="records",
                date_format="iso"
            )
        )

    latest_minute = comparison["Minute"].max().to_pydatetime()
    data = {
        "source_file": WORKBOOK_PATH.name,
        "location_analytics": records(analytics),
        "hour_summary": records(hourly),
        "latest_12_minute_comparisons": records(comparison.tail(12))
    }

    return latest_minute or datetime.now(), data


def get_workbook_sheet_data(sheet_name, offset=0, limit=50):

    if sheet_name not in WORKBOOK_SHEETS:
        raise ValueError("Unknown workbook sheet.")

    try:
        offset = max(0, int(offset))
        limit = min(100, max(1, int(limit)))
    except (TypeError, ValueError):
        raise ValueError("Offset and limit must be integers.") from None

    if not WORKBOOK_PATH.is_file():
        raise FileNotFoundError(
            f"Workbook was not found: {WORKBOOK_PATH}"
        )

    frame = pd.read_excel(
        WORKBOOK_PATH,
        sheet_name=sheet_name
    )
    page = frame.iloc[offset:offset + limit]
    rows = json.loads(
        page.to_json(
            orient="records",
            date_format="iso"
        )
    )

    return {
        "sheet": sheet_name,
        "tabs": list(WORKBOOK_SHEETS),
        "columns": list(frame.columns),
        "rows": rows,
        "total": len(frame),
        "offset": offset,
        "limit": limit
    }


def build_workbook_prompt(data):

    return f"""

Analyze the supplied MQ-135 workbook data for its five monitored locations.
Use the per-location analytics, one-hour statistics, and latest minute-by-minute
comparison to compare locations and identify recent changes or spikes.

Workbook data:
{json.dumps(data, indent=2, default=str)}

Treat PPM as estimated/project-calibrated sensor values, not certified
measurements or exact gas identification. Do not invent readings. Cite the
location and numeric evidence behind conclusions. Suggest practical inspection,
ventilation, or sensor-placement checks and explain how to verify improvement.

Return ONLY JSON with overall_status, priority, problem, evidence,
possible_causes, recommendation, and verification. Priority must be exactly
INFORMATION, OBSERVE, ACTION, or CRITICAL.
"""


# ============================================================
# NORMALIZE AI RESULT
# ============================================================

def normalize_result(
    result
):

    return {

        "overall_status":
            str(
                result.get(
                    "overall_status",
                    "UNKNOWN"
                )
            ),

        "priority":
            str(
                result.get(
                    "priority",
                    "OBSERVE"
                )
            ).upper(),

        "problem":
            str(
                result.get(
                    "problem",
                    ""
                )
            ),

        "evidence":
            str(
                result.get(
                    "evidence",
                    ""
                )
            ),

        "possible_causes":
            str(
                result.get(
                    "possible_causes",
                    ""
                )
            ),

        "recommendation":
            str(
                result.get(
                    "recommendation",
                    ""
                )
            ),

        "verification":
            str(
                result.get(
                    "verification",
                    ""
                )
            )

    }


# ============================================================
# ASK OLLAMA
# ============================================================

def ask_ai(
    period_type="hour"
):

    # --------------------------------------------------------
    # Validate period
    # --------------------------------------------------------

    if period_type not in MODEL_MAP and period_type != "workbook":

        raise ValueError(
            "Period must be minute, hour, day or workbook."
        )


    # --------------------------------------------------------
    # Get statistics
    # --------------------------------------------------------

    if period_type == "workbook":

        period_start, workbook_data = get_workbook_analysis_data()

        prompt = build_workbook_prompt(workbook_data)

    else:

        rows, statistics = get_analysis_data(
            period_type
        )

        if not rows:

            return None

        period_start = rows[-1].period_start

        prompt = build_prompt(
            period_type,
            statistics
        )


    # --------------------------------------------------------
    # Check Ollama first
    # --------------------------------------------------------

    ollama_status = check_ollama()


    if not ollama_status["running"]:

        raise RuntimeError(
            "Ollama is not running. "
            "Start Ollama and try again."
        )


    # --------------------------------------------------------
    # Call Ollama
    # --------------------------------------------------------

    payload = {

        "model": MODEL,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        "stream": False,

        "format": "json"

    }


    response = requests.post(

        OLLAMA_URL,

        json=payload,

        timeout=180

    )


    response.raise_for_status()


    response_json = response.json()


    # --------------------------------------------------------
    # Extract AI message
    # --------------------------------------------------------

    message = response_json.get(
        "message",
        {}
    )


    text = message.get(
        "content",
        ""
    )


    if not text:

        raise RuntimeError(
            "Ollama returned an empty response."
        )


    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        ai_result = json.loads(
            text
        )

    except json.JSONDecodeError:

        ai_result = {

            "overall_status":
                "ANALYSIS",

            "priority":
                "OBSERVE",

            "problem":
                text,

            "evidence":
                "The model returned text instead of structured JSON.",

            "possible_causes":
                "",

            "recommendation":
                "Review the latest sensor statistics and ventilation conditions.",

            "verification":
                "Run another analysis after collecting additional measurements."

        }


    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    ai_result = normalize_result(
        ai_result
    )


    # --------------------------------------------------------
    # Save AI result to SQLite
    # --------------------------------------------------------

    saved = save_ai(

        period_type,

        period_start,

        {

            "priority":
                ai_result["priority"],

            "overall_status":
                ai_result["overall_status"],

            "problem":
                ai_result["problem"],

            "evidence":
                ai_result["evidence"],

            "causes":
                ai_result["possible_causes"],

            "recommendation":
                ai_result["recommendation"],

            "verification":
                ai_result["verification"],

            "raw_response":
                text

        }

    )


    return saved