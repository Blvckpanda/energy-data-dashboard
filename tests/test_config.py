"""Sanity checks on the schema registry structure itself."""

import config

REQUIRED_KEYS = {
    "required_columns", "datetime_col", "date_format",
    "critical_columns", "median_fill_columns", "primary_power_col",
    "secondary_col", "reference_col", "ratio_name",
    "min_primary", "min_reference",
    "primary_label", "secondary_label", "ratio_label",
    "asset_label", "display_names", "interval_minutes",
    "scatter_reference", "distribution",
}


def test_all_schemas_present():
    assert set(config.SCHEMA_REGISTRY.keys()) == {"wind", "solar", "hydro"}


def test_every_schema_has_all_required_keys():
    for name, cfg in config.SCHEMA_REGISTRY.items():
        missing = REQUIRED_KEYS - set(cfg.keys())
        assert not missing, f"{name} schema missing keys: {missing}"


def test_display_names_cover_all_required_columns():
    """Every required CSV column has a plain-English display name."""
    for name, cfg in config.SCHEMA_REGISTRY.items():
        for col in cfg["required_columns"]:
            assert col in cfg["display_names"], (
                f"{name}: no display name for required column {col!r}"
            )


def test_scatter_reference_kind_is_valid():
    for name, cfg in config.SCHEMA_REGISTRY.items():
        assert cfg["scatter_reference"] in {"column", "identity"}, name


def test_distribution_spec_is_well_formed():
    for name, cfg in config.SCHEMA_REGISTRY.items():
        spec = cfg["distribution"]
        if spec["kind"] == "bins":
            assert spec["col"] in cfg["required_columns"], name
            assert int(spec["bins"]) > 0, name
        elif spec["kind"] == "group_mean":
            assert spec["group_col"] in cfg["required_columns"], name
            assert spec["value_col"] in cfg["required_columns"], name
        else:
            raise AssertionError(f"{name}: unknown distribution kind {spec['kind']!r}")


def test_interval_minutes_are_positive():
    for name, cfg in config.SCHEMA_REGISTRY.items():
        assert isinstance(cfg["interval_minutes"], int)
        assert cfg["interval_minutes"] > 0, name


def test_anomaly_constants_exist():
    assert hasattr(config, "ANOMALY_STD_THRESHOLD")
    assert hasattr(config, "ANOMALY_ROLLING_WINDOW")
    assert hasattr(config, "ANOMALY_ROLLING_DROP_PCT")
    assert 0 < config.ANOMALY_ROLLING_DROP_PCT < 1
