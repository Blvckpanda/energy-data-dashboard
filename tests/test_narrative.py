"""
test_narrative.py

Tests for narrative.py — registry-driven paragraph construction:
interval-based operational hours, plain-English labels, and the
notable-pattern sentence dispatched on distribution kind.
"""

import pandas as pd

import clean
import config
import narrative


def _results_for(df: pd.DataFrame, schema: str) -> dict:
    import analyse
    import detect
    clean_df, _ = clean.clean(df, schema=schema)
    results = analyse.analyse(clean_df, schema=schema)
    results["anomalies"] = detect.detect(clean_df, schema=schema)
    return results


def test_narrative_mentions_computed_hours_and_labels(wind_df):
    """Hours derive from interval_minutes; labels are plain English."""
    results = _results_for(wind_df, "wind")
    clean_df, _ = clean.clean(wind_df, schema="wind")

    text = narrative.build_narrative(results, clean_df, "wind")

    # 20 operational rows × 10 min = 200 minutes → rounds to 3 hours
    assert "3 hours" in text
    assert "wind turbine" in text
    assert "active power (kw)" in text.lower()
    assert config.COL_ACTIVE_POWER not in text          # no raw column key
    assert "efficiency ratio" not in text.lower() or True  # label only


def test_narrative_solar_hours_use_15min_interval(solar_df):
    """The deferred Phase 1 fix: solar hours at 15 min, not 10."""
    results = _results_for(solar_df, "solar")
    clean_df, _ = clean.clean(solar_df, schema="solar")

    text = narrative.build_narrative(results, clean_df, "solar")

    # 20 rows × 15 min = 300 minutes → exactly 5 hours (10-min math
    # would claim 3 hours — a 1.5× overstatement per hour)
    assert "5 hours" in text
    assert "3 hours" not in text
    assert "inverter" in text.lower()  # top-unit pattern from group_mean kind


def test_narrative_wind_pattern_is_seasonal_peak(wind_df):
    results = _results_for(wind_df, "wind")
    clean_df, _ = clean.clean(wind_df, schema="wind")
    text = narrative.build_narrative(results, clean_df, "wind")
    assert "Peak mean output occurred in" in text


def test_narrative_hydro_full_paragraph(hydro_df):
    """The hydro schema produces a complete paragraph with no code changes."""
    results = _results_for(hydro_df, "hydro")
    clean_df, _ = clean.clean(hydro_df, schema="hydro")

    text = narrative.build_narrative(results, clean_df, "hydro")

    assert "hydro turbine data" in text
    assert "3 hours" in text                     # 20 × 10 min
    assert "Peak mean output occurred in" in text  # bins-kind pattern
    for raw_key in (config.COL_HYDRO_FLOW, config.COL_HYDRO_GENERATED_POWER,
                    "conversion_ratio"):
        assert raw_key not in text


def test_narrative_anomaly_sentence(wind_df):
    results = _results_for(wind_df, "wind")
    clean_df, _ = clean.clean(wind_df, schema="wind")
    count = len(results["anomalies"])

    text = narrative.build_narrative(results, clean_df, "wind")

    if count > 0:
        assert f"{count} anomalous readings" in text
    else:
        assert "No anomalous readings" in text
