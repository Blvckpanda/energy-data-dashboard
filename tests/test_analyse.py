"""
test_analyse.py

Tests for analyse.py — stats, efficiency, resampling, distribution,
and the daily_mean result used by the anomaly timeline chart.
"""

import pandas as pd

import analyse
import clean
import config


def test_efficiency_excludes_zero_theoretical(wind_df):
    df = wind_df.copy()
    df.loc[0, config.COL_THEORETICAL] = 0
    clean_df, _ = clean.clean(df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert (results["efficiency"][config.COL_THEORETICAL] > 0).all()


def test_monthly_has_datetime_index(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert results["monthly"].index.dtype.kind == "M"


def test_daily_mean_has_datetime_index(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert results["daily_mean"].index.dtype.kind == "M"


def test_daily_mean_values_are_daily_means(wind_df):
    """daily_mean equals the mean of raw rows per day — not their sum."""
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")

    daily_mean = results["daily_mean"][config.COL_ACTIVE_POWER]
    expected = clean_df.set_index(config.COL_DATETIME)[
        config.COL_ACTIVE_POWER
    ].resample("D").mean()

    assert list(daily_mean.values) == list(expected.values)


def test_daily_mean_magnitude_matches_raw_rows(wind_df):
    """Anomaly points and the timeline line must share units: the daily
    mean must be far smaller than the daily total for a multi-row day."""
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")

    total = results["daily"][config.COL_ACTIVE_POWER].iloc[0]
    mean = results["daily_mean"][config.COL_ACTIVE_POWER].iloc[0]
    assert mean < total


def test_analyse_does_not_mutate_input(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    before = clean_df.copy()
    analyse.analyse(clean_df, schema="wind")
    pd.testing.assert_frame_equal(clean_df, before)


def test_wind_distribution_shape(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert len(results["distribution"]) <= config.WIND_DIRECTION_BINS


def test_solar_distribution_by_source_key(solar_df):
    clean_df, _ = clean.clean(solar_df, schema="solar")
    results = analyse.analyse(clean_df, schema="solar")
    assert "mean" in results["distribution"].columns
    assert "count" in results["distribution"].columns


def test_solar_efficiency_uses_conversion_ratio(solar_df):
    clean_df, _ = clean.clean(solar_df, schema="solar")
    results = analyse.analyse(clean_df, schema="solar")
    assert "conversion_ratio" in results["efficiency"].columns


def test_efficiency_columns_order_and_dedup(wind_df, solar_df):
    """analyse owns the efficiency column order. Order-preserving dedup:
    solar's secondary == reference collapses five selections to four.
    The produced efficiency frames follow the owned list exactly."""
    assert analyse.efficiency_columns(config.SCHEMA_REGISTRY["wind"]) == [
        config.COL_DATETIME, config.COL_ACTIVE_POWER, config.COL_WIND_SPEED,
        config.COL_THEORETICAL, "efficiency_ratio",
    ]
    assert analyse.efficiency_columns(config.SCHEMA_REGISTRY["solar"]) == [
        config.COL_SOLAR_DATETIME, config.COL_AC_POWER, config.COL_DC_POWER,
        "conversion_ratio",
    ]

    for df, schema in ((wind_df, "wind"), (solar_df, "solar")):
        clean_df, _ = clean.clean(df, schema=schema)
        results = analyse.analyse(clean_df, schema=schema)
        assert list(results["efficiency"].columns) == analyse.efficiency_columns(
            config.SCHEMA_REGISTRY[schema]
        )
