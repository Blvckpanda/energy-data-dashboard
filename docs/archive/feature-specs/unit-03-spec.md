# Unit 03: Cleaning + Quality Log

## Goal

Implement `clean.py` as a full single-session cleaning pipeline that
deduplicates, coerces types, handles nulls, and parses dates on the
raw DataFrame from `ingest.py` — appending a structured, append-only
entry to `logs/data_quality.log` for every decision made, keyed by a
unique `run_id` and `run_timestamp` so every run is independently
traceable.

---

## Implementation

### 1. Module Structure

`clean.py` owns exactly one pipeline responsibility: taking a raw
DataFrame and returning a clean one. It has one permitted side
effect — appending to `logs/data_quality.log` — which is documented
in the module docstring.

The module exposes one public function called by `main.py`, plus
internal helper functions for each cleaning step. No logic sits at
module level.

```python
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
    ...

# Internal helpers — not called directly by main.py
def _remove_duplicates(df, run_id, run_timestamp): ...
def _coerce_numeric(df, run_id, run_timestamp): ...
def _handle_nulls(df, run_id, run_timestamp): ...
def _parse_datetime(df, run_id, run_timestamp): ...
def _append_log(entries: list[dict]) -> None: ...
```

---

### 2. `clean(df)` — Public Entry Point

The single function `main.py` calls. Generates `run_id` and
`run_timestamp` once at the top, passes them to every internal
helper so all log entries for this run share the same identifiers,
then returns the cleaned DataFrame and the `run_id`.

```python
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
```

The `run_id` is returned to `main.py` because `export.py` (Unit 6)
will need it to filter the quality log to the current run's entries
only when writing the Data Quality Log sheet.

---

### 3. `_remove_duplicates(df, run_id, run_timestamp)`

Removes fully duplicate rows — rows where every column value is
identical.

```python
def _remove_duplicates(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Remove fully duplicate rows from the DataFrame.

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

    _append_log([{
        config.LOG_FIELD_RUN_ID:       run_id,
        config.LOG_FIELD_TIMESTAMP:    run_timestamp,
        config.LOG_FIELD_COLUMN:       "row",
        config.LOG_FIELD_ISSUE_TYPE:   "duplicate",
        config.LOG_FIELD_ROW_COUNT:    dropped,
        config.LOG_FIELD_ACTION_TAKEN: "dropped",
    }])

    return df
```

Log one entry for this step regardless of whether any duplicates
were found. A count of 0 is a valid and useful log entry — it
confirms the check ran.

---

### 4. `_coerce_numeric(df, run_id, run_timestamp)`

Coerces all four numeric SCADA columns to `float64` using
`pd.to_numeric(errors='coerce')`. Values that cannot be converted
become `NaN` — they will be handled in the null step. Log one entry
per column showing how many values were coerced.

```python
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
```

Log all four entries in a single `_append_log` call — one row per
column. A count of 0 is valid and expected for clean columns.

---

### 5. `_handle_nulls(df, run_id, run_timestamp)`

Two distinct strategies depending on whether the column is critical
or non-critical, as defined in `config.CRITICAL_COLUMNS` and
`config.MEDIAN_FILL_COLUMNS`.

```python
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
```

**Critical detail:** compute the median before calling `fillna()`.
If you compute it after, and nulls have already been filled with
something else, the median is no longer representative.

---

### 6. `_parse_datetime(df, run_id, run_timestamp)`

Parses `COL_DATETIME` to `datetime64`. Attempts the primary format
first, falls back to inference if it fails, exits if both fail.

```python
def _parse_datetime(
    df: pd.DataFrame, run_id: str, run_timestamp: str
) -> pd.DataFrame:
    """
    Parse COL_DATETIME to datetime64 dtype.

    Strategy:
      1. Primary: pd.to_datetime(format=config.DATE_FORMAT)
      2. Fallback: pd.to_datetime(infer_datetime_format=True)
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
                df[config.COL_DATETIME], infer_datetime_format=True
            )
            inferred = True
        except Exception as e:
            raise SystemExit(
                f"Error: Could not parse date column '{config.COL_DATETIME}'.\n"
                f"Primary format '{config.DATE_FORMAT}' failed.\n"
                f"Inference also failed: {e}"
            )

    issue_type = "date_parse_failure" if inferred else "type_coercion"
    _append_log([{
        config.LOG_FIELD_RUN_ID:       run_id,
        config.LOG_FIELD_TIMESTAMP:    run_timestamp,
        config.LOG_FIELD_COLUMN:       config.COL_DATETIME,
        config.LOG_FIELD_ISSUE_TYPE:   issue_type,
        config.LOG_FIELD_ROW_COUNT:    0,
        config.LOG_FIELD_ACTION_TAKEN: "coerced",
    }])

    return df
```

---

### 7. `_append_log(entries)`

The only function in the pipeline that writes to disk from
`clean.py`. Appends one or more log entry dicts as CSV rows to
`logs/data_quality.log`. Creates the file with a header row if it
does not exist. Never truncates.

```python
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
```

---

### 8. Update `main.py`

Add the import and replace the Unit 2 pipeline stub comment with
the Unit 3 call. The `[CLEAN]` terminal line is printed by
`main.py` — `clean.py` prints nothing except the `[WARN]` message
if date inference fires.

**Add import:**
```python
import clean
```

**Replace the Unit 3 stub comment with:**
```python
# ── Unit 3: Cleaning ─────────────────────────────────────────────
rows_before = len(raw_df)
clean_df, run_id = clean.clean(raw_df)
rows_after = len(clean_df)
dropped = rows_before - rows_after
print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
```

**Wrap in the same error handling pattern established in Unit 2:**
```python
try:
    rows_before = len(raw_df)
    clean_df, run_id = clean.clean(raw_df)
    rows_after = len(clean_df)
    dropped = rows_before - rows_after
    print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during cleaning: {e}")
```

---

## Dependencies

- `uuid` — stdlib, no install needed. Used to generate `run_id`.
- `csv` — stdlib, no install needed. Used to write log entries.
- `datetime` — stdlib, no install needed. Used to generate
  `run_timestamp`.
- `pandas` — already installed in Unit 2. No new install needed.

No new packages are installed in this unit.

---

## Verify When Done

### Terminal Output
- [ ] `python main.py --file data/turbine.csv` prints both
      `[LOAD]` and `[CLEAN]` lines in that order
- [ ] `[CLEAN]` line format is exactly:
      `[CLEAN] N rows in → M rows clean (K dropped)`
      with comma-separated thousands on all three numbers
- [ ] No Python traceback is visible — all errors surface as
      plain-English messages

### Quality Log — Structure
- [ ] `logs/data_quality.log` exists after the first run
- [ ] First line of the file is the header:
      `run_id,run_timestamp,column,issue_type,row_count,action_taken`
- [ ] Every data row contains a non-empty value in all six fields
- [ ] `run_id` values are valid UUID4 format
      (e.g. `3f2504e0-4f89-11d3-9a0c-0305e82c3301`)
- [ ] `run_timestamp` values are valid ISO 8601 format
      (e.g. `2026-05-07T14:23:01.123456+00:00`)
- [ ] `issue_type` values are only from the allowed set:
      `duplicate`, `null`, `type_coercion`, `date_parse_failure`
- [ ] `action_taken` values are only from the allowed set:
      `dropped`, `filled_median`, `coerced`, `flagged`

### Quality Log — Append Behaviour
- [ ] Run the script twice. Open `data_quality.log` and confirm
      it contains entries from both runs (two distinct `run_id`
      values present)
- [ ] Line count after two runs is approximately double that
      after one run
- [ ] The header row appears exactly once — at line 1 — not
      repeated between runs

### Quality Log — Content
- [ ] One entry exists with `column = "row"` and
      `issue_type = "duplicate"`
- [ ] Four entries exist with `issue_type = "type_coercion"`,
      one per numeric column
- [ ] Entries exist for all five columns covering null handling
      (two `dropped` entries for critical columns, three
      `filled_median` entries for non-critical columns)
- [ ] One entry exists for `COL_DATETIME` date parsing

### DataFrame Dtypes
- [ ] After cleaning, run:
      `python -c "import pandas as pd; import ingest, clean, config;
      df,_ = clean.clean(ingest.load_csv('data/turbine.csv'));
      print(df.dtypes)"`
- [ ] `COL_DATETIME` (`Date/Time`) shows dtype `datetime64[ns]`
- [ ] All four numeric columns show dtype `float64`
- [ ] No column shows dtype `object` except none — all are
      correctly typed

### Code Standards
- [ ] `clean.py` contains no `print()` calls except inside
      `_parse_datetime` for the `[WARN]` message
- [ ] `clean.py` references no raw column name strings —
      all column references go through `config.COL_*` and
      `config.CRITICAL_COLUMNS` / `config.MEDIAN_FILL_COLUMNS`
- [ ] `python -c "import clean"` runs silently — no side effects
      on import
- [ ] Every function has a complete docstring (what, parameters,
      returns, assumptions)
- [ ] Input DataFrame is not modified in place — `df.copy()` is
      called at the top of `clean()`
- [ ] `_append_log` uses `mode="a"` — confirmed by inspecting
      the source, never `mode="w"`
