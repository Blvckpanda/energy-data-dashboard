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