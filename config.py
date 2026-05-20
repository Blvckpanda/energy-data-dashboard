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
