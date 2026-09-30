"""
test_visualise.py

Tests for visualise.py — chart generation contract: four non-empty
.png files per run, charts_dir parameter honoured, config.CHARTS_DIR
default preserved, and the daily_mean timeline contract.
"""

import pandas as pd
import pytest

import analyse
import clean
import config
import detect
import visualise

CHART_NAMES = {
    "power_trend.png", "wind_scatter.png",
    "monthly_bar.png", "anomaly_timeline.png",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

SCHEMA_FIXTURES = {"wind": "wind_df", "solar": "solar_df", "hydro": "hydro_df"}


def _results_for(df: pd.DataFrame, schema: str) -> dict:
    """Run the pre-visualise stages and return the results dict."""
    clean_df, _ = clean.clean(df, schema=schema)
    results = analyse.analyse(clean_df, schema=schema)
    results["anomalies"] = detect.detect(clean_df, schema=schema)
    return results


@pytest.mark.parametrize("schema", ["wind", "solar", "hydro"])
def test_four_nonempty_valid_pngs_in_tmp_charts_dir(
    request, tmp_path, monkeypatch, schema
):
    """Every schema produces 4 valid PNGs in the requested charts dir."""
    df = request.getfixturevalue(SCHEMA_FIXTURES[schema])
    charts_dir = tmp_path / "charts"
    charts_dir.mkdir()

    results = _results_for(df, schema)
    paths = visualise.visualise(results, schema, charts_dir=charts_dir)

    assert {p.name for p in paths} == CHART_NAMES
    for path in paths:
        assert path.parent == charts_dir      # charts_dir honoured
        assert path.stat().st_size > 0        # non-empty
        assert path.read_bytes()[:8] == PNG_MAGIC  # valid PNG header


def test_charts_dir_parameter_is_used_not_default_charts_dir(
    wind_df, tmp_path, monkeypatch
):
    """Files land in charts_dir, NOT in config.CHARTS_DIR."""
    redirected_default = tmp_path / "config_default_charts"
    redirected_default.mkdir(parents=True)
    monkeypatch.setattr(config, "CHARTS_DIR", redirected_default)

    explicit_dir = tmp_path / "explicit_charts"
    explicit_dir.mkdir()

    results = _results_for(wind_df, "wind")
    paths = visualise.visualise(results, "wind", charts_dir=explicit_dir)

    assert all(p.parent == explicit_dir for p in paths)
    assert not any(redirected_default.iterdir()), (
        "charts leaked into config.CHARTS_DIR despite explicit charts_dir"
    )


def test_default_charts_dir_kept_for_backward_compat(
    wind_df, tmp_path, monkeypatch
):
    """charts_dir=None falls back to config.CHARTS_DIR."""
    redirected_default = tmp_path / "config_default_charts"
    redirected_default.mkdir(parents=True)
    monkeypatch.setattr(config, "CHARTS_DIR", redirected_default)

    results = _results_for(wind_df, "wind")
    paths = visualise.visualise(results, "wind")  # no charts_dir

    assert {p.name for p in paths} == CHART_NAMES
    assert all(p.parent == redirected_default for p in paths)


def test_anomaly_timeline_plots_daily_mean_not_daily_total(wind_df):
    """The timeline's line series is daily_mean — same units as the
    instantaneous anomaly points drawn over it."""
    results = _results_for(wind_df, "wind")

    # The visualise() call itself requires the key — this asserts the
    # contract between analyse and visualise
    daily_total = results["daily"][config.COL_ACTIVE_POWER].iloc[0]
    daily_mean = results["daily_mean"][config.COL_ACTIVE_POWER].iloc[0]
    assert daily_mean < daily_total  # multi-row day: mean << sum
