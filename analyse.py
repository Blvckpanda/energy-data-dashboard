"""
analyse.py

Owns all analytical computations for the pipeline.
Accepts a clean DataFrame from clean.py and returns a named dict
of result DataFrames covering summary statistics, power curve
efficiency, time-series aggregations, and distribution analysis.

Schema-aware: column names and ratios come from
config.SCHEMA_REGISTRY. No schema-specific branching except in
_compute_distribution, where the analysis method differs in kind
between wind (direction bins) and solar (source-key aggregation).

No files are written by this module. No output is produced.
All results are returned in memory for use by visualise.py
and export.py.
"""

import pandas as pd
import config


def analyse(df: pd.DataFrame, schema: str) -> dict[str, pd.DataFrame]:
    """
    Run all analytical computations on a clean SCADA DataFrame.

    Parameters:
        df (pd.DataFrame): clean DataFrame from clean.clean().
                           Must have datetime64 dtype on the datetime
                           column and float64 on all numeric columns.
        schema (str): "wind" or "solar" — selects column config from
                      config.SCHEMA_REGISTRY

    Returns:
        dict[str, pd.DataFrame]: named results with keys:
            'stats'        — summary statistics
            'efficiency'   — per-row efficiency/conversion ratio
            'monthly'      — monthly mean primary power
            'daily'        — daily total primary power
            'distribution' — schema-specific distribution analysis

    Assumptions:
        - datetime column is dtype datetime64 (required for resampling)
        - All numeric columns are dtype float64
        - Input DataFrame is not modified in place
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    return {
        "stats":        _compute_stats(df, cfg),
        "efficiency":   _compute_efficiency(df, cfg),
        "monthly":      _compute_monthly(df, cfg),
        "daily":        _compute_daily(df, cfg),
        "distribution": _compute_distribution(df, schema),
    }


def _compute_stats(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Compute descriptive statistics for primary and secondary columns.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: describe() output for the primary and secondary
                      columns. Index is statistic name.
    """
    return df[[cfg["primary_power_col"], cfg["secondary_col"]]].describe()


def _compute_efficiency(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Compute per-row efficiency or conversion ratio.

    Wind: efficiency_ratio = active_power / theoretical_power
    Solar: conversion_ratio = AC_POWER / DC_POWER

    Non-operational rows (reference <= min_reference or
    primary <= min_primary) are excluded before calculation.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: operational rows only, with an additional
                      ratio column named per cfg['ratio_name'].
    """
    total_rows = len(df)

    operational = df[
        (df[cfg["reference_col"]] > cfg["min_reference"]) &
        (df[cfg["primary_power_col"]] > cfg["min_primary"])
    ].copy()

    excluded = total_rows - len(operational)
    print(
        f"[ANALYSE] {excluded:,} rows excluded from {cfg['ratio_name']} "
        f"(zero reference or non-positive output)"
    )

    operational[cfg["ratio_name"]] = (
        operational[cfg["primary_power_col"]] /
        operational[cfg["reference_col"]]
    )

    select_cols = [
        cfg["datetime_col"], cfg["primary_power_col"],
        cfg["secondary_col"], cfg["reference_col"], cfg["ratio_name"],
    ]
    # Deduplicate while preserving order (handles solar where
    # secondary_col == reference_col)
    seen: set[str] = set()
    unique_cols: list[str] = []
    for c in select_cols:
        if c not in seen:
            seen.add(c)
            unique_cols.append(c)

    return operational[unique_cols]


def _compute_monthly(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Resample primary power to monthly mean.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with datetime64
                           datetime column
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: monthly mean primary power.
                      DatetimeIndex at month-start frequency ('MS').
    """
    return (
        df.set_index(cfg["datetime_col"])[cfg["primary_power_col"]]
        .resample("MS")
        .mean()
        .to_frame()
    )


def _compute_daily(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Resample primary power to daily total.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with datetime64
                           datetime column
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: daily total primary power.
                      DatetimeIndex at day frequency ('D').
    """
    return (
        df.set_index(cfg["datetime_col"])[cfg["primary_power_col"]]
        .resample("D")
        .sum()
        .to_frame()
    )


def _compute_distribution(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    """
    Compute schema-specific distribution analysis.

    Wind: wind direction frequency across 16 compass bins.
    Solar: mean and count of AC_POWER per inverter (SOURCE_KEY).

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        schema (str): "wind" or "solar"

    Returns:
        pd.DataFrame: distribution results
    """
    if schema == "wind":
        return _compute_wind_bins(df)
    elif schema == "solar":
        return _compute_source_key_distribution(df)


def _compute_wind_bins(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bin wind direction into 16 compass segments and count frequency.

    Bins are 22.5° wide, covering 0–360° (16 bins total),
    as defined by config.WIND_DIRECTION_BINS.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame

    Returns:
        pd.DataFrame: frequency count per wind direction bin.
                      Index: bin interval labels.
                      Column: 'count' (int64).
                      Exactly 16 rows.
    """
    bins = pd.cut(
        df[config.COL_WIND_DIRECTION],
        bins=config.WIND_DIRECTION_BINS,
        right=True,
    )
    result = bins.value_counts(sort=False).to_frame(name="count")
    result.index.name = "wind_direction_bin"
    return result


def _compute_source_key_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mean and count of AC_POWER per inverter (SOURCE_KEY).

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with COL_SOURCE_KEY
                           and COL_AC_POWER columns

    Returns:
        pd.DataFrame: index=SOURCE_KEY, columns=['mean', 'count']
    """
    return (
        df.groupby(config.COL_SOURCE_KEY)[config.COL_AC_POWER]
        .agg(["mean", "count"])
    )
