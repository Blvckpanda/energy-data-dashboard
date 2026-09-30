"""
conftest.py

Shared pytest fixtures: synthetic wind and solar DataFrames used
across the test suite. Fully synthetic — no dependency on real
Kaggle datasets being present in data/.
"""

import pandas as pd
import pytest

import config
import clean
import analyse
import detect
import visualise


@pytest.fixture
def wind_df() -> pd.DataFrame:
    """20 rows of synthetic wind SCADA data, 10-minute intervals."""
    timestamps = pd.date_range("2018-01-01", periods=20, freq="10min")
    return pd.DataFrame({
        config.COL_DATETIME: timestamps.strftime(config.DATE_FORMAT),
        config.COL_ACTIVE_POWER: [100.0 + i * 10 for i in range(20)],
        config.COL_WIND_SPEED: [5.0 + i * 0.2 for i in range(20)],
        config.COL_THEORETICAL: [120.0 + i * 10 for i in range(20)],
        config.COL_WIND_DIRECTION: [45.0 + i * 5 for i in range(20)],
    })


@pytest.fixture
def solar_df() -> pd.DataFrame:
    """20 rows of synthetic solar SCADA data, 15-minute intervals."""
    timestamps = pd.date_range("2020-05-15", periods=20, freq="15min")
    cfg = config.SCHEMA_REGISTRY["solar"]
    return pd.DataFrame({
        config.COL_SOLAR_DATETIME: timestamps.strftime(cfg["date_format"]),
        config.COL_PLANT_ID: ["4136001"] * 20,
        config.COL_SOURCE_KEY: ["INV001"] * 20,
        config.COL_DC_POWER: [200.0 + i * 15 for i in range(20)],
        config.COL_AC_POWER: [190.0 + i * 14 for i in range(20)],
        config.COL_DAILY_YIELD: [1000.0 + i * 50 for i in range(20)],
        config.COL_TOTAL_YIELD: [50000.0 + i * 50 for i in range(20)],
    })


@pytest.fixture
def hydro_df() -> pd.DataFrame:
    """20 rows of synthetic hydro SCADA data, 10-minute intervals."""
    timestamps = pd.date_range("2024-06-01", periods=20, freq="10min")
    cfg = config.SCHEMA_REGISTRY["hydro"]
    return pd.DataFrame({
        config.COL_HYDRO_DATETIME: timestamps.strftime(cfg["date_format"]),
        config.COL_HYDRO_FLOW: [12.0 + i * 0.5 for i in range(20)],
        config.COL_HYDRO_GENERATED_POWER: [800.0 + i * 40 for i in range(20)],
        config.COL_HYDRO_THEORETICAL_POWER: [900.0 + i * 45 for i in range(20)],
    })


@pytest.fixture
def wind_df_with_issues(wind_df) -> pd.DataFrame:
    """Wind DataFrame with a duplicate row, a null, and a bad string."""
    df = wind_df.copy()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplicate
    df.loc[5, config.COL_WIND_SPEED] = None                # null
    # Raw CSV columns arrive as object dtype — mimic a bad string there
    df[config.COL_ACTIVE_POWER] = df[config.COL_ACTIVE_POWER].astype(object)
    df.loc[6, config.COL_ACTIVE_POWER] = "N/A"              # bad string
    return df


@pytest.fixture
def wind_harness(tmp_path, monkeypatch):
    """
    Isolated pipeline harness for report tests.

    Redirects CHARTS_DIR and LOG_PATH into tmp_path, then returns a
    build(df) callable that runs clean → analyse → detect → visualise
    and returns (clean_df, run_id, results, chart_paths), plus the
    tmp output_dir and charts_dir paths.

    Returns:
        tuple: (build, output_dir, charts_dir) where
               build(df, schema="wind") runs the pre-export stages
    """
    output_dir = tmp_path / "output"
    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True)
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "logs" / "data_quality.log")
    monkeypatch.setattr(config, "CHARTS_DIR", charts_dir)

    def build(df: pd.DataFrame, schema: str = "wind") -> tuple:
        clean_df, run_id = clean.clean(df, schema=schema)
        results = analyse.analyse(clean_df, schema=schema)
        results["anomalies"] = detect.detect(clean_df, schema=schema)
        chart_paths = visualise.visualise(results, schema, charts_dir=charts_dir)
        return clean_df, run_id, results, chart_paths

    return build, output_dir, charts_dir
