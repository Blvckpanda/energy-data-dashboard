"""
analyse.py

Owns all analytical computations for the pipeline.
Accepts a clean DataFrame from clean.py and returns a named dict
of result DataFrames covering summary statistics, power curve
efficiency, time-series aggregations, and distribution analysis.
Schemas whose registry entry sets power_curve_bin_width additionally
get a measured power curve on IEC 61400-12-1-style fixed-width bins.

Schema-aware: column names, ratios, and the distribution analysis
come from config.SCHEMA_REGISTRY. Dispatch keys off registry values
(never schema names), so a new schema needs only a registry entry.

No files are written by this module. No output is produced.
All results are returned in memory for use by visualise.py
and export.py.
"""

import math

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
            'power_curve'  — measured power curve on IEC 61400-12-1-
                             style bins (only when the schema's
                             registry entry sets power_curve_bin_width)

    Assumptions:
        - datetime column is dtype datetime64 (required for resampling)
        - All numeric columns are dtype float64
        - Input DataFrame is not modified in place
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    results = {
        "stats":        _compute_stats(df, cfg),
        "efficiency":   _compute_efficiency(df, cfg),
        "monthly":      _compute_monthly(df, cfg),
        "daily":        _compute_daily(df, cfg),
        "daily_mean":   _compute_daily_mean(df, cfg),
        "distribution": _compute_distribution(df, cfg),
    }
    # Registry-driven: a schema opts into the measured power curve by
    # declaring a bin width — no schema-name branch here.
    if "power_curve_bin_width" in cfg:
        results["power_curve"] = _compute_power_curve(df, cfg)
    return results


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


def efficiency_columns(cfg: dict) -> list[str]:
    """
    Return the efficiency DataFrame's column order for a schema.

    Single owner of that order: _compute_efficiency selects these
    columns, and export._efficiency_headers derives the Efficiency
    Analysis sheet's header row from the same list — so the sheet can
    never drift out of step with the analysis. The registry key order
    is the contract: datetime, primary output, secondary metric,
    reference, then the ratio itself.

    Deduplication preserves order (handles solar, where secondary_col
    == reference_col: five selections collapse to four columns).

    Parameters:
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        list[str]: unique column names in report order
    """
    select_cols = [
        cfg["datetime_col"], cfg["primary_power_col"],
        cfg["secondary_col"], cfg["reference_col"], cfg["ratio_name"],
    ]
    seen: set[str] = set()
    unique_cols: list[str] = []
    for col in select_cols:
        if col not in seen:
            seen.add(col)
            unique_cols.append(col)
    return unique_cols


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

    return operational[efficiency_columns(cfg)]


def _compute_power_curve(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Build the measured power curve on IEC 61400-12-1-style bins.

    Operational readings (the same exclusion rule _compute_efficiency
    applies) are grouped into fixed-width bins of the secondary column
    — the wind speed, binned at 0.5 m/s per the standard's convention
    — and each bin's mean output forms the measured curve.

    Deviations from a full IEC 61400-12-1 measurement campaign are
    disclosed rather than hidden: the source is pre-aggregated SCADA
    data (10-minute rows), not raw sampled signals; the operational
    filter replaces the standard's full data-validation criteria; and
    no per-bin uncertainty quantification is attempted. The
    'sufficient' column flags bins with at least
    power_curve_min_samples samples — three 10-minute rows approximate
    the 30 minutes of data the standard expects per bin.

    Parameters:
        df (pd.DataFrame): clean SCADA DataFrame
        cfg (dict): schema config; needs power_curve_bin_width and
                    power_curve_min_samples

    Returns:
        pd.DataFrame: one row per non-empty bin, indexed by the
                      bin interval ({secondary_col}_bin), with columns
                      mean_secondary, mean_primary, mean_reference,
                      count (int64), sufficient (bool)
    """
    bin_width = cfg["power_curve_bin_width"]
    min_samples = cfg["power_curve_min_samples"]
    secondary = cfg["secondary_col"]

    # Same operational-row exclusion _compute_efficiency applies, so
    # every analysis surface describes the same rows
    operational = df[
        (df[cfg["reference_col"]] > cfg["min_reference"]) &
        (df[cfg["primary_power_col"]] > cfg["min_primary"])
    ]

    if operational.empty:
        print("[ANALYSE] Measured power curve: no operational rows to bin")
        return pd.DataFrame(
            columns=["mean_secondary", "mean_primary",
                     "mean_reference", "count", "sufficient"],
        )

    # Left-closed bins [v, v+width) from 0, with one spare edge at the
    # top so the maximum reading always lands inside the last bin
    top_edge = math.ceil(operational[secondary].max() / bin_width) + 1
    edges = [i * bin_width for i in range(top_edge + 1)]

    binned = pd.cut(operational[secondary], bins=edges, right=False)
    curve = operational.groupby(binned, observed=False).agg(
        mean_secondary=(secondary, "mean"),
        mean_primary=(cfg["primary_power_col"], "mean"),
        mean_reference=(cfg["reference_col"], "mean"),
        count=(secondary, "size"),
    )
    curve = curve[curve["count"] > 0]
    curve.index.name = f"{secondary}_bin"
    curve["sufficient"] = curve["count"] >= min_samples

    sufficient = int(curve["sufficient"].sum())
    print(
        f"[ANALYSE] Measured power curve: {len(curve)} bins of "
        f"{bin_width:g} {cfg['secondary_label'].split()[-1]}; "
        f"{sufficient} meet the data-sufficiency minimum "
        f"({min_samples}+ samples)"
    )
    return curve


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
