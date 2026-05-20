# Unit 05: Visualisation

## Goal

Implement `visualise.py` to generate three charts — a daily power
trend line, a wind speed vs power scatter with theoretical curve
overlay, and a monthly mean bar chart — saving each as a `.png`
to `output/charts/`, and update `main.py` to call it and print the
`[VISUALISE]` marker with each saved file path.

---

## Implementation

### 1. Install Dependencies

This is the first unit where `matplotlib` and `seaborn` are needed.
Install both now inside your active environment before writing any
code:

```bash
pip install "matplotlib>=3.8,<4.0" "seaborn>=0.13,<1.0"
```

Confirm both installs:

```bash
python -c "import matplotlib; print(matplotlib.__version__)"
python -c "import seaborn; print(seaborn.__version__)"
```

---

### 2. Module Structure

`visualise.py` owns one responsibility: generating chart figures
and saving them as `.png` files to `output/charts/`. It returns a
list of saved file paths so `export.py` (Unit 6) knows exactly
which images to embed — it does not need to scan the folder.

`visualise.py` does not know about Excel, about `analyse.py`
internals, or about the report structure. It receives DataFrames
and returns file paths.

```python
"""
visualise.py

Owns chart generation and .png export to output/charts/.
Accepts result DataFrames from analyse.py and saves one .png
per chart. Returns a list of saved file paths for use by export.py.

Side effect: writes .png files to output/charts/.
This directory must exist before visualise() is called.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — no display window needed
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import config


def visualise(results: dict[str, pd.DataFrame]) -> list[Path]:
    ...

# Internal helpers — one per chart
def _plot_power_trend(daily_df: pd.DataFrame) -> Path: ...
def _plot_wind_scatter(efficiency_df: pd.DataFrame) -> Path: ...
def _plot_monthly_bar(monthly_df: pd.DataFrame) -> Path: ...
```

**Critical — `matplotlib.use("Agg")`:**
This line must appear immediately after importing `matplotlib` and
before importing `matplotlib.pyplot`. It sets the non-interactive
backend so the pipeline can generate charts without a display
(required on headless servers and prevents pop-up windows during
runs). If this line is missing or placed after `plt` is imported,
the script may hang or crash on some environments.

---

### 3. Seaborn Theme Setup

Set the Seaborn theme once at module level — after the backend is
set, before any plot functions are defined. This applies a
consistent visual style to all charts with no per-chart
configuration needed.

```python
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
```

This is the one permitted module-level call beyond imports —
it configures the global Matplotlib state and must be set before
any figure is created. It is not "logic" in the sense of
Invariant 3; it is library initialisation equivalent to setting
a default.

---

### 4. `visualise(results)` — Public Entry Point

Receives the full `results` dict from `analyse.analyse()`, calls
each chart helper, and returns the list of all saved paths.

```python
def visualise(results: dict[str, pd.DataFrame]) -> list[Path]:
    """
    Generate all three charts and save them to output/charts/.

    Parameters:
        results (dict[str, pd.DataFrame]): the full results dict
            from analyse.analyse(). Must contain keys:
            'daily', 'efficiency', 'monthly'.

    Returns:
        list[Path]: list of three Path objects pointing to the
                    saved .png files, in this order:
                    [power_trend.png, wind_scatter.png, monthly_bar.png]

    Assumptions:
        - output/charts/ directory already exists
        - 'daily' DataFrame has a DatetimeIndex and COL_ACTIVE_POWER column
        - 'efficiency' DataFrame has COL_WIND_SPEED, COL_ACTIVE_POWER,
          COL_THEORETICAL columns
        - 'monthly' DataFrame has a DatetimeIndex and COL_ACTIVE_POWER column
    """
    paths = [
        _plot_power_trend(results["daily"]),
        _plot_wind_scatter(results["efficiency"]),
        _plot_monthly_bar(results["monthly"]),
    ]
    return paths
```

---

### 5. `_plot_power_trend(daily_df)` → `power_trend.png`

**What it shows:** Daily total active power output over the full
time range of the dataset. Reveals seasonal patterns, maintenance
periods, and long-term trends.

**Chart type:** Line chart

**Data source:** `results["daily"]` — DatetimeIndex, one column
(`COL_ACTIVE_POWER`), one row per calendar day.

```python
def _plot_power_trend(daily_df: pd.DataFrame) -> Path:
    """
    Generate a line chart of daily total active power over time.

    Parameters:
        daily_df (pd.DataFrame): daily resampled DataFrame from
                                 analyse._compute_daily(). DatetimeIndex,
                                 single column COL_ACTIVE_POWER.

    Returns:
        Path: path to the saved power_trend.png file

    Assumptions:
        - daily_df has a DatetimeIndex
        - output/charts/ directory exists
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        daily_df.index,
        daily_df[config.COL_ACTIVE_POWER],
        linewidth=0.8,
        color=sns.color_palette("muted")[0],
    )

    ax.set_title("Daily Active Power Output Over Time", fontsize=14, pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Active Power (kW)", fontsize=11)
    ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "power_trend.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path
```

**`plt.close(fig)` is mandatory** after every `fig.savefig()` call.
If figures are not closed, Matplotlib accumulates them in memory.
On a full dataset this will silently consume hundreds of MB.

---

### 6. `_plot_wind_scatter(efficiency_df)` → `wind_scatter.png`

**What it shows:** The relationship between wind speed and actual
power output, with the theoretical power curve overlaid as a second
series. The gap between actual and theoretical is the efficiency
loss visible at a glance.

**Chart type:** Scatter (actual output) + line (theoretical curve)

**Data source:** `results["efficiency"]` — operational rows only,
contains `COL_WIND_SPEED`, `COL_ACTIVE_POWER`, `COL_THEORETICAL`.

```python
def _plot_wind_scatter(efficiency_df: pd.DataFrame) -> Path:
    """
    Generate a scatter plot of wind speed vs active power output,
    with the theoretical power curve overlaid as a line.

    Parameters:
        efficiency_df (pd.DataFrame): efficiency DataFrame from
                                      analyse._compute_efficiency().
                                      Operational rows only.
                                      Must contain COL_WIND_SPEED,
                                      COL_ACTIVE_POWER, COL_THEORETICAL.

    Returns:
        Path: path to the saved wind_scatter.png file

    Assumptions:
        - efficiency_df contains only operational rows
          (COL_THEORETICAL > 0 and COL_ACTIVE_POWER > 0)
        - output/charts/ directory exists
    """
    # Sort by wind speed so the theoretical curve line renders cleanly
    sorted_df = efficiency_df.sort_values(config.COL_WIND_SPEED)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Actual power — scatter, semi-transparent to show density
    ax.scatter(
        efficiency_df[config.COL_WIND_SPEED],
        efficiency_df[config.COL_ACTIVE_POWER],
        alpha=0.15,
        s=3,
        color=sns.color_palette("muted")[0],
        label="Actual Power Output",
    )

    # Theoretical curve — line over sorted data
    ax.plot(
        sorted_df[config.COL_WIND_SPEED],
        sorted_df[config.COL_THEORETICAL],
        linewidth=1.5,
        color=sns.color_palette("muted")[2],
        label="Theoretical Power Curve",
    )

    ax.set_title(
        "Wind Speed vs Active Power Output (with Theoretical Curve)",
        fontsize=13,
        pad=12,
    )
    ax.set_xlabel("Wind Speed (m/s)", fontsize=11)
    ax.set_ylabel("Power (kW)", fontsize=11)
    ax.legend(fontsize=10)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "wind_scatter.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path
```

**`alpha=0.15` and `s=3`** are intentional — the SCADA dataset has
~50,000 rows. Without low alpha and small point size, the scatter
renders as a solid black mass. These values show the data density
distribution clearly.

**Sort before plotting the theoretical line** — `sorted_df` is used
only for the theoretical curve. If the data is unsorted, the line
will zigzag back and forth across the x-axis instead of following
the curve shape.

---

### 7. `_plot_monthly_bar(monthly_df)` → `monthly_bar.png`

**What it shows:** Mean active power output per calendar month.
Reveals seasonal patterns — wind turbines typically produce more
in winter and less in summer in the Northern Hemisphere.

**Chart type:** Vertical bar chart

**Data source:** `results["monthly"]` — DatetimeIndex at `MS`
frequency, one column (`COL_ACTIVE_POWER`), one row per month.

```python
def _plot_monthly_bar(monthly_df: pd.DataFrame) -> Path:
    """
    Generate a bar chart of monthly mean active power output.

    Parameters:
        monthly_df (pd.DataFrame): monthly resampled DataFrame from
                                   analyse._compute_monthly().
                                   DatetimeIndex at MS frequency,
                                   single column COL_ACTIVE_POWER.

    Returns:
        Path: path to the saved monthly_bar.png file

    Assumptions:
        - monthly_df has a DatetimeIndex
        - output/charts/ directory exists
    """
    # Format x-axis labels as "Jan 2018", "Feb 2018", etc.
    labels = monthly_df.index.strftime("%b %Y")

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(
        range(len(monthly_df)),
        monthly_df[config.COL_ACTIVE_POWER],
        color=sns.color_palette("muted")[1],
        edgecolor="white",
        linewidth=0.5,
    )

    ax.set_xticks(range(len(monthly_df)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_title("Monthly Mean Active Power Output", fontsize=14, pad=12)
    ax.set_xlabel("Month", fontsize=11)
    ax.set_ylabel("Mean Active Power (kW)", fontsize=11)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "monthly_bar.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path
```

**`range(len(monthly_df))` for x positions, then `set_xticklabels`:**
Matplotlib's `bar()` works better with numeric x positions than
datetime objects for this chart type. The labels are applied
separately with `strftime("%b %Y")` formatting so they read as
`"Jan 2018"` not raw timestamps.

---

### 8. Update `main.py`

Add the import and call `visualise()` after the `[ANALYSE]` block.
`main.py` owns the `[VISUALISE]` terminal output — `visualise.py`
returns paths, it does not print anything.

**Add import:**
```python
import visualise
```

**Add after the `[ANALYSE]` block:**
```python
# ── Unit 5: Visualisation ─────────────────────────────────────────
try:
    chart_paths = visualise.visualise(results)
    print("[VISUALISE]")
    for path in chart_paths:
        print(f"  Chart saved → {path}")
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during visualisation: {e}")
```

**Terminal output will look like:**
```
[VISUALISE]
  Chart saved → output\charts\power_trend.png
  Chart saved → output\charts\wind_scatter.png
  Chart saved → output\charts\monthly_bar.png
```

---

## Dependencies

- `matplotlib >= 3.8, < 4.0` — install now:
  `pip install "matplotlib>=3.8,<4.0"`
- `seaborn >= 0.13, < 1.0` — install now:
  `pip install "seaborn>=0.13,<1.0"`

No other new packages in this unit.

---

## Verify When Done

### Installation
- [ ] `python -c "import matplotlib; print(matplotlib.__version__)"` 
      prints a `3.x` version string
- [ ] `python -c "import seaborn; print(seaborn.__version__)"` 
      prints a `0.13.x` version string
- [ ] `pip show openpyxl` returns "not found" — confirming
      just-in-time install discipline holds

### Terminal Output
- [ ] Running `python main.py --file data/turbine.csv` prints
      `[LOAD]`, `[CLEAN]`, the efficiency exclusion line,
      `[ANALYSE]`, and `[VISUALISE]` in that order with no errors
- [ ] Three `Chart saved →` lines appear under `[VISUALISE]`,
      one per file
- [ ] No pop-up window appears during the run — confirms the
      `Agg` backend is set correctly

### File Output
- [ ] `output/charts/power_trend.png` exists after the run
- [ ] `output/charts/wind_scatter.png` exists after the run
- [ ] `output/charts/monthly_bar.png` exists after the run
- [ ] All three files have non-zero file size (not empty/corrupt)
- [ ] All three files open correctly in an image viewer

### Chart Content — `power_trend.png`
- [ ] X-axis shows dates across the full time range of the dataset
- [ ] Y-axis label reads `"Active Power (kW)"` — not a raw column key
- [ ] Chart title reads `"Daily Active Power Output Over Time"`
- [ ] Line is continuous (not a scatter/dot plot)

### Chart Content — `wind_scatter.png`
- [ ] Two distinct series are visible: scattered points and a line
- [ ] Legend is present and labels both series in plain English:
      `"Actual Power Output"` and `"Theoretical Power Curve"`
- [ ] X-axis label reads `"Wind Speed (m/s)"`
- [ ] Y-axis label reads `"Power (kW)"`
- [ ] Scatter points are semi-transparent — density is visible,
      not a solid block
- [ ] Theoretical curve line is smooth (sorted by wind speed,
      not zigzagging)

### Chart Content — `monthly_bar.png`
- [ ] X-axis tick labels are formatted as `"Mon YYYY"`
      (e.g. `"Jan 2018"`) — not raw timestamps
- [ ] X-axis labels are rotated and not overlapping
- [ ] Y-axis label reads `"Mean Active Power (kW)"`
- [ ] Chart title reads `"Monthly Mean Active Power Output"`
- [ ] Bar count matches the number of distinct months in the dataset

### Small Dataset Test
- [ ] Run the pipeline on the first 500 rows:
      create a test CSV with `head -501 data/turbine.csv > data/test.csv`
      then run `python main.py --file data/test.csv`
- [ ] All three charts generate without errors on this small slice
- [ ] Delete `data/test.csv` after testing

### Code Standards
- [ ] `visualise.py` contains no `print()` calls
- [ ] `matplotlib.use("Agg")` appears before `import matplotlib.pyplot`
- [ ] `plt.close(fig)` is called after every `fig.savefig()` — 
      confirmed by inspecting source (three `close` calls, one per chart)
- [ ] `python -c "import visualise"` runs silently — no side effects,
      no file writes, no windows on import
- [ ] All four functions have complete docstrings
- [ ] `visualise.py` does not import `ingest`, `clean`, `analyse`,
      or `export` — no lateral imports
- [ ] No hardcoded file path strings — all paths use `config.CHARTS_DIR`
