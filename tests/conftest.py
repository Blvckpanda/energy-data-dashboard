"""
conftest.py

Shared pytest fixtures: synthetic wind and solar DataFrames used
across the test suite. Fully synthetic — no dependency on real
Kaggle datasets being present in data/.
"""

import pandas as pd
import pytest
import config


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
def wind_df_with_issues(wind_df) -> pd.DataFrame:
    """Wind DataFrame with a duplicate row, a null, and a bad string."""
    df = wind_df.copy()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplicate
    df.loc[5, config.COL_WIND_SPEED] = None                # null
    df.loc[6, config.COL_ACTIVE_POWER] = "N/A"              # bad string
    return df
