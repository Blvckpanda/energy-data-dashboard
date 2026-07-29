# Unit 10: Anomaly Detection

## Goal

Implement `detect.py` to flag anomalous power output rows using two
schema-agnostic methods — a standard-deviation threshold and a
rolling-window sustained-drop check — surfaced via a `[DETECT]`
terminal line, a fourth chart with anomalies highlighted, and a
seventh "Anomaly Report" sheet in the Excel export.

---

## Implementation

### 1. Confirm Config Constants

These three constants should already exist in `config.py` from the
earlier planning session. Confirm the names match exactly before
writing `detect.py`:

```python
ANOMALY_STD_THRESHOLD    = 2.0   # std deviations from mean to flag
ANOMALY_ROLLING_WINDOW   = 36    # intervals (36 × 10-min = 6 hours)
ANOMALY_ROLLING_DROP_PCT = 0.20  # rolling mean drop % to flag
```

If names differ, either rename them to match this spec or adjust
the code below to match your existing names — but the values and
meaning must stay as defined here.

---

### 2. Module Structure

```python
"""
detect.py

Owns anomaly detection for operational power output.
Accepts a clean DataFrame and schema name, returns a DataFrame
containing only the flagged anomalous rows with a reason column.

Two detection methods, both schema-agnostic via SCHEMA_REGISTRY:
  1. Static threshold — value deviates > N std devs from the
     operational mean
  2. Rolling window — sustained drop in a rolling mean vs the
     overall operational mean

No files are written by this module. No side effects beyond
the [DETECT] summary line printed to the terminal.
"""

import pandas as pd
import config


def detect(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    ...

def _flag_threshold(operational: pd.DataFrame, primary_col: str) -> pd.Series: ...
def _flag_rolling(operational: pd.DataFrame, datetime_col: str, primary_col: str) -> pd.Series: ...
```

---

### 3. `detect(df, schema)` — Public Entry Point

```python
def detect(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    """
    Flag anomalous rows in the primary power column.

    Parameters:
        df (pd.DataFrame): clean DataFrame (post clean.clean())
        schema (str): "wind" or "solar" — selects primary_power_col
                      and min_primary from config.SCHEMA_REGISTRY

    Returns:
        pd.DataFrame: only the flagged rows, with columns:
            [datetime_col, primary_power_col, anomaly_type, deviation]
            anomaly_type is one of: 'threshold', 'rolling_window', 'both'

    Assumptions:
        - df has already had efficiency-style operational filtering
          NOT applied — detect() filters internally to operational
          rows (primary_col > min_primary) before flagging, to avoid
          treating night-time / zero-output periods as anomalies
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    primary_col = cfg["primary_power_col"]
    datetime_col = cfg["datetime_col"]
    min_primary = cfg["min_primary"]

    operational = df[df[primary_col] > min_primary].copy()
    operational = operational.sort_values(datetime_col)

    threshold_flags = _flag_threshold(operational, primary_col)
    rolling_flags = _flag_rolling(operational, datetime_col, primary_col)

    operational["_threshold"] = threshold_flags
    operational["_rolling"] = rolling_flags

    flagged = operational[operational["_threshold"] | operational["_rolling"]].copy()

    def _label(row):
        if row["_threshold"] and row["_rolling"]:
            return "both"
        elif row["_threshold"]:
            return "threshold"
        return "rolling_window"

    flagged["anomaly_type"] = flagged.apply(_label, axis=1)

    mean_val = operational[primary_col].mean()
    flagged["deviation"] = flagged[primary_col] - mean_val

    result = flagged[[datetime_col, primary_col, "anomaly_type", "deviation"]]

    threshold_count = (flagged["anomaly_type"].isin(["threshold", "both"])).sum()
    rolling_count = (flagged["anomaly_type"].isin(["rolling_window", "both"])).sum()
    print(
        f"[DETECT] {len(result):,} anomalies flagged "
        f"({threshold_count} threshold, {rolling_count} rolling window)"
    )

    return result
```

---

### 4. `_flag_threshold(operational, primary_col)`

```python
def _flag_threshold(operational: pd.DataFrame, primary_col: str) -> pd.Series:
    """
    Flag rows where the value deviates more than
    config.ANOMALY_STD_THRESHOLD standard deviations from the mean.

    Parameters:
        operational (pd.DataFrame): operational rows only
        primary_col (str): column to evaluate

    Returns:
        pd.Series[bool]: True where flagged
    """
    mean_val = operational[primary_col].mean()
    std_val = operational[primary_col].std()
    threshold = config.ANOMALY_STD_THRESHOLD * std_val
    return (operational[primary_col] - mean_val).abs() > threshold
```

---

### 5. `_flag_rolling(operational, datetime_col, primary_col)`

```python
def _flag_rolling(
    operational: pd.DataFrame, datetime_col: str, primary_col: str
) -> pd.Series:
    """
    Flag rows where a rolling mean has dropped more than
    config.ANOMALY_ROLLING_DROP_PCT below the overall operational
    mean, sustained over config.ANOMALY_ROLLING_WINDOW intervals.

    Parameters:
        operational (pd.DataFrame): operational rows, sorted by
                                    datetime_col
        datetime_col (str): datetime column name
        primary_col (str): column to evaluate

    Returns:
        pd.Series[bool]: True where flagged. Index-aligned with
                         the input operational DataFrame.
    """
    overall_mean = operational[primary_col].mean()
    rolling_mean = (
        operational[primary_col]
        .rolling(window=config.ANOMALY_ROLLING_WINDOW, min_periods=1)
        .mean()
    )
    drop_threshold = overall_mean * (1 - config.ANOMALY_ROLLING_DROP_PCT)
    return rolling_mean < drop_threshold
```

---

### 6. Update `main.py`

Add the import and call `detect()` after the `[ANALYSE]` block,
inserting the result into `results` under the key `"anomalies"`.
This keeps `visualise()` and `export()` signatures unchanged — they
simply receive one more key in the dict they already accept.

```python
import detect
```

```python
# ── Unit 10: Anomaly Detection ────────────────────────────────────
try:
    results["anomalies"] = detect.detect(clean_df, schema)
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during anomaly detection: {e}")
```

Place this immediately after the `[ANALYSE]` preview block and
before `[VISUALISE]` — `visualise.py` needs `results["anomalies"]`
for the new anomaly timeline chart.

---

### 7. `visualise.py` — Fourth Chart

Add `_plot_anomaly_timeline(daily_df, anomalies_df, cfg)` producing
`anomaly_timeline.png`: the same daily trend line as `power_trend.png`,
with red markers overlaid at each anomalous timestamp.

```python
def _plot_anomaly_timeline(
    daily_df: pd.DataFrame, anomalies_df: pd.DataFrame, cfg: dict, axis_label: str
) -> Path:
    """
    Generate a trend line with anomalous periods highlighted.

    Parameters:
        daily_df (pd.DataFrame): daily resampled DataFrame
        anomalies_df (pd.DataFrame): output of detect.detect()
        cfg (dict): schema config from SCHEMA_REGISTRY
        axis_label (str): plain-English y-axis label

    Returns:
        Path: path to the saved anomaly_timeline.png file
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        daily_df.index, daily_df[cfg["primary_power_col"]],
        linewidth=0.8, color=sns.color_palette("muted")[0], zorder=1,
    )

    if not anomalies_df.empty:
        ax.scatter(
            anomalies_df[cfg["datetime_col"]],
            anomalies_df[cfg["primary_power_col"]],
            color="crimson", s=12, zorder=2, label="Anomaly",
        )
        ax.legend()

    ax.set_title("Power Output with Anomalies Highlighted", fontsize=14, pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel(axis_label, fontsize=11)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()

    out_path = config.CHARTS_DIR / "anomaly_timeline.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path
```

Update `visualise(results, schema)` to call this fourth helper and
return a list of **four** paths. Update the docstring and the
`main.py` print loop — no code change needed there since it already
iterates the returned list generically.

**Note:** anomaly markers are plotted from `anomalies_df` timestamps
directly (10-minute resolution), overlaid on the *daily* trend line.
A single anomalous 10-minute reading may appear to sit slightly off
the smoothed daily line — this is expected and acceptable; the
purpose is to show roughly where anomalies cluster, not exact
per-point alignment.

---

### 8. `export.py` — Seventh Sheet

Add `_write_anomalies(ws, anomalies_df, cfg)`:

```python
def _write_anomalies(ws, anomalies_df: pd.DataFrame, cfg: dict) -> None:
    """
    Write the anomaly report to the Anomaly Report sheet.

    Parameters:
        ws: openpyxl Worksheet
        anomalies_df (pd.DataFrame): output of detect.detect()
        cfg (dict): schema config, used for the primary column label

    Returns:
        None
    """
    headers = {
        cfg["datetime_col"]: "Timestamp",
        cfg["primary_power_col"]: "Output Value",
        "anomaly_type": "Detection Method",
        "deviation": "Deviation from Mean",
    }
    _write_dataframe(ws, anomalies_df, plain_headers=headers)
```

Update `export()` to add this as the seventh sheet, positioned
after "Charts" and before "Data Quality Log":

```
Summary → Clean Data → Trend Analysis → Efficiency Analysis →
Charts → Anomaly Report → Data Quality Log
```

Update `_write_charts` to embed the fourth image
(`anomaly_timeline.png`) alongside the existing three.

---

## Dependencies

No new packages. `pandas.Series.rolling()` is already available in
the installed pandas version.

---

## Verify When Done

### Terminal Output
- [ ] `[DETECT]` line appears after the `[ANALYSE]` block, before
      `[VISUALISE]`, in the format:
      `[DETECT] N anomalies flagged (X threshold, Y rolling window)`

### Detection Correctness — Synthetic Test
- [ ] Manually inject one extreme outlier into a test CSV (set one
      row's power value to 10× the column mean), run the pipeline,
      confirm that row appears in `results["anomalies"]` with
      `anomaly_type` including `"threshold"`
- [ ] Manually zero out ~40 consecutive rows' power values (simulating
      a sustained drop) in a test CSV, run the pipeline, confirm
      those rows are flagged with `anomaly_type` including
      `"rolling_window"`

### Data Correctness
- [ ] No row in `results["anomalies"]` has a `primary_col` value at
      or below `min_primary` — non-operational rows are excluded
      before flagging, not flagged as anomalies
- [ ] `deviation` column values are correctly signed (negative for
      below-mean anomalies, positive for above-mean)

### Charts
- [ ] `visualise()` returns four paths, not three
- [ ] `output/charts/anomaly_timeline.png` exists and shows red
      markers on the trend line
- [ ] If a test run has zero anomalies, the chart still generates
      successfully with just the trend line and no legend (empty
      `anomalies_df` handled gracefully, no crash)

### Export
- [ ] Workbook contains seven sheets in the order specified above
- [ ] "Anomaly Report" sheet has plain-English headers:
      `Timestamp`, `Output Value`, `Detection Method`,
      `Deviation from Mean`
- [ ] Charts sheet shows all four embedded images

### Schema Compatibility
- [ ] `python main.py --file data/turbine.csv --schema wind` — 
      detection runs without error
- [ ] `python main.py --file data/solar.csv --schema solar` — 
      detection runs without error, using `AC_POWER` as the
      evaluated column

### Code Standards
- [ ] `detect.py` contains exactly one `print()` call — the
      `[DETECT]` summary line
- [ ] No raw column strings in `detect.py` — all references go
      through `cfg` values sourced from `config.SCHEMA_REGISTRY`
- [ ] `python -c "import detect"` runs silently
- [ ] All functions have complete docstrings
- [ ] `detect.py` does not import `ingest`, `visualise`, or `export`
