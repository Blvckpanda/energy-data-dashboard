"""
clean.py

Owns data cleaning and quality logging.
Accepts a raw DataFrame from ingest.py, applies cleaning steps
in a defined sequence, and returns a clean DataFrame.

Side effect: appends structured CSV rows to logs/data_quality.log
after every run. This file is append-only and never truncated.
"""

import uuid
import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import config


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """
    Run the full cleaning pipeline on a raw SCADA DataFrame.

    Steps executed in order:
      1. Remove duplicate rows
      2. Coerce numeric columns
      3. Handle nulls (drop critical, fill non-critical with median)
      4. Parse the datetime column

    Parameters:
        df (pd.DataFrame): raw DataFrame from ingest.load_csv(),
                           schema already validated by ingest.validate_schema()

    Returns:
        tuple[pd.DataFrame, str]:
            - clean DataFrame with correct dtypes, no duplicates, no nulls
              in critical columns
            - run_id (str): UUID4 string identifying this run, used by
              main.py to filter the quality log for the current run

    Assumptions:
        - All five SCADA columns are present (validated upstream)
        - Input DataFrame is not modified in place — a copy is made
    """
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()

    df = df.copy()
    df = _remove_duplicates(df, run_id, run_timestamp)
    df = _coerce_numeric(df, run_id, run_timestamp)
    df = _handle_nulls(df, run_id, run_timestamp)
    df = _parse_datetime(df, run_id, run_timestamp)

    return df, run_id


def _remove_duplicates(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Remove fully duplicate rows from the DataFrame.

    A duplicate is defined as a row where ALL column values
    are identical to another row.

    Parameters:
        df (pd.DataFrame): DataFrame to deduplicate
        run_id (str): UUID for this run, written to the log
        run_timestamp (str): ISO 8601 run start time, written to the log

    Returns:
        pd.DataFrame: deduplicated DataFrame

    Assumptions:
        - A duplicate is defined as a row where ALL column values
          are identical to another row
    """
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)

    _append_log([
        {
            config.LOG_FIELD_RUN_ID:       run_id,
            config.LOG_FIELD_TIMESTAMP:    run_timestamp,
            config.LOG_FIELD_COLUMN:       "row",
            config.LOG_FIELD_ISSUE_TYPE:   "duplicate",
            config.LOG_FIELD_ROW_COUNT:    dropped,
            config.LOG_FIELD_ACTION_TAKEN: "dropped",
        }
    ])

    return df


def _coerce_numeric(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Coerce all four numeric SCADA columns to float64.

    Non-numeric values (strings, symbols) become NaN via
    pd.to_numeric(errors='coerce'). NaN values are addressed
    in the subsequent _handle_nulls step.

    Parameters:
        df (pd.DataFrame): DataFrame with raw column types
        run_id (str): UUID for this run
        run_timestamp (str): ISO 8601 run start time

    Returns:
        pd.DataFrame: DataFrame with numeric columns cast to float64

    Assumptions:
        - COL_DATETIME is not touched by this function
        - Columns are already present (validated by ingest)
    """
    numeric_cols = [
        config.COL_ACTIVE_POWER,
        config.COL_WIND_SPEED,
        config.COL_THEORETICAL,
        config.COL_WIND_DIRECTION,
    ]
    log_entries = []

    for col in numeric_cols:
        before_nulls = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_nulls = df[col].isna().sum()
        newly_coerced = int(after_nulls - before_nulls)

        log_entries.append({
            config.LOG_FIELD_RUN_ID:       run_id,
            config.LOG_FIELD_TIMESTAMP:    run_timestamp,
            config.LOG_FIELD_COLUMN:       col,
            config.LOG_FIELD_ISSUE_TYPE:   "type_coercion",
            config.LOG_FIELD_ROW_COUNT:    newly_coerced,
            config.LOG_FIELD_ACTION_TAKEN: "coerced",
        })

    _append_log(log_entries)
    return df


def _handle_nulls(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Handle null values using column-specific strategies.

    Critical columns (COL_DATETIME, COL_ACTIVE_POWER):
        Rows with nulls are dropped entirely.

    Non-critical columns (COL_WIND_SPEED, COL_THEORETICAL,
    COL_WIND_DIRECTION):
        Nulls are filled with the column median. Median is
        computed BEFORE any filling so it reflects the true
        distribution of real values.

    Parameters:
        df (pd.DataFrame): DataFrame after numeric coercion
        run_id (str): UUID for this run
        run_timestamp (str): ISO 8601 run start time

    Returns:
        pd.DataFrame: DataFrame with no nulls in critical columns
                      and medians substituted in non-critical columns

    Assumptions:
        - Numeric coercion has already run — non-critical columns
          are float64 so median() is meaningful
    """
    log_entries = []

    # Critical columns — drop rows with nulls
    for col in config.CRITICAL_COLUMNS:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            df = df.dropna(subset=[col])
        log_entries.append({
            config.LOG_FIELD_RUN_ID:       run_id,
            config.LOG_FIELD_TIMESTAMP:    run_timestamp,
            config.LOG_FIELD_COLUMN:       col,
            config.LOG_FIELD_ISSUE_TYPE:   "null",
            config.LOG_FIELD_ROW_COUNT:    null_count,
            config.LOG_FIELD_ACTION_TAKEN: "dropped",
        })

    # Non-critical columns — fill nulls with column median
    for col in config.MEDIAN_FILL_COLUMNS:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
        log_entries.append({
            config.LOG_FIELD_RUN_ID:       run_id,
            config.LOG_FIELD_TIMESTAMP:    run_timestamp,
            config.LOG_FIELD_COLUMN:       col,
            config.LOG_FIELD_ISSUE_TYPE:   "null",
            config.LOG_FIELD_ROW_COUNT:    null_count,
            config.LOG_FIELD_ACTION_TAKEN: "filled_median",
        })

    _append_log(log_entries)
    return df


def _parse_datetime(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Parse COL_DATETIME to datetime64 dtype.

    Strategy:
      1. Primary: pd.to_datetime(format=config.DATE_FORMAT)
      2. Fallback: pd.to_datetime(format='mixed')
         — prints a [WARN] terminal message if used
      3. If both fail: raises SystemExit with a plain-English message

    Parameters:
        df (pd.DataFrame): DataFrame with COL_DATETIME as a string column
        run_id (str): UUID for this run
        run_timestamp (str): ISO 8601 run start time

    Returns:
        pd.DataFrame: DataFrame with COL_DATETIME as datetime64

    Assumptions:
        - Null rows in COL_DATETIME have already been dropped
    """
    inferred = False

    try:
        df[config.COL_DATETIME] = pd.to_datetime(
            df[config.COL_DATETIME], format=config.DATE_FORMAT
        )
    except (ValueError, TypeError):
        try:
            print("[WARN] Date format inferred — verify output timestamps")
            df[config.COL_DATETIME] = pd.to_datetime(
                df[config.COL_DATETIME], format="mixed"
            )
            inferred = True
        except Exception as e:
            raise SystemExit(
                f"Error: Could not parse date column '{config.COL_DATETIME}'.\n"
                f"Primary format '{config.DATE_FORMAT}' failed.\n"
                f"Inference also failed: {e}"
            )

    issue_type = "date_parse_failure" if inferred else "type_coercion"
    _append_log([
        {
            config.LOG_FIELD_RUN_ID:       run_id,
            config.LOG_FIELD_TIMESTAMP:    run_timestamp,
            config.LOG_FIELD_COLUMN:       config.COL_DATETIME,
            config.LOG_FIELD_ISSUE_TYPE:   issue_type,
            config.LOG_FIELD_ROW_COUNT:    0,
            config.LOG_FIELD_ACTION_TAKEN: "coerced",
        }
    ])

    return df


def _append_log(entries: list[dict]) -> None:
    """
    Append one or more quality log entries to logs/data_quality.log.

    Creates the file with a header row on first write.
    Appends on all subsequent writes — never truncates.

    Parameters:
        entries (list[dict]): list of dicts, each containing all
                              six fields defined in config.LOG_FIELDS

    Returns:
        None

    Assumptions:
        - config.LOG_PATH parent directory (logs/) already exists
        - Each dict in entries contains exactly the keys in
          config.LOG_FIELDS in any order
    """
    log_path: Path = config.LOG_PATH
    file_exists = log_path.exists()

    with open(log_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=config.LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(entries)