"""Tests for analyse.py — stats, efficiency, resampling, distribution."""

import config
import clean
import analyse


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
