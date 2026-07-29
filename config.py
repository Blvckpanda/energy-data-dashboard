"""
config.py

Single source of truth for all constants. Lives at the project root.
Contains column names, file paths, date formats, numeric thresholds,
and log field names. Contains no logic. Imported by all other modules.
"""

from pathlib import Path

# ── SCADA Column Names ────────────────────────────────────────────
COL_DATETIME       = "Date/Time"
COL_ACTIVE_POWER   = "LV ActivePower (kW)"
COL_WIND_SPEED     = "Wind Speed (m/s)"
COL_THEORETICAL    = "Theoretical_Power_Curve (KWh)"
COL_WIND_DIRECTION = "Wind Direction (°)"

# Columns where null rows are DROPPED (critical)
CRITICAL_COLUMNS = [COL_DATETIME, COL_ACTIVE_POWER]

# Columns where nulls are FILLED with column median (non-critical)
MEDIAN_FILL_COLUMNS = [COL_WIND_SPEED, COL_THEORETICAL, COL_WIND_DIRECTION]

# ── Date Parsing ──────────────────────────────────────────────────
# Primary format expected in the SCADA CSV (10-minute intervals)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── File Paths ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR     = PROJECT_ROOT / "data"
OUTPUT_DIR   = PROJECT_ROOT / "output"
CHARTS_DIR   = OUTPUT_DIR / "charts"
LOGS_DIR     = PROJECT_ROOT / "logs"
LOG_PATH     = LOGS_DIR / "data_quality.log"

# ── Quality Log Fields ────────────────────────────────────────────
LOG_FIELD_RUN_ID        = "run_id"
LOG_FIELD_TIMESTAMP     = "run_timestamp"
LOG_FIELD_COLUMN        = "column"
LOG_FIELD_ISSUE_TYPE    = "issue_type"
LOG_FIELD_ROW_COUNT     = "row_count"
LOG_FIELD_ACTION_TAKEN  = "action_taken"

LOG_FIELDS = [
    LOG_FIELD_RUN_ID,
    LOG_FIELD_TIMESTAMP,
    LOG_FIELD_COLUMN,
    LOG_FIELD_ISSUE_TYPE,
    LOG_FIELD_ROW_COUNT,
    LOG_FIELD_ACTION_TAKEN,
]

# ── Analysis Thresholds ───────────────────────────────────────────
# Number of compass bins for wind direction distribution
WIND_DIRECTION_BINS = 16

# Rows excluded from efficiency if either condition is true:
# COL_THEORETICAL == 0  →  non-operational period
# COL_ACTIVE_POWER <= 0  →  turbine not producing
EFFICIENCY_MIN_THEORETICAL = 0   # exclusive (> 0 required)
EFFICIENCY_MIN_ACTIVE_POWER = 0  # exclusive (> 0 required)

# ── Solar SCADA Column Names ───────────────────────────────────────
COL_SOLAR_DATETIME = "DATE_TIME"
COL_PLANT_ID       = "PLANT_ID"
COL_SOURCE_KEY     = "SOURCE_KEY"
COL_DC_POWER       = "DC_POWER"
COL_AC_POWER       = "AC_POWER"
COL_DAILY_YIELD    = "DAILY_YIELD"
COL_TOTAL_YIELD    = "TOTAL_YIELD"

SOLAR_DATE_FORMAT = "%d-%m-%Y %H:%M"

SOLAR_CRITICAL_COLUMNS    = [COL_SOLAR_DATETIME, COL_AC_POWER]
SOLAR_MEDIAN_FILL_COLUMNS = [COL_DC_POWER, COL_DAILY_YIELD, COL_TOTAL_YIELD]

CONVERSION_MIN_DC = 0   # exclusive — DC_POWER > 0 required (daylight)
CONVERSION_MIN_AC = 0   # exclusive — AC_POWER > 0 required

# ── Schema Registry ────────────────────────────────────────────────
SCHEMA_REGISTRY = {
    "wind": {
        "required_columns": [
            COL_DATETIME, COL_ACTIVE_POWER, COL_WIND_SPEED,
            COL_THEORETICAL, COL_WIND_DIRECTION,
        ],
        "datetime_col":         COL_DATETIME,
        "date_format":          DATE_FORMAT,
        "critical_columns":     CRITICAL_COLUMNS,
        "median_fill_columns":  MEDIAN_FILL_COLUMNS,
        "primary_power_col":    COL_ACTIVE_POWER,
        "secondary_col":        COL_WIND_SPEED,
        "reference_col":        COL_THEORETICAL,
        "ratio_name":           "efficiency_ratio",
        "min_primary":          EFFICIENCY_MIN_ACTIVE_POWER,
        "min_reference":        EFFICIENCY_MIN_THEORETICAL,
    },
    "solar": {
        "required_columns": [
            COL_SOLAR_DATETIME, COL_PLANT_ID, COL_SOURCE_KEY,
            COL_DC_POWER, COL_AC_POWER, COL_DAILY_YIELD, COL_TOTAL_YIELD,
        ],
        "datetime_col":         COL_SOLAR_DATETIME,
        "date_format":          SOLAR_DATE_FORMAT,
        "critical_columns":     SOLAR_CRITICAL_COLUMNS,
        "median_fill_columns":  SOLAR_MEDIAN_FILL_COLUMNS,
        "primary_power_col":    COL_AC_POWER,
        "secondary_col":        COL_DC_POWER,
        "reference_col":        COL_DC_POWER,
        "ratio_name":           "conversion_ratio",
        "min_primary":          CONVERSION_MIN_AC,
        "min_reference":        CONVERSION_MIN_DC,
    },
}

# ── Anomaly Detection ─────────────────────────────────────────────
ANOMALY_STD_THRESHOLD    = 2.0   # std deviations from mean to flag
ANOMALY_ROLLING_WINDOW   = 36    # intervals (36 × 10-min = 6 hours)
ANOMALY_ROLLING_DROP_PCT = 0.20  # rolling mean drop % to flag
