"""
export.py

Owns Excel workbook assembly and file export.
Receives the clean DataFrame, analysis results dict, chart image
paths, run_id(s), schema, and output directory. Assembles a
seven-sheet .xlsx workbook and returns the output file path.

Fully schema-agnostic: sheet headers, narrative text, and statistics
labels come from config.SCHEMA_REGISTRY — adding a schema requires
no changes here.

Side effect: writes one .xlsx file to output/.
"""

import csv
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows

import config
import narrative


def _efficiency_headers(cfg: dict) -> dict:
    """
    Build the Efficiency Analysis sheet's plain-English headers from
    the registry: display names for the efficiency DataFrame's own
    columns plus the ratio column.

    Parameters:
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        dict: mapping of raw column names to display headers
    """
    ratio_name = cfg["ratio_name"]
    ratio_label = cfg["ratio_label"]
    seen: set[str] = set()
    eff_cols: list[str] = []
    for col in (cfg["datetime_col"], cfg["primary_power_col"],
                cfg["secondary_col"], cfg["reference_col"], ratio_name):
        if col not in seen:
            seen.add(col)
            eff_cols.append(col)
    return {
        col: (ratio_label if col == ratio_name
              else cfg["display_names"].get(col, col))
        for col in eff_cols
    }


def export(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    run_ids: list[str],
    output_dir: Path,
    schema: str,
) -> Path:
    """
    Assemble and save the seven-sheet Excel report.

    Parameters:
        clean_df (pd.DataFrame): cleaned SCADA DataFrame from clean.clean()
        results (dict[str, pd.DataFrame]): analysis results from
            analyse.analyse(). Must contain keys: 'stats', 'efficiency',
            'monthly', 'daily', 'daily_mean', 'distribution', 'anomalies'.
        chart_paths (list[Path]): list of four .png paths from
            visualise.visualise(), in order:
            [power_trend.png, wind_scatter.png, monthly_bar.png,
             anomaly_timeline.png]
        run_ids (list[str]): run UUIDs from clean.clean(), normalised
            to a list at the pipeline boundary (main._run_pipeline) —
            one for single-file runs, one per file for batch runs. The
            quality log is filtered to entries matching any of them.
        output_dir (Path): directory to write the report to
        schema (str): a schema name from config.SCHEMA_REGISTRY

    Returns:
        Path: full path of the written .xlsx file,
              e.g. output/report_2026-05-20.xlsx

    Assumptions:
        - output_dir exists
        - All four chart .png files in chart_paths exist on disk
        - logs/data_quality.log exists and contains entries for run_ids
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    wb = Workbook()
    wb.remove(wb.active)  # Remove the default empty sheet

    # Add sheets in required order
    _write_summary(
        wb.create_sheet("Summary"), results, clean_df, cfg, run_ids, schema
    )
    _write_dataframe(
        wb.create_sheet("Clean Data"),
        clean_df,
        plain_headers=cfg["display_names"],
    )
    _write_trend_analysis(wb.create_sheet("Trend Analysis"), results, cfg)
    _write_efficiency_analysis(
        wb.create_sheet("Efficiency Analysis"), results["efficiency"], cfg
    )
    _write_charts(wb.create_sheet("Charts"), chart_paths)
    _write_anomalies(wb.create_sheet("Anomaly Report"), results["anomalies"], cfg)
    _write_quality_log(wb.create_sheet("Data Quality Log"), run_ids)

    # Build timestamped filename — Invariant 6
    base_filename = f"report_{date.today().isoformat()}"
    filename = f"{base_filename}.xlsx"
    out_path = output_dir / filename

    counter = 1
    while out_path.exists():
        filename = f"{base_filename}_{counter}.xlsx"
        out_path = output_dir / filename
        counter += 1

    wb.save(out_path)

    return out_path


# ── Narrative helpers ─────────────────────────────────────────────



def _write_summary(
    ws, results: dict, clean_df: pd.DataFrame, cfg: dict,
    run_ids: list[str], schema: str,
) -> None:
    """
    Write the Summary sheet with narrative paragraph and statistics table.

    Component 1 (rows 1-3): Narrative paragraph merged across A1:F3.
    Component 2 (rows 5+): Headline statistics table with plain-English
    labels and styled header. Batch runs add a Source Files Processed
    row equal to the number of run IDs.

    Parameters:
        ws: openpyxl Worksheet
        results (dict): analysis results from analyse.analyse()
        clean_df (pd.DataFrame): cleaned SCADA DataFrame
        cfg (dict): schema config from config.SCHEMA_REGISTRY
        run_ids (list[str]): current run ID, or per-file run IDs in
                             batch mode
        schema (str): active schema name — build_narrative keys the
                      registry lookup by name
    """
    # ── Component 1: Narrative paragraph ────────────────────────────
    narrative_text = narrative.build_narrative(results, clean_df, schema)

    ws.merge_cells("A1:F3")
    cell = ws.cell(row=1, column=1, value=narrative_text)
    cell.alignment = Alignment(wrap_text=True, vertical="top")

    # ── Component 2: Headline statistics table (rows 5 onward) ──────
    # Rows come from the shared builder in narrative.py — identical
    # row set and order as the HTML report's table
    stats_table = narrative.build_headline_stats(
        results, clean_df, cfg, run_ids
    )

    ws.cell(row=5, column=1, value="Metric")
    ws.cell(row=5, column=2, value="Value")
    for offset, (label, value) in enumerate(stats_table, start=1):
        ws.cell(row=5 + offset, column=1, value=label)
        ws.cell(row=5 + offset, column=2, value=value)

    # Style the header row (row 5)
    _style_header_row(ws, row_num=5, col_count=2)


def _write_dataframe(
    ws,
    df: pd.DataFrame,
    plain_headers: dict,
) -> None:
    """
    Write a DataFrame to a worksheet with plain-English headers.

    Parameters:
        ws: openpyxl Worksheet to write to
        df (pd.DataFrame): DataFrame to write
        plain_headers (dict): mapping of raw column names to
                              plain-English display labels
    """
    display_df = df.rename(columns=plain_headers)

    for row_idx, row in enumerate(
        dataframe_to_rows(display_df, index=True, header=True), start=1
    ):
        ws.append(row)
        if row_idx == 1:
            _style_header_row(ws, row_num=1, col_count=len(row))


def _write_trend_analysis(ws, results: dict, cfg: dict) -> None:
    """
    Write the Trend Analysis sheet with monthly and daily sections.

    Parameters:
        ws: openpyxl Worksheet
        results (dict): analysis results from analyse.analyse()
        cfg (dict): schema config from SCHEMA_REGISTRY
    """
    monthly_df = results["monthly"]
    daily_df = results["daily"]

    # ── Monthly section ────────────────────────────────────────────
    ws.cell(row=1, column=1, value="Monthly Mean Power").font = Font(
        bold=True, size=11
    )

    header_row = 2
    monthly_headers = ["Date", "Power"]
    ws.append(monthly_headers)
    _style_header_row(ws, row_num=header_row, col_count=len(monthly_headers))

    for idx, (date_val, power) in enumerate(monthly_df.iterrows()):
        ws.append([str(date_val.date()), round(power.iloc[0], 2)])

    # ── Daily section ──────────────────────────────────────────────
    daily_start_row = len(monthly_df) + 3 + 1  # monthly rows + blank + header

    ws.cell(row=daily_start_row, column=1, value="Daily Total Power").font = (
        Font(bold=True, size=11)
    )

    daily_header_row = daily_start_row + 1
    daily_headers = ["Date", "Power"]
    for col_idx, header in enumerate(daily_headers, start=1):
        ws.cell(row=daily_header_row, column=col_idx, value=header)
    _style_header_row(ws, row_num=daily_header_row, col_count=len(daily_headers))

    for row_offset, (date_val, power) in enumerate(daily_df.iterrows(), start=1):
        row_num = daily_header_row + row_offset
        ws.cell(row=row_num, column=1, value=str(date_val.date()))
        ws.cell(row=row_num, column=2, value=round(power.iloc[0], 2))


def _write_efficiency_analysis(
    ws, efficiency_df: pd.DataFrame, cfg: dict
) -> None:
    """
    Write the efficiency/conversion DataFrame to the sheet.

    Parameters:
        ws: openpyxl Worksheet
        efficiency_df (pd.DataFrame): efficiency results
        cfg (dict): schema config from config.SCHEMA_REGISTRY
    """
    _write_dataframe(ws, efficiency_df, plain_headers=_efficiency_headers(cfg))


def _write_charts(ws, chart_paths: list[Path]) -> None:
    """
    Embed chart .png files as images into the Charts sheet.

    Parameters:
        ws: openpyxl Worksheet
        chart_paths (list[Path]): list of .png file paths
    """
    anchors = ["A1", "A32", "A62", "A92"]
    titles = [
        "Daily Power Trend",
        "Power vs Secondary Metric",
        "Monthly Mean Power",
        "Anomaly Timeline",
    ]

    for path, anchor, title in zip(chart_paths, anchors, titles):
        row_num = int(anchor[1:]) if len(anchor) > 2 else int(anchor[1])
        ws.cell(row=row_num, column=1, value=title).font = Font(
            bold=True, size=11
        )

        img = XLImage(str(path))
        img.width = 700
        img.height = 300
        img_anchor = f"A{row_num + 2}"
        ws.add_image(img, img_anchor)


def _write_anomalies(ws, anomalies_df: pd.DataFrame, cfg: dict) -> None:
    """
    Write the anomaly report to the Anomaly Report sheet.

    Parameters:
        ws: openpyxl Worksheet
        anomalies_df (pd.DataFrame): output of detect.detect()
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        None
    """
    headers = {
        cfg["datetime_col"]: "Timestamp",
        cfg["primary_power_col"]: cfg["primary_label"],
        "anomaly_type": "Detection Method",
        "deviation": "Deviation from Mean",
    }
    _write_dataframe(ws, anomalies_df, plain_headers=headers)


def _write_quality_log(ws, run_ids: list[str]) -> None:
    """
    Write quality log entries for the current run to the sheet.

    Parameters:
        ws: openpyxl Worksheet
        run_ids (list[str]): run UUIDs, normalised to a list at the
            pipeline boundary — entries matching any listed ID are
            included
    """
    log_path: Path = config.LOG_PATH

    with open(log_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r[config.LOG_FIELD_RUN_ID] in run_ids]

    # Write header
    headers = config.LOG_FIELDS
    ws.append(headers)
    _style_header_row(ws, row_num=1, col_count=len(headers))

    # Write matching rows
    for row in rows:
        ws.append([row[field] for field in headers])


def _style_header_row(ws, row_num: int, col_count: int) -> None:
    """
    Apply header styling to a row in a worksheet.

    Style: dark navy background (#1B3A5C), white bold text,
    centre-aligned.

    Parameters:
        ws: openpyxl Worksheet
        row_num (int): 1-based row number to style
        col_count (int): number of columns to style (starting from col 1)
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
