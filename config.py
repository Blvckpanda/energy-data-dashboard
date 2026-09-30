"""
config.py

Single source of truth for all constants. Lives at the project root.
Contains column names, file paths, date formats, numeric thresholds,
and log field names. Contains no logic. Imported by all other modules.
"""

from pathlib import Path

# ── Wind Turbine SCADA Column Names ───────────────────────────────
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
# Primary format expected in the wind SCADA CSV (10-minute intervals)
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
# Number of compass bins for wind direction distribution (consumed
# via SCHEMA_REGISTRY['wind']['distribution']['bins'])
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

# ── Hydro SCADA Column Names ────────────────────────────────────────
COL_HYDRO_DATETIME          = "Timestamp"
COL_HYDRO_FLOW              = "Water_Flow_Rate (m3/s)"
COL_HYDRO_GENERATED_POWER   = "Generated_Power (kW)"
COL_HYDRO_THEORETICAL_POWER = "Theoretical_Potential (kW)"

HYDRO_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

HYDRO_CRITICAL_COLUMNS   = [COL_HYDRO_DATETIME, COL_HYDRO_GENERATED_POWER]
HYDRO_MEDIAN_FILL_COLUMNS = [
    COL_HYDRO_FLOW, COL_HYDRO_THEORETICAL_POWER,
]

HYDRO_MIN_GENERATED  = 0  # exclusive — Generated_Power > 0 required
HYDRO_MIN_THEORETICAL = 0  # exclusive — Theoretical_Potential > 0 required

# ── Schema Registry ────────────────────────────────────────────────
# Adding a new schema requires ONLY a column-constant block above and
# one registry entry here. Pipeline modules derive everything else —
# CLI choices, labels, headers, scatter references, narrative
# sentences, and analysis intervals — from this dict.
#
# Registry keys:
#   required_columns     columns the CSV must contain
#   datetime_col         parsed to datetime64 during cleaning
#   date_format          primary parse format ('mixed' is the fallback)
#   critical_columns     rows with nulls here are dropped
#   median_fill_columns  nulls here are filled with the column median
#   primary_power_col    output metric (efficiency numerator)
#   secondary_col        scatter x-axis metric
#   reference_col        efficiency denominator
#   ratio_name           results-dict key for the per-row ratio
#   min_primary          primary must be > this to be operational
#   min_reference        reference must be > this to be operational
#   primary_label / secondary_label   plain-English chart labels
#   ratio_label          plain-English label for the mean ratio
#   asset_label          report title fragment, e.g. "Wind Turbine"
#   display_names        raw column -> plain-English sheet header
#   interval_minutes     minutes per SCADA row (operational-hours math)
#   scatter_reference    "column"  — plot reference_col as the curve
#                        "identity" — plot an ideal 1:1 y=x line
#   distribution         how the distribution analysis works:
#                        {"kind": "bins", "col", "bins"}      (fixed
#                        numeric binning of one column) or
#                        {"kind": "group_mean", "group_col",
#                         "value_col"}                         (mean
#                        of one value per group of another)
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
        "primary_label":        "Active Power (kW)",
        "secondary_label":      "Wind Speed (m/s)",
        "ratio_label":          "Efficiency",
        "asset_label":          "Wind Turbine",
        "display_names": {
            COL_DATETIME:       "Timestamp",
            COL_ACTIVE_POWER:   "Active Power (kW)",
            COL_WIND_SPEED:     "Wind Speed (m/s)",
            COL_THEORETICAL:    "Theoretical Power (kWh)",
            COL_WIND_DIRECTION: "Wind Direction (°)",
        },
        "interval_minutes":     10,
        "scatter_reference":    "column",
        "distribution": {
            "kind": "bins",
            "col":  COL_WIND_DIRECTION,
            "bins": WIND_DIRECTION_BINS,
        },
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
        "primary_label":        "AC Power (kW)",
        "secondary_label":      "DC Power (kW)",
        "ratio_label":          "Conversion Ratio",
        "asset_label":          "Solar Power",
        "display_names": {
            COL_SOLAR_DATETIME: "Timestamp",
            COL_PLANT_ID:       "Plant ID",
            COL_SOURCE_KEY:     "Inverter ID",
            COL_DC_POWER:       "DC Power (kW)",
            COL_AC_POWER:       "AC Power (kW)",
            COL_DAILY_YIELD:    "Daily Yield (kWh)",
            COL_TOTAL_YIELD:    "Total Yield (kWh)",
        },
        "interval_minutes":     15,
        "scatter_reference":    "identity",
        "distribution": {
            "kind":       "group_mean",
            "group_col":  COL_SOURCE_KEY,
            "value_col":  COL_AC_POWER,
        },
    },
    "hydro": {
        "required_columns": [
            COL_HYDRO_DATETIME, COL_HYDRO_FLOW,
            COL_HYDRO_GENERATED_POWER, COL_HYDRO_THEORETICAL_POWER,
        ],
        "datetime_col":         COL_HYDRO_DATETIME,
        "date_format":          HYDRO_DATE_FORMAT,
        "critical_columns":     HYDRO_CRITICAL_COLUMNS,
        "median_fill_columns":  HYDRO_MEDIAN_FILL_COLUMNS,
        "primary_power_col":    COL_HYDRO_GENERATED_POWER,
        "secondary_col":        COL_HYDRO_FLOW,
        "reference_col":        COL_HYDRO_THEORETICAL_POWER,
        "ratio_name":           "conversion_ratio",
        "min_primary":          HYDRO_MIN_GENERATED,
        "min_reference":        HYDRO_MIN_THEORETICAL,
        "primary_label":        "Generated Power (kW)",
        "secondary_label":      "Water Flow Rate (m³/s)",
        "ratio_label":          "Conversion Ratio",
        "asset_label":          "Hydro Turbine",
        "display_names": {
            COL_HYDRO_DATETIME:          "Timestamp",
            COL_HYDRO_FLOW:              "Water Flow Rate (m³/s)",
            COL_HYDRO_GENERATED_POWER:   "Generated Power (kW)",
            COL_HYDRO_THEORETICAL_POWER: "Theoretical Potential (kW)",
        },
        "interval_minutes":     10,
        "scatter_reference":    "column",
        "distribution": {
            "kind": "bins",
            "col":  COL_HYDRO_FLOW,
            "bins": 12,
        },
    },
}

# ── Anomaly Detection ─────────────────────────────────────────────
ANOMALY_STD_THRESHOLD    = 2.0   # std deviations from mean to flag
ANOMALY_ROLLING_WINDOW   = 36    # intervals (36 × 10-min = 6 hours)
ANOMALY_ROLLING_DROP_PCT = 0.20  # rolling mean drop % to flag
