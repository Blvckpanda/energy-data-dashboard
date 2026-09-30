# Unit 04: Analysis + Printed Preview

## Goal

Implement `analyse.py` to produce five named result DataFrames —
`stats`, `efficiency`, `monthly`, `daily`, and `wind_bins` — from
the clean DataFrame, and update `main.py` to call it and print a
5-row terminal preview of each result so every output is immediately
verifiable without export needing to exist yet.

---

## Implementation

### 1. Module Structure

`analyse.py` owns one responsibility: computing all analytical
results from the clean DataFrame. It returns a single dict of named
DataFrames. It does not touch files, does not print anything, and
does not know that Excel or charts exist.

```python
"""
analyse.py

Owns all analytical computations for the pipeline.
Accepts a clean DataFrame from clean.py and returns a named dict
of result DataFrames covering summary statistics, power curve
efficiency, time-series aggregations, and wind direction distribution.

No files are written by this module. No output is produced.
All results are returned in memory for use by visualise.py
and export.py.
"""

import pandas as pd
import config


def analyse(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ...

# Internal helpers
def _compute_stats(df): ...
def _compute_efficiency(df): ...
def _compute_monthly(df): ...
def _compute_daily(df): ...
def _compute_wind_bins(df): ...
```

---

### 2. `analyse(df)` — Public Entry Point

The single function `main.py` calls. Passes the clean DataFrame to
each internal helper in sequence, assembles all results into a named
dict, and returns it.

```python
def analyse(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Run all analytical computations on a clean SCADA DataFrame.

    Parameters:
        df (pd.DataFrame): clean DataFrame from clean.clean().
                           Must have datetime64 dtype on COL_DATETIME
                           and float64 on all four numeric columns.

    Returns:
        dict[str, pd.DataFrame]: named results with keys:
            'stats'      — summary statistics for power and wind speed
            'efficiency' — per-row efficiency ratio (operational rows only)
            'monthly'    — monthly mean active power
            'daily'      — daily total active power
            'wind_bins'  — wind direction frequency across 16 bins

    Assumptions:
        - COL_DATETIME is dtype datetime64 (required for resampling)
        - All numeric columns are dtype float64
        - Input DataFrame is not modified in place
    """
    return {
        "stats":      _compute_stats(df),
        "efficiency": _compute_efficiency(df),
        "monthly":    _compute_monthly(df),
        "daily":      _compute_daily(df),
        "wind_bins":  _compute_wind_bins(df),
    }
```

---

### 3. `_compute_stats(df)`

Computes descriptive statistics for `COL_ACTIVE_POWER` and
`COL_WIND_SPEED` using `describe()`. Returns a DataFrame with
both columns as its columns and statistics (count, mean, std,
min, 25%, 50%, 75%, max) as its index rows.

```python
def _compute_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute descriptive statistics for active power and wind speed.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame

    Returns:
        pd.DataFrame: describe() output for COL_ACTIVE_POWER and
                      COL_WIND_SPEED. Index is statistic name
                      (count, mean, std, min, 25%, 50%, 75%, max).
                      Columns are the two metric names.

    Assumptions:
        - Both columns are float64
    """
    return df[[config.COL_ACTIVE_POWER, config.COL_WIND_SPEED]].describe()
```

---

### 4. `_compute_efficiency(df)`

Computes a per-row efficiency ratio: actual output divided by
theoretical maximum. Before any computation, filters the DataFrame
to operational rows only. Logs the excluded row count to the
terminal.

**Filtering rule (from architecture.md Invariant 8):**
Exclude all rows where `COL_THEORETICAL == 0` OR
`COL_ACTIVE_POWER <= 0`. These are non-operational periods.
Do not fill or replace — exclude entirely.

**Ratio formula:**
`efficiency_ratio = COL_ACTIVE_POWER / COL_THEORETICAL`

This produces a value between 0 and 1 for normal operation
(values above 1 are possible and valid — they indicate output
exceeding the theoretical model).

```python
def _compute_efficiency(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-row efficiency ratio for operational periods only.

    Efficiency = COL_ACTIVE_POWER / COL_THEORETICAL_POWER_CURVE.

    Non-operational rows (zero theoretical or non-positive output)
    are excluded before calculation. The excluded count is printed
    to the terminal.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame

    Returns:
        pd.DataFrame: operational rows only, with an additional
                      'efficiency_ratio' column (float64).
                      Contains COL_DATETIME, COL_ACTIVE_POWER,
                      COL_WIND_SPEED, COL_THEORETICAL, and
                      'efficiency_ratio'.

    Assumptions:
        - COL_THEORETICAL and COL_ACTIVE_POWER are float64
        - Division by zero is impossible because COL_THEORETICAL == 0
          rows are excluded before division
    """
    total_rows = len(df)

    operational = df[
        (df[config.COL_THEORETICAL] > config.EFFICIENCY_MIN_THEORETICAL) &
        (df[config.COL_ACTIVE_POWER] > config.EFFICIENCY_MIN_ACTIVE_POWER)
    ].copy()

    excluded = total_rows - len(operational)
    print(
        f"[ANALYSE] {excluded:,} rows excluded from efficiency "
        f"(zero theoretical or non-positive output)"
    )

    operational["efficiency_ratio"] = (
        operational[config.COL_ACTIVE_POWER] /
        operational[config.COL_THEORETICAL]
    )

    return operational[[
        config.COL_DATETIME,
        config.COL_ACTIVE_POWER,
        config.COL_WIND_SPEED,
        config.COL_THEORETICAL,
        "efficiency_ratio",
    ]]
```

Note: `_compute_efficiency` is the **only** internal helper
permitted to print to the terminal — because the excluded row
count is defined in `code-standards.md` as a required terminal
output, and it is logically inseparable from the computation.

---

### 5. `_compute_monthly(df)`

Resamples `COL_ACTIVE_POWER` to monthly frequency and computes
the mean for each month. Requires `COL_DATETIME` to be the
DataFrame index for `resample()` to work.

```python
def _compute_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample active power to monthly mean.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with datetime64
                           COL_DATETIME column

    Returns:
        pd.DataFrame: monthly mean COL_ACTIVE_POWER.
                      DatetimeIndex at month-start frequency ('MS').
                      Single column: COL_ACTIVE_POWER.
                      One row per calendar month present in the data.

    Assumptions:
        - COL_DATETIME is dtype datetime64
        - Data spans at least one full calendar month
    """
    return (
        df.set_index(config.COL_DATETIME)[config.COL_ACTIVE_POWER]
        .resample("MS")
        .mean()
        .to_frame()
    )
```

Use `"MS"` (month start) not `"M"` (month end) — month start
produces cleaner date labels (e.g. `2018-01-01` vs `2018-01-31`)
which read better in charts and the Excel report.

---

### 6. `_compute_daily(df)`

Resamples `COL_ACTIVE_POWER` to daily frequency and computes the
total (sum) for each day.

```python
def _compute_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample active power to daily total.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with datetime64
                           COL_DATETIME column

    Returns:
        pd.DataFrame: daily total COL_ACTIVE_POWER.
                      DatetimeIndex at day frequency ('D').
                      Single column: COL_ACTIVE_POWER.
                      One row per calendar day present in the data.

    Assumptions:
        - COL_DATETIME is dtype datetime64
        - Data is recorded at 10-minute intervals (144 readings/day)
    """
    return (
        df.set_index(config.COL_DATETIME)[config.COL_ACTIVE_POWER]
        .resample("D")
        .sum()
        .to_frame()
    )
```

Monthly uses `.mean()` (average power output per month).
Daily uses `.sum()` (total energy produced per day). These are
different aggregations for a reason — monthly mean is better for
trend comparison, daily total is better for energy yield charts.

---

### 7. `_compute_wind_bins(df)`

Bins `COL_WIND_DIRECTION` into 16 compass segments of 22.5°
each, covering 0–360°. Returns a frequency count per bin.

```python
def _compute_wind_bins(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bin wind direction into 16 compass segments and count frequency.

    Bins are 22.5° wide, covering 0–360° (16 bins total),
    as defined by config.WIND_DIRECTION_BINS.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame

    Returns:
        pd.DataFrame: frequency count per wind direction bin.
                      Index: bin interval labels
                        (e.g. (0.0, 22.5], (22.5, 45.0], ...)
                      Column: 'count' (int64)
                      Exactly 16 rows.

    Assumptions:
        - COL_WIND_DIRECTION values are in range 0–360 degrees
        - config.WIND_DIRECTION_BINS == 16
    """
    bins = pd.cut(
        df[config.COL_WIND_DIRECTION],
        bins=config.WIND_DIRECTION_BINS,
        right=True,
    )
    result = bins.value_counts(sort=False).to_frame(name="count")
    result.index.name = "wind_direction_bin"
    return result
```

`sort=False` preserves the natural bin order (0→360) rather than
sorting by frequency — essential for wind direction, which is
directional not ranked data.

---

### 8. Update `main.py`

Add the import, call `analyse()`, print the `[ANALYSE]` marker,
and print a 5-row preview of every result key. All printing lives
in `main.py` — `analyse.py` prints nothing except the efficiency
exclusion line inside `_compute_efficiency`.

**Add import:**
```python
import analyse
```

**Add after the `[CLEAN]` block:**
```python
# ── Unit 4: Analysis ─────────────────────────────────────────────
try:
    results = analyse.analyse(clean_df)
    print("[ANALYSE]")
    for key, result_df in results.items():
        print(f"\n--- {key} ({len(result_df)} rows) ---")
        print(result_df.head())
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during analysis: {e}")
```

**Terminal output will look like:**
```
[ANALYSE] 43,226 rows excluded from efficiency (zero theoretical or non-positive output)
[ANALYSE]

--- stats (8 rows) ---
       LV ActivePower (kW)  Wind Speed (m/s)
count         52608.000000      52608.000000
mean           1154.256781          7.843022
...

--- efficiency (49382 rows) ---
            Date/Time  LV ActivePower (kW)  ...  efficiency_ratio
0  2018-01-01 00:00:00          380.047791  ...          0.312847
...
```

---

## Dependencies

- `pandas` — already installed in Unit 2. No new install needed.

No new packages are installed in this unit.

---

## Verify When Done

### Terminal Output
- [ ] Running `python main.py --file data/turbine.csv` prints
      `[LOAD]`, `[CLEAN]`, the efficiency exclusion line, and
      `[ANALYSE]` in that order with no errors
- [ ] The efficiency exclusion line format is exactly:
      `[ANALYSE] N rows excluded from efficiency (zero theoretical or non-positive output)`
- [ ] Five preview blocks appear after `[ANALYSE]`, one per key,
      each labelled `--- key (N rows) ---` followed by 5 rows

### `stats` Result
- [ ] `stats` has exactly 8 rows (count, mean, std, min, 25%,
      50%, 75%, max)
- [ ] `stats` has exactly 2 columns: `COL_ACTIVE_POWER` and
      `COL_WIND_SPEED`
- [ ] `stats` mean for `COL_ACTIVE_POWER` is a plausible turbine
      output value — spot-check against the raw CSV mean

### `efficiency` Result
- [ ] `efficiency` contains a column named `efficiency_ratio`
- [ ] `efficiency` contains exactly 5 columns: `COL_DATETIME`,
      `COL_ACTIVE_POWER`, `COL_WIND_SPEED`, `COL_THEORETICAL`,
      `efficiency_ratio`
- [ ] No row in `efficiency` has `COL_THEORETICAL == 0` —
      verify: `assert (efficiency_df[config.COL_THEORETICAL] > 0).all()`
- [ ] No row in `efficiency` has `COL_ACTIVE_POWER <= 0` —
      verify: `assert (efficiency_df[config.COL_ACTIVE_POWER] > 0).all()`
- [ ] `efficiency_ratio` values are all positive floats —
      spot-check 3 rows manually: ratio = active / theoretical

### `monthly` Result
- [ ] `monthly` has a `DatetimeIndex` (not an integer index)
- [ ] `monthly` has exactly 1 column: `COL_ACTIVE_POWER`
- [ ] Row count equals the number of distinct calendar months
      in the dataset — verify by checking min and max dates
- [ ] Index frequency is month-start (`MS`) — first index value
      ends in `-01` (e.g. `2018-01-01`)
- [ ] Monthly mean values are plausible — spot-check January
      mean against manually filtered raw CSV

### `daily` Result
- [ ] `daily` has a `DatetimeIndex`
- [ ] `daily` has exactly 1 column: `COL_ACTIVE_POWER`
- [ ] Row count equals the number of distinct calendar days
      in the dataset
- [ ] Daily totals are plausible — a full day at 144 readings
      of ~1,154 kW mean should total roughly ~166,000 kW

### `wind_bins` Result
- [ ] `wind_bins` has exactly 16 rows
- [ ] `wind_bins` has exactly 1 column named `count`
- [ ] `wind_bins` index name is `wind_direction_bin`
- [ ] Sum of all `count` values equals the total row count of
      the clean DataFrame (every row is binned exactly once)
- [ ] Bins are in ascending order (0→360), not sorted by frequency

### Code Standards
- [ ] `analyse.py` contains exactly one `print()` call — inside
      `_compute_efficiency` for the exclusion count line
- [ ] No raw column name strings appear in `analyse.py` — all
      references go through `config.COL_*` constants
- [ ] `python -c "import analyse"` runs silently — no side
      effects on import
- [ ] All six functions have complete docstrings (what,
      parameters, returns, assumptions)
- [ ] Input DataFrame is never modified in place — `.copy()` is
      called inside `_compute_efficiency` before adding the
      `efficiency_ratio` column
- [ ] `analyse.py` does not import `ingest`, `clean`, `export`,
      or `visualise` — lateral imports are forbidden
