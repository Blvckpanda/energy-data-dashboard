"""
analyse.py

Owns all analytical computations for the pipeline.
Accepts a clean DataFrame from clean.py and returns a named dict
of result DataFrames covering summary statistics, power curve
efficiency, time-series aggregations, and distribution analysis.

Schema-aware: column names, ratios, and the distribution analysis
come from config.SCHEMA_REGISTRY. Dispatch keys off registry values
(never schema names), so a new schema needs only a registry entry.

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
        schema (str): a schema name from config.SCHEMA_REGISTRY —
                      selects column config from
                      config.SCHEMA_REGISTRY

    Returns:
        dict[str, pd.DataFrame]: named results with keys:
            'stats'        — summary statistics
            'efficiency'   — per-row efficiency/conversion ratio
            'monthly'      — monthly mean primary power
            'daily'        — daily total primary power
            'daily_mean'   — daily mean primary power (anomaly
                             timeline baseline, same units as the
                             raw rows plotted over it)
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
        "daily":        _compute_daily(df, cfg),            "daily_mean":   _compute_daily_mean(df, cfg),
            "distribution": _compute_distribution(df, cfg),
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

    The ratio is primary_power_col / reference_col, with the column
    choice and exclusion thresholds coming from the schema registry.

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


def _compute_daily_mean(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Resample primary power to daily mean.

    Mirrors _compute_monthly at day frequency. The anomaly timeline
    chart plots this series instead of daily totals so instantaneous
    anomaly points share the same units and magnitude as the line
    they are drawn over.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame with datetime64
                           datetime column
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: daily mean primary power.
                      DatetimeIndex at day frequency ('D').
    """
    return (
        df.set_index(cfg["datetime_col"])[cfg["primary_power_col"]]
        .resample("D")
        .mean()
        .to_frame()
    )


def _compute_distribution(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Compute the schema's distribution analysis, dispatched on the
    registry's distribution kind — not on the schema name.

    Kinds:
        "bins"       — frequency count of a numeric column across
                       fixed bin edges (e.g. wind-direction compass
                       segments, hydro flow-rate bands)
        "group_mean" — mean and count of one value column grouped by
                       another (e.g. AC power per inverter)

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: distribution results
    """
    spec = cfg["distribution"]
    if spec["kind"] == "bins":
        return _compute_binned_distribution(df, spec)
    return _compute_group_mean_distribution(df, spec)


def _compute_binned_distribution(
    df: pd.DataFrame, spec: dict
) -> pd.DataFrame:
    """
    Frequency count of a numeric column across fixed bins.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        spec (dict): distribution spec with 'col' and 'bins' keys

    Returns:
        pd.DataFrame: frequency count per bin.
                      Index: bin interval labels.
                      Column: 'count' (int64).
                      One row per bin.
    """
    bins = pd.cut(
        df[spec["col"]],
        bins=spec["bins"],
        right=True,
    )
    result = bins.value_counts(sort=False).to_frame(name="count")
    result.index.name = f"{spec['col']}_bin"
    return result


def _compute_group_mean_distribution(
    df: pd.DataFrame, spec: dict
) -> pd.DataFrame:
    """
    Mean and count of a value column per group of a grouping column.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        spec (dict): distribution spec with 'group_col' and
                     'value_col' keys

    Returns:
        pd.DataFrame: index=group values, columns=['mean', 'count']
    """
    return (
        df.groupby(spec["group_col"])[spec["value_col"]]
        .agg(["mean", "count"])
    )
