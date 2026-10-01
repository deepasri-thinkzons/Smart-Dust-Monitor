# ============================================================
# MQ-135 AI COMMAND CENTER
# Flask Backend
# SQLite + SQLAlchemy + Ollama
# ============================================================

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    Response
)

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import csv
import io


IST = ZoneInfo("Asia/Kolkata")


def as_ist(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=IST)
        return value.astimezone(IST)

    return value


# ============================================================
# DATABASE MODELS
# ============================================================

from models import (
    SessionLocal,
    RawSample,
    MinuteStat,
    HourlyStat,
    DailyStat
)


# ============================================================
# DATABASE QUERIES
# ============================================================

from queries import (
    latest_raw,
    latest_stats,
    latest_ai,
    insert_raw
)


# ============================================================
# ANALYTICS
# ============================================================

from analytics import (
    calculate_minute,
    calculate_hour,
    calculate_day
)


# ============================================================
# AI ENGINE
# ============================================================

from ai_engine import (
    ask_ai,
    check_ollama,
    get_workbook_sheet_data,
    MODEL
)


# ============================================================
# SQLALCHEMY
# ============================================================

from sqlalchemy import select


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder="templates"
)


# ============================================================
# DATABASE OBJECT -> DICTIONARY
# ============================================================

def rowdict(row):

    if row is None:
        return None

    result = {}

    for key, value in vars(row).items():

        if not key.startswith("_"):

            if isinstance(value, datetime):
                value = as_ist(value)
                if value is not None:
                    value = value.isoformat()

            result[key] = value

    return result


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    ollama = check_ollama()

    return jsonify({
        "server": True,
        "ollama": ollama,
        "model": MODEL,
        "time": datetime.now(IST).isoformat()
    })


# ============================================================
# RECEIVE ESP32 SENSOR DATA
# ============================================================

@app.post("/api/sample")
def sample():

    try:

        data = request.get_json(force=True)

        if data is None:
            return jsonify({
                "ok": False,
                "error": "No JSON data received."
            }), 400

        now = datetime.now(IST)

        def number(key, default=0):
            try:
                return float(data.get(key, default))
            except (TypeError, ValueError):
                return float(default)

        row = {
            "ts": now,
            "source": str(data.get("source", "ESP32")),
            "device_ms": data.get("device_ms"),
            "adc": number("adc"),
            "voltage": number("voltage"),
            "rs": number("rs"),
            "r0": number("r0"),
            "ratio": number("ratio"),
            "ppm": number("ppm"),
            "temperature": number("temperature"),
            "humidity": number("humidity"),
            "status": str(data.get("status", "UNKNOWN"))
        }

        inserted = insert_raw(row)

        completed_minute = now - timedelta(minutes=1)
        calculate_minute(completed_minute)

        completed_hour = now - timedelta(hours=1)
        calculate_hour(completed_hour)

        completed_day = now - timedelta(days=1)
        calculate_day(completed_day)

        return jsonify({
            "ok": True,
            "id": inserted.id,
            "server_time": now.isoformat()
        })

    except Exception as e:
        print("ERROR /api/sample:", repr(e))
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ============================================================
# DASHBOARD DATA
# ============================================================

@app.get("/api/data")
def data():

    try:

        # ----------------------------------------------------
        # Raw data
        # ----------------------------------------------------

        raw = latest_raw(60)


        # ----------------------------------------------------
        # Minute statistics
        # ----------------------------------------------------

        minutes = latest_stats(
            MinuteStat,
            60
        )


        # ----------------------------------------------------
        # Hour statistics
        # ----------------------------------------------------

        hours = latest_stats(
            HourlyStat,
            48
        )


        # ----------------------------------------------------
        # Day statistics
        # ----------------------------------------------------

        days = latest_stats(
            DailyStat,
            30
        )


        # ----------------------------------------------------
        # AI history
        # ----------------------------------------------------

        ai = latest_ai(10)


        return jsonify({

            "raw":
                [
                    rowdict(x)
                    for x in raw
                ],

            "minute":
                [
                    rowdict(x)
                    for x in minutes
                ],

            "hour":
                [
                    rowdict(x)
                    for x in hours
                ],

            "day":
                [
                    rowdict(x)
                    for x in days
                ],

            "ai":
                [
                    rowdict(x)
                    for x in ai
                ]

        })


    except Exception as e:

        print(
            "ERROR /api/data:",
            repr(e)
        )


        return jsonify({

            "error":
                str(e)

        }), 500


@app.get("/api/workbook")
def workbook_sheet():

    try:
        result = get_workbook_sheet_data(
            request.args.get("sheet", "Analytics_Summary"),
            request.args.get("offset", 0),
            request.args.get("limit", 50)
        )
        return jsonify({"ok": True, **result})

    except ValueError as error:
        return jsonify({"ok": False, "error": str(error)}), 400

    except FileNotFoundError as error:
        return jsonify({"ok": False, "error": str(error)}), 404

    except Exception as error:
        app.logger.exception("Workbook data request failed")
        return jsonify({"ok": False, "error": str(error)}), 500


# ============================================================
# AI ANALYSIS
# ============================================================

@app.post("/api/ai/<period>")
def ai_analysis(period):

    # --------------------------------------------------------
    # Validate period
    # --------------------------------------------------------

    if period not in (
        "minute",
        "hour",
        "day",
        "workbook"
    ):

        return jsonify({

            "ok": False,

            "error":
                "Invalid period. "
                "Use minute, hour, day or workbook."

        }), 400


    try:

        print()
        print(
            "========================================"
        )

        print(
            "AI ANALYSIS REQUEST"
        )

        print(
            "Period:",
            period
        )

        print(
            "Model:",
            MODEL
        )

        print(
            "========================================"
        )


        # ----------------------------------------------------
        # Ask Ollama
        # ----------------------------------------------------

        insight = ask_ai(period)


        # ----------------------------------------------------
        # No statistical data
        # ----------------------------------------------------

        if insight is None:

            return jsonify({

                "ok": False,

                "error":
                    "No analysis data is available for " +
                    period +
                    ". Check that the workbook or sensor statistics exist."

            }), 404


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        print(
            "AI ANALYSIS COMPLETE"
        )


        return jsonify({

            "ok": True,

            "insight":
                rowdict(insight)

        })


    except Exception as e:

        print()
        print(
            "========================================"
        )

        print(
            "AI ERROR"
        )

        print(
            repr(e)
        )

        print(
            "========================================"
        )


        return jsonify({

            "ok": False,

            "error":
                str(e)

        }), 500


# ============================================================
# OLLAMA STATUS
# ============================================================

@app.get("/api/ollama")
def ollama_status():

    try:

        result = check_ollama()


        return jsonify({

            "model":
                MODEL,

            **result

        })


    except Exception as e:

        return jsonify({

            "running":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# CSV EXPORT
# ============================================================

@app.get("/api/export/<kind>.csv")
def export_csv(kind):

    # --------------------------------------------------------
    # Select database model
    # --------------------------------------------------------

    model_map = {

        "raw":
            RawSample,

        "minute":
            MinuteStat,

        "hour":
            HourlyStat,

        "day":
            DailyStat

    }


    model = model_map.get(
        kind
    )


    if model is None:

        return (
            "Invalid export type",
            400
        )


    # --------------------------------------------------------
    # Read database
    # --------------------------------------------------------

    with SessionLocal() as session:

        rows = list(
            session.scalars(
                select(model)
                .order_by(model.id)

            ).all()

        )


    # --------------------------------------------------------
    # Empty CSV
    # --------------------------------------------------------

    if not rows:

        return Response(
            "",

            mimetype="text/csv"

        )


    # --------------------------------------------------------
    # Get columns
    # --------------------------------------------------------

    fields = [

        key

        for key in vars(
            rows[0]
        )

        if not key.startswith("_")

    ]


    # --------------------------------------------------------
    # Build CSV
    # --------------------------------------------------------

    output = io.StringIO()


    writer = csv.writer(
        output
    )


    writer.writerow(
        fields
    )


    for row in rows:

        writer.writerow([

            getattr(
                row,
                field
            )

            for field in fields

        ])


    # --------------------------------------------------------
    # Return file
    # --------------------------------------------------------

    filename = f"{kind}Data.csv"


    return Response(
        output.getvalue(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
                f"attachment; filename={filename}"

        }

    )


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "=============================================="
    )

    print(
        "     MQ-135 AI COMMAND CENTER"
    )

    print(
        "=============================================="
    )

    print(
        "Flask : http://127.0.0.1:5000"
    )

    print(
        "Ollama: http://127.0.0.1:11434"
    )

    print(
        "Model :",
        MODEL
    )

    print(
        "=============================================="
    )

    print()


    app.run(
        host="0.0.0.0",

        port=5000,

        debug=False

    )