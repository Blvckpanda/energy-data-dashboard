"""
detect.py

Owns anomaly detection for operational power output.
Accepts a clean DataFrame and schema name, returns a DataFrame
containing only the flagged anomalous rows with a reason column.

Two detection methods, both schema-agnostic via SCHEMA_REGISTRY:
  1. Static threshold — value deviates > N std devs from the
     operational mean
  2. Rolling window — sustained drop in a rolling mean vs the
     overall operational mean

No files are written by this module. No side effects beyond
the [DETECT] summary line printed to the terminal.
"""

import pandas as pd
import config


def detect(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    """
    Flag anomalous rows in the primary power column.

    Filters to operational rows (primary_power > min_primary) before
    flagging, then runs both detection methods and combines results.

    Parameters:
        df (pd.DataFrame): clean DataFrame (post clean.clean())
        schema (str): "wind" or "solar" — selects primary_power_col
                      and min_primary from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: only the flagged rows, with columns:
            [datetime_col, primary_power_col, anomaly_type, deviation]
            anomaly_type is one of: 'threshold', 'rolling_window', 'both'

    Assumptions:
        - df has already passed through clean.clean() — datetime
          column is parsed, numeric columns are float64
        - Non-operational rows (zero / near-zero output) ARE excluded
          before flagging, NOT flagged as anomalies
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    primary_col = cfg["primary_power_col"]
    datetime_col = cfg["datetime_col"]
    min_primary = cfg["min_primary"]

    operational = df[df[primary_col] > min_primary].copy()
    operational = operational.sort_values(datetime_col)

    threshold_flags = _flag_threshold(operational, primary_col)
    rolling_flags = _flag_rolling(operational, datetime_col, primary_col)

    operational["_threshold"] = threshold_flags
    operational["_rolling"] = rolling_flags

    flagged = operational[operational["_threshold"] | operational["_rolling"]].copy()

    def _label(row):
        if row["_threshold"] and row["_rolling"]:
            return "both"
        elif row["_threshold"]:
            return "threshold"
        return "rolling_window"

    flagged["anomaly_type"] = flagged.apply(_label, axis=1)

    mean_val = operational[primary_col].mean()
    flagged["deviation"] = flagged[primary_col] - mean_val

    result = flagged[[datetime_col, primary_col, "anomaly_type", "deviation"]]

    threshold_count = (flagged["anomaly_type"].isin(["threshold", "both"])).sum()
    rolling_count = (flagged["anomaly_type"].isin(["rolling_window", "both"])).sum()
    print(
        f"[DETECT] {len(result):,} anomalies flagged "
        f"({threshold_count} threshold, {rolling_count} rolling window)"
    )

    return result


def _flag_threshold(operational: pd.DataFrame, primary_col: str) -> pd.Series:
    """
    Flag rows where the value deviates more than
    config.ANOMALY_STD_THRESHOLD standard deviations from the mean.

    Parameters:
        operational (pd.DataFrame): operational rows only
        primary_col (str): column to evaluate

    Returns:
        pd.Series[bool]: True where flagged. Index-aligned with the
                         input operational DataFrame.
    """
    mean_val = operational[primary_col].mean()
    std_val = operational[primary_col].std()
    threshold = config.ANOMALY_STD_THRESHOLD * std_val
    return (operational[primary_col] - mean_val).abs() > threshold


def _flag_rolling(
    operational: pd.DataFrame, datetime_col: str, primary_col: str
) -> pd.Series:
    """
    Flag rows where a rolling mean has dropped more than
    config.ANOMALY_ROLLING_DROP_PCT below the overall operational
    mean, sustained over config.ANOMALY_ROLLING_WINDOW intervals.

    Parameters:
        operational (pd.DataFrame): operational rows, sorted by
                                    datetime_col
        datetime_col (str): datetime column name (unused directly,
                            but ensures data is temporally ordered)
        primary_col (str): column to evaluate

    Returns:
        pd.Series[bool]: True where flagged. Index-aligned with the
                         input operational DataFrame.
    """
    overall_mean = operational[primary_col].mean()
    rolling_mean = (
        operational[primary_col]
        .rolling(window=config.ANOMALY_ROLLING_WINDOW, min_periods=1)
        .mean()
    )
    drop_threshold = overall_mean * (1 - config.ANOMALY_ROLLING_DROP_PCT)
    return rolling_mean < drop_threshold
