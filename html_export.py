"""
html_export.py

Owns self-contained HTML report generation.
Produces a single .html file with all chart images embedded as
base64 data URIs — no external CSS, JS, or image file dependencies.
The file opens correctly offline and is safe to share as a single
attachment or deploy to GitHub Pages.

Fully schema-agnostic: statistics labels and the report title come
from config.SCHEMA_REGISTRY — adding a schema requires no changes
here.

Side effect: writes one .html file to the output directory.
"""

import base64
import csv
from datetime import date
from pathlib import Path

import pandas as pd

import config
import narrative


def export_html(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    schema: str,
    output_dir: Path,
    run_ids: list[str] | None = None,
) -> Path:
    """
    Generate and save the self-contained HTML report.

    Parameters:
        clean_df (pd.DataFrame): clean DataFrame for this run
        results (dict): analysis results, including 'anomalies'
        chart_paths (list[Path]): four chart .png paths from visualise()
        schema (str): a schema name from config.SCHEMA_REGISTRY
        output_dir (Path): directory to write the report to
        run_ids (list[str] | None): run UUIDs, normalised to a list at
            the pipeline boundary (main._run_pipeline) — one for
            single-file runs, one per file for batch runs. Used to
            include this run's quality-log entries as the report's
            Data Quality note. None omits the section.

    Returns:
        Path: path to the saved .html file

    Assumptions:
        - All paths in chart_paths exist on disk
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    narrative_text = narrative.build_narrative(results, clean_df, schema)
    stats_html = _render_stats_table(results, clean_df, cfg, run_ids)
    anomaly_html = _render_anomaly_summary(results)
    quality_html = _render_quality_note(run_ids)
    power_curve_html = (
        _render_power_curve_table(results["power_curve"], cfg)
        if "power_curve" in results else ""
    )
    images_b64 = [_encode_image(p) for p in chart_paths]

    chart_titles = [
        "Daily Power Trend",
        "Power vs Secondary Metric",
        "Monthly Mean Power",
        "Power Output with Anomalies Highlighted",
    ]

    html = _build_html(
        narrative_text, stats_html, anomaly_html, quality_html,
        power_curve_html, images_b64, chart_titles, schema,
    )

    base_filename = f"report_{date.today().isoformat()}.html"
    out_path = output_dir / base_filename

    # Unique-per-day filenames — Invariant 6: never overwrite a
    # previous report (same counter pattern as export.py)
    counter = 1
    while out_path.exists():
        filename = f"report_{date.today().isoformat()}_{counter}.html"
        out_path = output_dir / filename
        counter += 1

    out_path.write_text(html, encoding="utf-8")

    return out_path


def _render_quality_note(run_ids: list[str] | None) -> str:
    """
    Build the Data Quality note: cleaning decisions logged for the
    given run IDs, grouped by issue type and action taken.

    Parameters:
        run_ids (list[str] | None): current run UUIDs. None or empty
            yields a note saying no log data is attached.

    Returns:
        str: HTML block, either a summary table or a plain paragraph
    """
    run_ids = run_ids or []
    if not run_ids or not config.LOG_PATH.exists():
        return "<p>No data quality log entries are attached to this report.</p>"

    with open(config.LOG_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            r for r in reader
            if r.get(config.LOG_FIELD_RUN_ID) in run_ids
            and int(r.get(config.LOG_FIELD_ROW_COUNT, 0) or 0) > 0
        ]

    if not rows:
        return (
            "<p>Data quality checks ran for this report; no cleaning "
            "actions were required — all rows passed validation.</p>"
        )

    counts: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r[config.LOG_FIELD_ISSUE_TYPE], r[config.LOG_FIELD_ACTION_TAKEN])
        counts[key] = counts.get(key, 0) + int(r[config.LOG_FIELD_ROW_COUNT])

    action_labels = {
        "dropped": "rows dropped",
        "filled_median": "values filled with column median",
        "coerced": "values coerced to numeric",
        "flagged": "rows flagged for review",
    }
    issue_labels = {
        "duplicate": "duplicate rows",
        "null": "missing values",
        "type_coercion": "non-numeric entries",
        "date_parse_failure": "date parsing failures",
    }
    rows_html = "".join(
        f"<tr><td>{issue_labels.get(issue, issue)}</td>"
        f"<td>{count:,} {action_labels.get(action, action)}</td></tr>"
        for (issue, action), count in sorted(counts.items())
    )
    return (
        "<table><thead><tr><th>Cleaning Check</th>"
        f"<th>Rows Affected</th></tr></thead><tbody>{rows_html}</tbody></table>"
    )


# ── Internal helpers ──────────────────────────────────────────────


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


def _render_stats_table(
    results: dict,
    clean_df: pd.DataFrame,
    cfg: dict,
    run_ids: list[str] | None,
) -> str:
    """
    Build an HTML table of headline statistics.

    Rows come from the shared builder in narrative.py — identical
    row set and order as the Excel Summary sheet; only the value
    formatting differs (percent-suffixed ratio, thousands-comma
    counts).

    Parameters:
        results (dict): analysis results dict
        clean_df (pd.DataFrame): the clean DataFrame for this run
        cfg (dict): schema config from SCHEMA_REGISTRY
        run_ids (list[str] | None): normalised run IDs; more than
            one adds the Source Files Processed row

    Returns:
        str: HTML <tr> rows for the statistics table body
    """
    ratio_rows = {
        label: value
        for label, value in narrative.build_headline_stats(
            results, clean_df, cfg, run_ids
        )
    }
    ratio_label = f"Mean {cfg['ratio_label']}"

    def _fmt(label: str, value: float | int) -> str:
        if label == ratio_label:
            return f"{value:.1f}%"
        if isinstance(value, int) and value >= 1000:
            return f"{value:,}"
        return f"{value:g}"

    return "".join(
        f"<tr><td>{label}</td><td>{_fmt(label, value)}</td></tr>"
        for label, value in ratio_rows.items()
    )


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
    parts = [
        f"{count} {label.replace('_', ' ')}"
        for label, count in counts.items()
    ]
    return (
        f"<p>{len(anomalies)} anomalies flagged: {', '.join(parts)}.</p>"
    )


def _render_power_curve_table(power_curve_df: pd.DataFrame, cfg: dict) -> str:
    """
    Build the measured power curve table (IEC 61400-12-1 bins), with
    the data-sufficiency flag rendered as Yes/No. Headers come from
    narrative.power_curve_headers — one definition shared with the
    Excel sheet.

    Parameters:
        power_curve_df (pd.DataFrame): analyse's power-curve result
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        str: complete HTML section, or "" for an empty curve
    """
    if power_curve_df.empty:
        return ""

    headers = narrative.power_curve_headers(cfg)
    bin_header = narrative.power_curve_bin_header(cfg)

    header_cells = f"<th>{bin_header}</th>" + "".join(
        f"<th>{label}</th>" for label in headers.values()
    )
    rows_html = "".join(
        f"<tr><td>{interval}</td>"
        + f"<td>{row['mean_secondary']:.2f}</td>"
        + f"<td>{row['mean_primary']:,.1f}</td>"
        + f"<td>{row['mean_reference']:,.1f}</td>"
        + f"<td>{int(row['count']):,}</td>"
        + f"<td>{'Yes' if row['sufficient'] else 'No'}</td></tr>"
        for interval, row in power_curve_df.iterrows()
    )
    section = config.POWER_CURVE_SHEET_NAME
    return (
        f"<h2>{section}</h2>"
        f"<table><thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )


def _build_html(
    narrative_text: str,
    stats_rows_html: str,
    anomaly_html: str,
    quality_html: str,
    power_curve_html: str,
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
        quality_html (str): data quality note HTML block
        power_curve_html (str): measured power curve section, or ""
            when the schema has no power-curve analysis
        images_b64 (list[str]): base64 data URIs, one per chart
        chart_titles (list[str]): plain-English titles, same order
        schema (str): active schema name — used via the registry's
                      asset_label in the page title

    Returns:
        str: complete, valid, self-contained HTML document
    """
    schema_label = config.SCHEMA_REGISTRY[schema]["asset_label"]
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

  <h2>Data Quality</h2>
  {quality_html}

  {power_curve_html}

  <h2>Charts</h2>
  {charts_html}

  <footer>Generated by Energy Operations Data Dashboard</footer>
</body>
</html>"""
