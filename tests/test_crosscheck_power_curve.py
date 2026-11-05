"""
tests/test_crosscheck_power_curve.py

Unit tests for the reusable comparison helpers in
scripts/crosscheck_power_curve.py, run on a small synthetic frame: the
two independent implementations must agree with the pipeline curve on
identical bins and the table must drop under-sampled bins. The real
dataset run itself is a one-off and lives in
context/power-curve-crosscheck.md.
"""

import pandas as pd

import config
import scripts.crosscheck_power_curve as cc


def _wind_frame(ws: list[float], power: list[float]) -> pd.DataFrame:
    """
    Build a synthetic clean-style wind frame for the compare helpers.

    Rows are operational by construction (theoretical power and active
    power sitting above the registry's minimum thresholds).

    Parameters:
        ws (list[float]): wind speed readings (m/s)
        power (list[float]): active power readings (kW)

    Returns:
        pd.DataFrame: frame shaped like a cleaned wind dataset
    """
    n = len(ws)
    return pd.DataFrame({
        config.COL_DATETIME: pd.date_range(
            "2026-01-01", periods=n, freq="10min"
        ),
        config.COL_ACTIVE_POWER: power,
        config.COL_WIND_SPEED: ws,
        config.COL_THEORETICAL: [100.0] * n,
        config.COL_WIND_DIRECTION: [0.0] * n,
    })


def test_implementations_agree_on_identical_bins():
    """OpenOA-style floor binning and the pandas reference must produce
    identical bin means on the same frame."""
    df = _wind_frame(
        ws=[3.01, 3.24, 3.49, 3.99, 4.01, 4.49],
        power=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    )
    cfg = config.SCHEMA_REGISTRY["wind"]
    operational = cc._operational_filter(df, cfg)

    openoa_curve = cc.openoa_iec_binned(operational, cfg, 0.5)
    reference_curve = cc.pandas_reference_binned(operational, cfg, 0.5)

    assert openoa_curve.index.equals(reference_curve.index)
    pd.testing.assert_series_equal(
        openoa_curve.sort_index(),
        reference_curve.sort_index(),
        check_names=False,
    )


def test_table_reports_zero_difference_for_identical_bins():
    """Every compared bin reports 0% difference for both independent
    implementations when the pipeline curve is the target."""
    df = _wind_frame(
        ws=[3.01, 3.24, 3.49, 3.99, 3.02, 3.36, 3.5, 3.1],
        power=[10.0, 20.0, 30.0, 40.0, 25.0, 35.0, 45.0, 15.0],
    )
    cfg = config.SCHEMA_REGISTRY["wind"]
    operational = cc._operational_filter(df, cfg)
    table = cc.build_crosscheck_table(operational, cfg)

    assert not table.empty
    assert table["openoa_diff_pct"].max() == 0.0
    assert table["reference_diff_pct"].max() == 0.0


def test_under_sampled_bins_are_dropped():
    """Bins below MIN_SAMPLES samples stay out of the comparison."""
    df = _wind_frame(
        ws=[3.01, 3.24, 3.49, 3.99, 4.01, 4.49],
        power=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    )
    cfg = config.SCHEMA_REGISTRY["wind"]
    operational = cc._operational_filter(df, cfg)
    table = cc.build_crosscheck_table(operational, cfg)

    assert (table["samples"] >= cc.MIN_SAMPLES).all()
    # 5 of the 6 rows land in [3.0, 3.5); that bin is dropped, and the
    # single-sample tail bins are dropped too
    assert table.empty


def test_out_of_range_bins_are_dropped():
    """Bins outside the common wind-speed range are not compared."""
    df = _wind_frame(
        ws=[25.01, 25.49, 25.01, 25.49, 25.01, 25.49, 25.01, 25.49],
        power=[70.0, 80.0, 70.0, 80.0, 70.0, 80.0, 70.0, 80.0],
    )
    cfg = config.SCHEMA_REGISTRY["wind"]
    operational = cc._operational_filter(df, cfg)
    table = cc.build_crosscheck_table(operational, cfg)

    assert table.empty
