# Unit 06: Export

## Goal

Implement `export.py` to assemble a six-sheet openpyxl workbook
from the analysis results, clean DataFrame, chart images, and
quality log — writing it to `output/report_YYYY-MM-DD.xlsx` —
and update `main.py` to call it, print `[EXPORT]`, and print the
final `Report saved →` line that completes the pipeline.

---

## Implementation

### 1. Install openpyxl

This is the first unit where `openpyxl` is needed. Install it now
inside your active environment before writing any code:

```bash
pip install "openpyxl>=3.1,<4.0"
```

Confirm the install:

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
```

---

### 2. Module Structure

`export.py` owns one responsibility: assembling the workbook and
writing it to disk. It receives all data it needs as arguments —
it does not import `analyse`, `clean`, `visualise`, or `ingest`.

```python
"""
export.py

Owns Excel workbook assembly and file export.
Receives the clean DataFrame, analysis results dict, chart image
paths, run_id, and output directory. Assembles a six-sheet .xlsx
workbook and returns the output file path.

Side effect: writes one .xlsx file to output/.
"""

from pathlib import Path
from datetime import date
import csv

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

import config


def export(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    run_id: str,
    output_dir: Path,
) -> Path:
    ...

# Internal helpers — one per sheet
def _write_summary(ws, results: dict, clean_df: pd.DataFrame) -> None: ...
def _write_dataframe(ws, df: pd.DataFrame, plain_headers: dict) -> None: ...
def _write_trend_analysis(ws, results: dict) -> None: ...
def _write_power_curve(ws, efficiency_df: pd.DataFrame) -> None: ...
def _write_charts(ws, chart_paths: list[Path]) -> None: ...
def _write_quality_log(ws, run_id: str) -> None: ...
def _style_header_row(ws, row_num: int, col_count: int) -> None: ...
```

---

### 3. `export(...)` — Public Entry Point

Builds the workbook, adds all six sheets in the required order,
saves the file, and returns the output path.

```python
def export(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    run_id: str,
    output_dir: Path,
) -> Path:
    """
    Assemble and save the six-sheet Excel report.

    Parameters:
        clean_df (pd.DataFrame): cleaned SCADA DataFrame from clean.clean()
        results (dict[str, pd.DataFrame]): analysis results from
            analyse.analyse(). Must contain keys: 'stats', 'efficiency',
            'monthly', 'daily', 'wind_bins'.
        chart_paths (list[Path]): list of three .png paths from
            visualise.visualise(), in order:
            [power_trend.png, wind_scatter.png, monthly_bar.png]
        run_id (str): UUID from clean.clean(), used to filter the
            quality log to this run's entries only
        output_dir (Path): directory to write the report to

    Returns:
        Path: full path of the written .xlsx file,
              e.g. output/report_2026-05-20.xlsx

    Assumptions:
        - output_dir exists
        - All three chart .png files in chart_paths exist on disk
        - logs/data_quality.log exists and contains entries for run_id
    """
    wb = Workbook()
    wb.remove(wb.active)  # Remove the default empty sheet

    # Add sheets in required order
    _write_summary(wb.create_sheet("Summary"), results, clean_df)
    _write_dataframe(
        wb.create_sheet("Clean Data"),
        clean_df,
        plain_headers=CLEAN_DATA_HEADERS,
    )
    _write_trend_analysis(wb.create_sheet("Trend Analysis"), results)
    _write_power_curve(wb.create_sheet("Power Curve Analysis"), results["efficiency"])
    _write_charts(wb.create_sheet("Charts"), chart_paths)
    _write_quality_log(wb.create_sheet("Data Quality Log"), run_id)

    # Build timestamped filename — Invariant 6
    filename = f"report_{date.today().isoformat()}.xlsx"
    out_path = output_dir / filename
    wb.save(out_path)

    return out_path
```

---

### 4. Plain-English Header Mapping

No raw column key names may appear in the workbook. Define a
module-level dict that maps each `config.COL_*` constant to its
plain-English label. This dict is the only place this mapping
lives — sheet writers reference it, they do not define their own.

```python
# Module-level — not logic, just a lookup table
CLEAN_DATA_HEADERS = {
    config.COL_DATETIME:       "Timestamp",
    config.COL_ACTIVE_POWER:   "Active Power (kW)",
    config.COL_WIND_SPEED:     "Wind Speed (m/s)",
    config.COL_THEORETICAL:    "Theoretical Power (kWh)",
    config.COL_WIND_DIRECTION: "Wind Direction (°)",
}

EFFICIENCY_HEADERS = {
    config.COL_DATETIME:       "Timestamp",
    config.COL_ACTIVE_POWER:   "Active Power (kW)",
    config.COL_WIND_SPEED:     "Wind Speed (m/s)",
    config.COL_THEORETICAL:    "Theoretical Power (kWh)",
    "efficiency_ratio":        "Efficiency Ratio",
}
```

---

### 5. `_write_summary(ws, results, clean_df)`

The Summary sheet has two components written top-to-bottom with
one blank row separating them:

**Component 1 — Narrative paragraph (rows 1–3):**

Generate a 3–5 sentence paragraph programmatically from real
computed values. Write it into cell `A1` with `wrap_text=True`.
Merge cells `A1:F3` so the paragraph has space to display.

The paragraph must cover these four points derived from the data:

- Total operational hours: `len(results["efficiency"]) * 10 / 60`
  (dataset records at 10-minute intervals)
- Mean active power: `results["stats"].loc["mean", config.COL_ACTIVE_POWER]`
- Overall mean efficiency ratio:
  `results["efficiency"]["efficiency_ratio"].mean() * 100`
- One notable pattern: the month with the highest mean output,
  derived from `results["monthly"]`

Example paragraph structure (values must be real, not hardcoded):

```python
peak_month = results["monthly"][config.COL_ACTIVE_POWER].idxmax()
peak_month_label = peak_month.strftime("%B %Y")
mean_power = results["stats"].loc["mean", config.COL_ACTIVE_POWER]
mean_efficiency = results["efficiency"]["efficiency_ratio"].mean() * 100
op_hours = round(len(results["efficiency"]) * 10 / 60)

narrative = (
    f"This report analyses {op_hours:,} hours of operational wind turbine data. "
    f"The turbine produced a mean active power output of {mean_power:,.1f} kW "
    f"across all operational periods. "
    f"Overall efficiency against the theoretical power curve averaged "
    f"{mean_efficiency:.1f}%, indicating the proportion of available wind energy "
    f"converted to output. "
    f"Peak mean output occurred in {peak_month_label}, suggesting strong seasonal "
    f"wind resource during this period."
)
```

**Component 2 — Headline statistics table (rows 5 onward):**

Write a simple two-column table with plain-English labels in
column A and values in column B. Style the header row with a dark
fill and white bold text.

| Metric | Value |
|---|---|
| Mean Active Power (kW) | `{value}` |
| Max Active Power (kW) | `{value}` |
| Std Dev Active Power (kW) | `{value}` |
| Mean Wind Speed (m/s) | `{value}` |
| Max Wind Speed (m/s) | `{value}` |
| Mean Efficiency Ratio (%) | `{value}` |
| Total Rows Analysed | `{value}` |
| Rows Excluded from Efficiency | `{value}` |

All values rounded to 2 decimal places. The `Rows Excluded`
value is `len(clean_df) - len(results["efficiency"])`.

---

### 6. `_write_dataframe(ws, df, plain_headers)`

Reusable helper used by Clean Data, Trend Analysis, and Power
Curve Analysis sheets. Writes a DataFrame to a worksheet starting
at row 1, using `plain_headers` to rename columns. Styles the
header row.

```python
def _write_dataframe(
    ws,
    df: pd.DataFrame,
    plain_headers: dict,
) -> None:
    """
    Write a DataFrame to a worksheet with plain-English headers.

    Renames columns using the plain_headers mapping before writing.
    Styles row 1 as a header row (dark fill, white bold text).
    All other rows are written as plain data.

    Parameters:
        ws: openpyxl Worksheet to write to
        df (pd.DataFrame): DataFrame to write
        plain_headers (dict): mapping of raw column names to
                              plain-English display labels.
                              Columns not in the mapping are
                              written with their original names.

    Returns:
        None
    """
    display_df = df.rename(columns=plain_headers)

    for row_idx, row in enumerate(
        dataframe_to_rows(display_df, index=True, header=True), start=1
    ):
        ws.append(row)
        if row_idx == 1:
            _style_header_row(ws, row_num=1, col_count=len(row))
```

---

### 7. `_write_trend_analysis(ws, results)`

Writes the `monthly` and `daily` DataFrames to the Trend Analysis
sheet, separated by a section label row.

Layout:
- Row 1: bold label `"Monthly Mean Active Power"`
- Row 2: header row for monthly data
- Rows 3–N: monthly data rows
- One blank row after monthly data
- Next row: bold label `"Daily Total Active Power"`
- Next row: header row for daily data
- Remaining rows: daily data rows

Use `_write_dataframe` is not appropriate here because of the
two-section layout — write both sections manually using
`ws.append()`, applying `_style_header_row` to each header row.
Plain-English column label for both sections: `"Active Power (kW)"`.

---

### 8. `_write_power_curve(ws, efficiency_df)`

Writes the `efficiency` DataFrame to the Power Curve Analysis
sheet using `_write_dataframe` with `EFFICIENCY_HEADERS` as the
header mapping.

```python
def _write_power_curve(ws, efficiency_df: pd.DataFrame) -> None:
    """
    Write the efficiency DataFrame to the Power Curve Analysis sheet.

    Parameters:
        ws: openpyxl Worksheet
        efficiency_df (pd.DataFrame): efficiency results from
                                      analyse._compute_efficiency()

    Returns:
        None
    """
    _write_dataframe(ws, efficiency_df, plain_headers=EFFICIENCY_HEADERS)
```

---

### 9. `_write_charts(ws, chart_paths)`

Embeds all three chart `.png` files as openpyxl `Image` objects
into the Charts sheet. Images are anchored to specific cells so
they are positioned consistently and do not overlap.

```python
def _write_charts(ws, chart_paths: list[Path]) -> None:
    """
    Embed chart .png files as images into the Charts sheet.

    Images are not linked — they are embedded directly into
    the workbook so the file is self-contained.

    Parameters:
        ws: openpyxl Worksheet
        chart_paths (list[Path]): list of three .png file paths,
                                  in order: power_trend, wind_scatter,
                                  monthly_bar

    Returns:
        None

    Assumptions:
        - All paths in chart_paths exist on disk
    """
    # Anchor positions — stacked vertically with spacing
    anchors = ["A1", "A32", "A62"]
    titles = ["Daily Power Trend", "Wind Speed vs Power Output", "Monthly Mean Power"]

    for path, anchor, title in zip(chart_paths, anchors, titles):
        # Write a plain label above each image
        row_num = int(anchor[1:]) if len(anchor) > 2 else int(anchor[1])
        ws.cell(row=row_num, column=1, value=title).font = Font(bold=True, size=11)

        img = XLImage(str(path))
        img.width = 700
        img.height = 300
        # Anchor image two rows below the label
        img_anchor = f"A{row_num + 2}"
        ws.add_image(img, img_anchor)
```

**`XLImage(str(path))`** — openpyxl requires a string path, not a
`pathlib.Path`. Always cast with `str()`.

**Image dimensions** (`width=700, height=300`) match the aspect
ratio of the saved `.png` files (1400×600 px at 2x). Do not omit
these — without explicit dimensions openpyxl uses the image's
native pixel size which will be enormous.

---

### 10. `_write_quality_log(ws, run_id)`

Reads `logs/data_quality.log`, filters rows to the current
`run_id` only, and writes them to the Data Quality Log sheet.
This sheet shows only this run's entries — not the full
append-only history.

```python
def _write_quality_log(ws, run_id: str) -> None:
    """
    Write quality log entries for the current run to the sheet.

    Reads logs/data_quality.log, filters to the current run_id,
    and writes matching rows with a styled header.

    Parameters:
        ws: openpyxl Worksheet
        run_id (str): UUID identifying the current run

    Returns:
        None

    Assumptions:
        - config.LOG_PATH exists and is readable
        - At least one entry for run_id exists in the log
    """
    log_path: Path = config.LOG_PATH

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r[config.LOG_FIELD_RUN_ID] == run_id]

    # Write header
    headers = config.LOG_FIELDS
    ws.append(headers)
    _style_header_row(ws, row_num=1, col_count=len(headers))

    # Write matching rows
    for row in rows:
        ws.append([row[field] for field in headers])
```

---

### 11. `_style_header_row(ws, row_num, col_count)`

Shared helper used by every sheet writer to apply consistent
header styling: dark navy fill, white bold text, centred alignment.

```python
def _style_header_row(ws, row_num: int, col_count: int) -> None:
    """
    Apply header styling to a row in a worksheet.

    Style: dark navy background (#1B3A5C), white bold text,
    centre-aligned.

    Parameters:
        ws: openpyxl Worksheet
        row_num (int): 1-based row number to style
        col_count (int): number of columns to style (starting from col 1)

    Returns:
        None
    """
    header_fill = PatternFill(
        start_color="1B3A5C", end_color="1B3A5C", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_alignment = Alignment(horizontal="center", vertical="center")

    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
```

---

### 12. Update `main.py`

Add the import and call `export()` after the `[VISUALISE]` block.
`main.py` prints `[EXPORT]` and the final `Report saved →` line.

**Add import:**
```python
import export
```

**Add after the `[VISUALISE]` block:**
```python
# ── Unit 6: Export ────────────────────────────────────────────────
try:
    print("[EXPORT]")
    report_path = export.export(
        clean_df=clean_df,
        results=results,
        chart_paths=chart_paths,
        run_id=run_id,
        output_dir=args.output,
    )
    print(f"Report saved → {report_path}")
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during export: {e}")
```

**Full terminal output for a successful end-to-end run:**
```
[LOAD] 52,608 rows × 5 columns
[CLEAN] 52,608 rows in → 52,543 rows clean (65 dropped)
[ANALYSE] 3,226 rows excluded from efficiency (zero theoretical or non-positive output)
[ANALYSE]

--- stats (8 rows) ---
...
[VISUALISE]
  Chart saved → output\charts\power_trend.png
  Chart saved → output\charts\wind_scatter.png
  Chart saved → output\charts\monthly_bar.png
[EXPORT]
Report saved → output\report_2026-05-20.xlsx
```

---

## Dependencies

- `openpyxl >= 3.1, < 4.0` — install now:
  `pip install "openpyxl>=3.1,<4.0"`. First use in the pipeline.

---

## Verify When Done

### Installation
- [ ] `python -c "import openpyxl; print(openpyxl.__version__)"`
      prints a `3.x` version string

### File Output
- [ ] Running `python main.py --file data/turbine.csv` produces
      a file named `report_YYYY-MM-DD.xlsx` in `output/` with
      today's date in the filename
- [ ] Running the script a second time produces a second file —
      the first file is not overwritten (both files exist in `output/`)
- [ ] The `.xlsx` file is non-zero in size (not an empty workbook)

### Workbook Structure
- [ ] File opens in Excel without any warnings or repair prompts
- [ ] Workbook contains exactly six sheets in this tab order:
      `Summary`, `Clean Data`, `Trend Analysis`,
      `Power Curve Analysis`, `Charts`, `Data Quality Log`
- [ ] No sheet is named using a raw `COL_*` constant or Python
      variable name

### Summary Sheet
- [ ] Sheet opens to a narrative paragraph in the top rows —
      not a table
- [ ] Narrative contains a specific number for operational hours
      (not a placeholder like `{op_hours}`)
- [ ] Narrative contains a specific mean active power value in kW
- [ ] Narrative contains a specific mean efficiency percentage
- [ ] Narrative names a specific peak month (e.g. "January 2018")
- [ ] A statistics table appears below the narrative
- [ ] Table has exactly 8 rows of metrics with plain-English labels
- [ ] No cell in the sheet contains a raw column key name such as
      `LV ActivePower (kW)` or `COL_ACTIVE_POWER`
- [ ] Header row has dark background with white bold text

### Clean Data Sheet
- [ ] Column headers are plain English:
      `Timestamp`, `Active Power (kW)`, `Wind Speed (m/s)`,
      `Theoretical Power (kWh)`, `Wind Direction (°)`
- [ ] Row count matches the clean DataFrame row count from the
      `[CLEAN]` terminal output
- [ ] Header row styled with dark background and white bold text

### Trend Analysis Sheet
- [ ] Two sections present: `Monthly Mean Active Power` and
      `Daily Total Active Power`, each with a bold section label
- [ ] Monthly section row count matches the number of distinct
      months in the dataset
- [ ] Daily section row count matches the number of distinct
      days in the dataset

### Power Curve Analysis Sheet
- [ ] Column headers are plain English:
      `Timestamp`, `Active Power (kW)`, `Wind Speed (m/s)`,
      `Theoretical Power (kWh)`, `Efficiency Ratio`
- [ ] Row count matches `len(results["efficiency"])` from Unit 4
- [ ] No `efficiency_ratio` raw key name visible in the sheet

### Charts Sheet
- [ ] Three images are visible in the sheet — not broken links,
      not placeholder boxes
- [ ] Each image has a plain-English label above it
- [ ] Images do not overlap each other
- [ ] Charts are still visible after closing and reopening the file
      (confirms images are embedded, not linked to external paths)

### Data Quality Log Sheet
- [ ] Column headers match `config.LOG_FIELDS` exactly
- [ ] Rows contain only entries matching the current run's `run_id`
- [ ] No entries from a previous run appear in the sheet
- [ ] Row count matches the number of log entries written during
      this run (verify against `logs/data_quality.log`)

### Code Standards
- [ ] `export.py` contains no `print()` calls
- [ ] `python -c "import export"` runs silently — no side effects
      on import
- [ ] All functions have complete docstrings
- [ ] No raw column name strings appear in `export.py` — all
      column references go through `config.COL_*` or the header
      mapping dicts defined at module level
- [ ] `export.py` does not import `ingest`, `clean`, `analyse`,
      or `visualise` — no lateral imports
- [ ] `XLImage` is called with `str(path)` not a `Path` object
