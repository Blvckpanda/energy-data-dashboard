"""Sanity checks on the schema registry structure itself."""

import config

REQUIRED_KEYS = {
    "required_columns", "datetime_col", "date_format",
    "critical_columns", "median_fill_columns", "primary_power_col",
    "secondary_col", "reference_col", "ratio_name",
    "min_primary", "min_reference",
}


def test_both_schemas_present():
    assert "wind" in config.SCHEMA_REGISTRY
    assert "solar" in config.SCHEMA_REGISTRY


def test_wind_schema_has_all_required_keys():
    assert REQUIRED_KEYS.issubset(config.SCHEMA_REGISTRY["wind"].keys())


def test_solar_schema_has_all_required_keys():
    assert REQUIRED_KEYS.issubset(config.SCHEMA_REGISTRY["solar"].keys())


def test_anomaly_constants_exist():
    assert hasattr(config, "ANOMALY_STD_THRESHOLD")
    assert hasattr(config, "ANOMALY_ROLLING_WINDOW")
    assert hasattr(config, "ANOMALY_ROLLING_DROP_PCT")
    assert 0 < config.ANOMALY_ROLLING_DROP_PCT < 1
