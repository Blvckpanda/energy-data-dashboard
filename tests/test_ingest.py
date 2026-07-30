"""Tests for ingest.py — schema validation."""

import pytest
import ingest


def test_validate_schema_wind_passes(wind_df):
    """A valid wind DataFrame passes validation without raising."""
    ingest.validate_schema(wind_df, schema="wind")  # should not raise


def test_validate_schema_solar_passes(solar_df):
    """A valid solar DataFrame passes validation without raising."""
    ingest.validate_schema(solar_df, schema="solar")  # should not raise


def test_validate_schema_missing_column_raises(wind_df):
    """Removing a required column triggers SystemExit with a clear message."""
    broken = wind_df.drop(columns=["Wind Speed (m/s)"])
    with pytest.raises(SystemExit) as exc_info:
        ingest.validate_schema(broken, schema="wind")
    assert "Wind Speed (m/s)" in str(exc_info.value)


def test_validate_schema_wrong_schema_flags_all_missing(solar_df):
    """A solar DataFrame validated against the wind schema fails clearly."""
    with pytest.raises(SystemExit):
        ingest.validate_schema(solar_df, schema="wind")
