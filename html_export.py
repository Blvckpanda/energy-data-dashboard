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
        "Daily Power Trend",
        "Power vs Secondary Metric",
        "Monthly Mean Power",
        "Power Output with Anomalies Highlighted",
    ]

    html = _build_html(
        narrative_text, stats_html, anomaly_html,
        images_b64, chart_titles, schema,
    )

    filename = f"report_{date.today().isoformat()}.html"
    out_path = output_dir / filename
    out_path.write_text(html, encoding="utf-8")

    return out_path


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

    # Use plain-English labels
    if cfg["primary_power_col"] == config.COL_ACTIVE_POWER:
        primary_label = "Active Power (kW)"
    else:
        primary_label = "AC Power (kW)"

    if cfg["ratio_name"] == "efficiency_ratio":
        ratio_label = "Efficiency"
    else:
        ratio_label = "Conversion Ratio"

    rows = [
        (f"Mean {primary_label}",
         f"{stats.loc['mean', cfg['primary_power_col']]:.2f}"),
        (f"Max {primary_label}",
         f"{stats.loc['max', cfg['primary_power_col']]:.2f}"),
        (f"Mean {ratio_label}",
         f"{efficiency[ratio_col].mean() * 100:.1f}%"),
        ("Total Rows Analysed",
         f"{len(efficiency):,}"),
    ]
    return "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>"
        for label, value in rows
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
