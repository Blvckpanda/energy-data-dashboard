"""Tests for detect.py — threshold and rolling-window anomaly detection."""

import config
import clean
import detect


def test_threshold_flags_extreme_outlier(wind_df):
    df = wind_df.copy()
    df.loc[10, config.COL_ACTIVE_POWER] = 10_000.0  # extreme spike
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert "threshold" in anomalies["anomaly_type"].values or \
           "both" in anomalies["anomaly_type"].values


def test_rolling_window_flags_sustained_drop(wind_df):
    df = wind_df.copy()
    # Drop a sustained block of values well below the mean
    df.loc[5:15, config.COL_ACTIVE_POWER] = 1.0
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert len(anomalies) > 0


def test_detect_excludes_non_operational_rows(wind_df):
    """Rows at or below min_primary are never flagged as anomalies."""
    df = wind_df.copy()
    df.loc[0, config.COL_ACTIVE_POWER] = 0.0
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert 0.0 not in anomalies[config.COL_ACTIVE_POWER].values


def test_detect_empty_result_does_not_crash(wind_df):
    """A dataset with no anomalies returns an empty DataFrame, no error."""
    clean_df, _ = clean.clean(wind_df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert anomalies is not None  # empty is fine, None is not
