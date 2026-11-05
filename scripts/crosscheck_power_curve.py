"""
crosscheck_power_curve.py

One-off validation of the pipeline measured power curve
(analyse._compute_power_curve) against two independent implementations,
run on the real wind SCADA dataset:

1. A vendored equivalent of OpenOA's `openoa.utils.power_curve.IEC`
   binned-mean algorithm (OpenOA is BSD-3 licensed; verified behaviour:
   left-closed fixed-width wind-speed bins, one mean output per bin,
   empty bins dropped). Re-implemented here with numpy floor binning so
   no OpenOA install is needed on Windows.

2. A short pandas reference: `pd.cut(..., right=False)` groupby mean,
   independent of both above implementations.

Both are computed on the exact same operational-row frame the pipeline
uses (its efficiency exclusion rule), then compared with the pipeline
curve at the same bin centres. For a like-for-like comparison, bins are
dropped when they hold fewer than MIN_SAMPLES samples in the
cross-check frame, or when their centre sits outside the IEC-style
cut-out range (WIND_RANGE).

Known deviations from a full IEC 61400-12-1 campaign apply to all
three implementations equally and are disclosed in
context/power-curve-crosscheck.md: nacelle anemometer wind speeds, no
air-density or turbulence filtering, and 10-minute pre-aggregated rows.

Run:  .venv/Scripts/python.exe scripts/crosscheck_power_curve.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import analyse
import clean
import config
import ingest

DATA_FILE = Path("data") / "turbine.csv"
SCHEMA = "wind"
MIN_SAMPLES = 6
WIND_RANGE = (0.0, 25.0)


def load_clean_wind_df() -> pd.DataFrame:
    """
    Load and clean the real wind SCADA CSV through the pipeline itself.

    Returns:
        pd.DataFrame: the same cleaned frame a normal pipeline run
                      analyses
    """
    raw_df = ingest.load_csv(DATA_FILE)
    ingest.validate_schema(raw_df, SCHEMA)
    clean_df, _ = clean.clean(raw_df, SCHEMA)
    return clean_df


def _operational_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Apply the pipeline's own operational-row exclusion rule.

    Mirrors the filter in analyse._compute_power_curve so every
    implementation sees identical rows.

    Parameters:
        df (pd.DataFrame): clean wind DataFrame
        cfg (dict): wind entry of config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: operational rows only
    """
    return df[
        (df[cfg["reference_col"]] > cfg["min_reference"]) &
        (df[cfg["primary_power_col"]] > cfg["min_primary"])
    ]


def openoa_iec_binned(
    operational: pd.DataFrame, cfg: dict, bin_width: float
) -> pd.Series:
    """
    Vendored equivalent of OpenOA's IEC binned power-curve algorithm.

    Reproduces the behaviour of `openoa.utils.power_curve.IEC` with
    `interpolate=False` on the operational frame: left-closed
    fixed-width bins over [0, 25) m/s, produced via numpy floor
    arithmetic rather than pandas.cut, one mean output per bin, empty
    bins dropped. Algorithm and licence attribution: National
    Renewable Energy Laboratory's OpenOA repository (BSD-3).

    Parameters:
        operational (pd.DataFrame): operational rows
        cfg (dict): wind registry entry
        bin_width (float): bin width in m/s

    Returns:
        pd.Series: bin mean power indexed by bin centre (m/s)
    """
    ws = operational[cfg["secondary_col"]].to_numpy()
    power = operational[cfg["primary_power_col"]].to_numpy()
    start, end = WIND_RANGE

    in_range = (ws >= start) & (ws < end)
    ws, power = ws[in_range], power[in_range]

    edges = np.arange(start, end, bin_width)
    index = np.floor((ws - start) / bin_width).astype(int)
    means = pd.Series(power).groupby(index[index < len(edges)]).mean()
    means.index = edges[means.index] + bin_width / 2
    means.index.name = "bin_centre"
    return means


def pandas_reference_binned(
    operational: pd.DataFrame, cfg: dict, bin_width: float
) -> pd.Series:
    """
    Short independent reference implementation with pandas.cut.

    Left-closed bins `[v, v + width)` over the common wind range, one
    mean output per bin. Deliberately written differently from
    analyse._compute_power_curve.

    Parameters:
        operational (pd.DataFrame): operational rows
        cfg (dict): wind registry entry
        bin_width (float): bin width in m/s

    Returns:
        pd.Series: bin mean power indexed by bin centre (m/s)
    """
    start, end = WIND_RANGE
    ws = operational[cfg["secondary_col"]]
    mask = (ws >= start) & (ws < end)
    binned = pd.cut(
        ws[mask], bins=np.arange(start, end + bin_width, bin_width), right=False
    )
    means = operational.loc[mask, cfg["primary_power_col"]].groupby(
        binned, observed=True
    ).mean()
    centres = [i.left + bin_width / 2 for i in means.index]
    means.index = pd.Index(centres, name="bin_centre")
    return means


def build_crosscheck_table(operational: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Compare the pipeline curve with both independent implementations.

    The pipeline curve is recomputed on the operational frame via
    analyse._compute_power_curve. Bins are kept only where the
    pipeline's sample count reaches MIN_SAMPLES in the cross-check
    frame and the bin centre lies inside WIND_RANGE; each kept bin
    reports the three means and the per-bin percentage difference of
    each independent implementation versus the pipeline.

    Parameters:
        operational (pd.DataFrame): operational rows
        cfg (dict): wind registry entry

    Returns:
        pd.DataFrame: one row per compared bin
    """
    bin_width = cfg["power_curve_bin_width"]
    pipeline_curve = analyse._compute_power_curve(operational, cfg)
    openoa_curve = openoa_iec_binned(operational, cfg, bin_width)
    reference_curve = pandas_reference_binned(operational, cfg, bin_width)

    pipeline_curve = pipeline_curve[
        pipeline_curve["count"] >= MIN_SAMPLES
    ]
    centres = pipeline_curve.index.map(
        lambda interval: interval.left + bin_width / 2
    )

    rows = []
    for interval, centre in zip(pipeline_curve.index, centres, strict=True):
        if not (WIND_RANGE[0] <= centre < WIND_RANGE[1]):
            continue
        p_mean = pipeline_curve.loc[interval, "mean_primary"]
        p_count = int(pipeline_curve.loc[interval, "count"])
        o_mean = (
            openoa_curve.loc[centre]
            if centre in openoa_curve.index
            else np.nan
        )
        r_mean = (
            reference_curve.loc[centre]
            if centre in reference_curve.index
            else np.nan
        )
        rows.append({
            "bin": str(interval),
            "centre": centre,
            "samples": p_count,
            "pipeline_kw": p_mean,
            "openoa_kw": o_mean,
            "reference_kw": r_mean,
            "openoa_diff_pct": abs(o_mean - p_mean) / p_mean * 100,
            "reference_diff_pct": abs(r_mean - p_mean) / p_mean * 100,
        })
    return pd.DataFrame(rows, columns=[
        "bin", "centre", "samples", "pipeline_kw",
        "openoa_kw", "reference_kw",
        "openoa_diff_pct", "reference_diff_pct",
    ])


def main() -> None:
    """
    Run the cross-check and print the results table and summary.

    Loads the real wind dataset through the pipeline, builds the
    comparison table, prints every bin, marks bins that disagree by
    more than FLAG_PCT, and prints the overall mean absolute
    percentage difference for both independent implementations.
    """
    flag_pct = 2.0
    cfg = config.SCHEMA_REGISTRY[SCHEMA]
    clean_df = load_clean_wind_df()
    operational = _operational_filter(clean_df, cfg)

    table = build_crosscheck_table(operational, cfg)
    table = table.round(
        {"centre": 2, "pipeline_kw": 2, "openoa_kw": 2,
         "reference_kw": 2, "openoa_diff_pct": 3, "reference_diff_pct": 3}
    )

    print(f"\nRows: total {len(clean_df)}, operational {len(operational)}")
    print(f"Bins compared ({MIN_SAMPLES}+ samples, "
          f"{WIND_RANGE[0]:g}-{WIND_RANGE[1]:g} m/s): {len(table)}")
    print(table.to_string(index=False))

    flagged = table[
        (table["openoa_diff_pct"] > flag_pct) |
        (table["reference_diff_pct"] > flag_pct)
    ]
    if flagged.empty:
        print(f"\nNo bin disagrees by more than {flag_pct:g}%")
    else:
        print(f"\nBins disagreeing by more than {flag_pct:g}%:")
        print(flagged["bin"].to_list())

    print(f"\nOverall mean absolute % difference vs pipeline: "
          f"OpenOA {table['openoa_diff_pct'].mean():.3f}%, "
          f"reference {table['reference_diff_pct'].mean():.3f}%")
    print(f"Operational share of rows: {len(operational) / len(clean_df):.1%}")


if __name__ == "__main__":
    main()
