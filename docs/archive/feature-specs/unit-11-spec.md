# Unit 11: HTML Report

## Goal

Implement `html_export.py` to generate a single, self-contained
`report_YYYY-MM-DD.html` file — with charts embedded as base64
images and no external dependencies — mirroring the Excel report's
narrative, statistics, and anomaly content, selectable via a new
`--format` flag alongside the existing Excel export.

---

## Implementation

### 1. Extract Shared Narrative Logic First

Before writing `html_export.py`, refactor the narrative builders
out of `export.py` into a new shared module. Both exporters need
identical narrative text — duplicating it would violate the
single-source-of-truth principle this project has followed since
Unit 1.

**Create `narrative.py`:**

```python
"""
narrative.py

Owns narrative paragraph generation, shared between export.py
(Excel) and html_export.py (HTML). Produces schema-aware,
plain-English summaries from real computed analysis values.

No files are written. No side effects.
"""

import config


def build_narrative(results: dict, clean_df, schema: str) -> str:
    """
    Build the 3-5 sentence narrative paragraph for the given schema.

    Parameters:
        results (dict): analysis results from analyse.analyse(),
                        including 'anomalies' from detect.detect()
        clean_df: the clean DataFrame for this run
        schema (str): "wind" or "solar"

    Returns:
        str: narrative paragraph text
    """
    if schema == "wind":
        return _build_wind_narrative(results, clean_df)
    elif schema == "solar":
        return _build_solar_narrative(results, clean_df)


def _build_wind_narrative(results: dict, clean_df) -> str:
    ...  # moved from export.py, unchanged logic


def _build_solar_narrative(results: dict, clean_df) -> str:
    ...  # moved from export.py, unchanged logic
```

Move the exact logic already written in `export.py`'s
`_write_summary` (Unit 6) and its solar counterpart (Unit 9) into
these two functions verbatim — this is a relocation, not a rewrite.
Add one new sentence to both, since anomalies are now available:

```python
anomaly_count = len(results.get("anomalies", []))
anomaly_sentence = (
    f" {anomaly_count} anomalous readings were flagged during this "
    f"period and are detailed in the Anomaly Report."
    if anomaly_count > 0 else
    " No anomalous readings were flagged during this period."
)
```

**Update `export.py`:** replace its internal narrative-building code
with a call to `narrative.build_narrative(results, clean_df, schema)`.

---

### 2. Module Structure — `html_export.py`

```python
"""
html_export.py

Owns self-contained HTML report generation.
Produces a single .html file with all chart images embedded as
base64 data URIs — no external CSS, JS, or image file dependencies.
The file opens correctly offline and is safe to share as a single
attachment or deploy to GitHub Pages.

Side effect: writes one .html file to the output directory.
"""

import base64
from pathlib import Path
from datetime import date

import pandas as pd
import config
import narrative


def export_html(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    schema: str,
    output_dir: Path,
) -> Path:
    ...

def _encode_image(path: Path) -> str: ...
def _render_stats_table(results: dict, cfg: dict) -> str: ...
def _render_anomaly_summary(results: dict) -> str: ...
def _build_html(narrative_text, stats_html, anomaly_html, images_b64: list[str]) -> str: ...
```

---

### 3. `_encode_image(path)`

```python
def _encode_image(path: Path) -> str:
    """
    Read a .png file and return a base64 data URI string.

    Parameters:
        path (Path): path to the .png file

    Returns:
        str: complete data URI, e.g. "data:image/png;base64,iVBOR..."

    Assumptions:
        - path exists and is a valid PNG file
    """
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"
```

---

### 4. `_render_stats_table(results, cfg)`

Builds a plain HTML `<table>` from the same headline statistics
used in the Excel Summary sheet — mean, max for the primary column,
mean efficiency/conversion ratio, total rows analysed.

```python
def _render_stats_table(results: dict, cfg: dict) -> str:
    """
    Build an HTML table of headline statistics.

    Parameters:
        results (dict): analysis results dict
        cfg (dict): schema config from SCHEMA_REGISTRY

    Returns:
        str: HTML <tr> rows for the statistics table body
    """
    stats = results["stats"]
    efficiency = results["efficiency"]
    ratio_col = cfg["ratio_name"]

    rows = [
        ("Mean " + cfg["primary_power_col"], f"{stats.loc['mean', cfg['primary_power_col']]:.2f}"),
        ("Max " + cfg["primary_power_col"], f"{stats.loc['max', cfg['primary_power_col']]:.2f}"),
        ("Mean " + ratio_col, f"{efficiency[ratio_col].mean() * 100:.1f}%"),
        ("Total Rows Analysed", f"{len(efficiency):,}"),
    ]
    return "".join(f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows)
```

Use the same plain-English label dicts already defined in
`export.py` (`CLEAN_DATA_HEADERS`) to translate `cfg["primary_power_col"]`
into a human label rather than the raw column name — import and
reuse rather than redefining.

---

### 5. `_render_anomaly_summary(results)`

```python
def _render_anomaly_summary(results: dict) -> str:
    """
    Build a short HTML block summarising anomaly counts by type.

    Parameters:
        results (dict): must contain 'anomalies' key from detect.detect()

    Returns:
        str: HTML snippet, e.g. a small summary paragraph
    """
    anomalies = results.get("anomalies")
    if anomalies is None or anomalies.empty:
        return "<p>No anomalies were flagged during this period.</p>"

    counts = anomalies["anomaly_type"].value_counts()
    parts = [f"{count} {label.replace('_', ' ')}" for label, count in counts.items()]
    return f"<p>{len(anomalies)} anomalies flagged: {', '.join(parts)}.</p>"
```

---

### 6. `_build_html(...)` — Template Assembly

Single f-string template. Inline `<style>` only — no external CSS
file, no CDN links, no JS frameworks. Colour palette matches the
project's established navy/teal identity:

```python
def _build_html(
    narrative_text: str,
    stats_rows_html: str,
    anomaly_html: str,
    images_b64: list[str],
    chart_titles: list[str],
    schema: str,
) -> str:
    """
    Assemble the full HTML document as a single string.

    Parameters:
        narrative_text (str): narrative paragraph
        stats_rows_html (str): <tr> rows for the stats table
        anomaly_html (str): anomaly summary HTML block
        images_b64 (list[str]): base64 data URIs, one per chart
        chart_titles (list[str]): plain-English titles, same order
        schema (str): "wind" or "solar" — used in the page title

    Returns:
        str: complete, valid, self-contained HTML document
    """
    schema_label = "Wind Turbine" if schema == "wind" else "Solar Power"
    charts_html = "".join(
        f'<div class="chart"><h3>{title}</h3><img src="{img}" alt="{title}"></div>'
        for title, img in zip(chart_titles, images_b64)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{schema_label} Operations Report</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto;
         padding: 0 20px; color: #2D3142; background: #FFFFFF; }}
  h1 {{ color: #1B3A5C; border-bottom: 3px solid #2A7F8F; padding-bottom: 10px; }}
  h2 {{ color: #2A7F8F; margin-top: 40px; }}
  h3 {{ color: #1B3A5C; }}
  p.narrative {{ font-size: 1.05em; line-height: 1.6; background: #E8EEF2;
                padding: 20px; border-radius: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
  th, td {{ border: 1px solid #C8D6DE; padding: 8px 12px; text-align: left; }}
  th {{ background: #1B3A5C; color: white; }}
  .chart {{ margin: 30px 0; }}
  .chart img {{ max-width: 100%; border: 1px solid #C8D6DE; border-radius: 4px; }}
  footer {{ margin-top: 50px; font-size: 0.85em; color: #5B8FA8; text-align: center; }}
</style>
</head>
<body>
  <h1>{schema_label} Operations Report</h1>
  <p class="narrative">{narrative_text}</p>

  <h2>Headline Statistics</h2>
  <table><tbody>{stats_rows_html}</tbody></table>

  <h2>Anomaly Summary</h2>
  {anomaly_html}

  <h2>Charts</h2>
  {charts_html}

  <footer>Generated by Energy Operations Data Dashboard</footer>
</body>
</html>"""
```

---

### 7. `export_html(...)` — Public Entry Point

```python
def export_html(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    schema: str,
    output_dir: Path,
) -> Path:
    """
    Generate and save the self-contained HTML report.

    Parameters:
        clean_df (pd.DataFrame): clean DataFrame for this run
        results (dict): analysis results, including 'anomalies'
        chart_paths (list[Path]): four chart .png paths from visualise()
        schema (str): "wind" or "solar"
        output_dir (Path): directory to write the report to

    Returns:
        Path: path to the saved .html file

    Assumptions:
        - All paths in chart_paths exist on disk
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    narrative_text = narrative.build_narrative(results, clean_df, schema)
    stats_html = _render_stats_table(results, cfg)
    anomaly_html = _render_anomaly_summary(results)
    images_b64 = [_encode_image(p) for p in chart_paths]

    chart_titles = [
        "Daily Power Trend", "Power vs Secondary Metric",
        "Monthly Mean Power", "Power Output with Anomalies Highlighted",
    ]

    html = _build_html(narrative_text, stats_html, anomaly_html, images_b64, chart_titles, schema)

    filename = f"report_{date.today().isoformat()}.html"
    out_path = output_dir / filename
    out_path.write_text(html, encoding="utf-8")

    return out_path
```

---

### 8. `main.py` — `--format` Flag

```python
parser.add_argument(
    "--format",
    choices=["excel", "html", "both"],
    default="excel",
    help="Report format to generate: excel (default), html, or both.",
)
```

Update the export stage to branch on `args.format`:

```python
# ── Unit 11: Export ───────────────────────────────────────────────
try:
    print("[EXPORT]")
    if args.format in ("excel", "both"):
        report_path = export.export(
            clean_df=clean_df, results=results, chart_paths=chart_paths,
            run_id=run_id, output_dir=output_dir, schema=schema,
        )
        print(f"Report saved → {report_path}")
    if args.format in ("html", "both"):
        html_path = html_export.export_html(
            clean_df=clean_df, results=results, chart_paths=chart_paths,
            schema=schema, output_dir=output_dir,
        )
        print(f"Report saved → {html_path}")
except SystemExit:
    raise
except Exception as e:
    sys.exit(f"Unexpected error during export: {e}")
```

Add `import html_export` at the top of `main.py`. `main.py` does
not need to import `narrative` directly — only `export.py` and
`html_export.py` import it.

---

## Dependencies

- `base64` — stdlib, no install needed.

No new third-party packages in this unit.

---

## Verify When Done

### Refactor Correctness
- [ ] `export.py`'s Excel Summary sheet narrative text is
      identical in wording and computed values before and after
      the `narrative.py` extraction — confirms the refactor didn't
      change behaviour, only location
- [ ] `python -c "import narrative"` runs silently

### `--format` Flag Behaviour
- [ ] `python main.py --file data/turbine.csv` (no `--format` flag)
      produces only the `.xlsx` file — default unchanged
- [ ] `python main.py --file data/turbine.csv --format html`
      produces only the `.html` file — no `.xlsx` is written
- [ ] `python main.py --file data/turbine.csv --format both`
      produces both files in the same `output/` run

### HTML File Correctness
- [ ] `output/report_YYYY-MM-DD.html` exists after an `html` or
      `both` run
- [ ] File opens correctly in a browser with **no internet
      connection** — confirms no external CDN/font/image
      dependencies (disconnect Wi-Fi, open the file, verify styling
      and images still render)
- [ ] All four chart images are visible and correctly rendered —
      not broken image icons
- [ ] Narrative paragraph is present and contains real computed
      values, not placeholder text
- [ ] Anomaly summary section shows real counts matching the
      `[DETECT]` terminal line from the same run
- [ ] Statistics table renders as an actual HTML `<table>`, not
      raw text

### File Size Sanity Check
- [ ] The `.html` file size is reasonable — expect roughly 1–3 MB
      for four embedded 150 DPI charts (base64 adds ~33% overhead
      over the raw PNG size). If it's under 100 KB, images likely
      failed to embed; inspect the file for broken `data:` URIs.

### Schema Compatibility
- [ ] `python main.py --file data/turbine.csv --schema wind --format html`
      produces a correctly labelled "Wind Turbine Operations Report"
- [ ] `python main.py --file data/solar.csv --schema solar --format html`
      produces a correctly labelled "Solar Power Operations Report"

### Code Standards
- [ ] `html_export.py` contains no `print()` calls — `main.py` owns
      the `Report saved →` output
- [ ] No raw column strings in `html_export.py` — all references
      go through `cfg` or the shared header dicts from `export.py`
- [ ] `python -c "import html_export"` runs silently
- [ ] All functions have complete docstrings
- [ ] `html_export.py` does not import `ingest`, `clean`, `analyse`,
      `visualise`, or `export` — only `narrative` and `config`
