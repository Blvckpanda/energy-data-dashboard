"""
export.py

Owns Excel workbook assembly and file export.
Receives the clean DataFrame, analysis results dict, chart image
paths, run_id, schema, and output directory. Assembles a seven-sheet
.xlsx workbook and returns the output file path.

Schema-aware: headers, narrative text, and sheet naming come from
config.SCHEMA_REGISTRY and the schema-keyed header dicts below.

Side effect: writes one .xlsx file to output/.
"""

from pathlib import Path
from datetime import date
import csv

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment

import config
import narrative


# ── Plain-English Header Mappings (schema-keyed) ───────────────────
WIND_HEADERS = {
    config.COL_DATETIME:       "Timestamp",
    config.COL_ACTIVE_POWER:   "Active Power (kW)",
    config.COL_WIND_SPEED:     "Wind Speed (m/s)",
    config.COL_THEORETICAL:    "Theoretical Power (kWh)",
    config.COL_WIND_DIRECTION: "Wind Direction (°)",
}

SOLAR_HEADERS = {
    config.COL_SOLAR_DATETIME: "Timestamp",
    config.COL_PLANT_ID:       "Plant ID",
    config.COL_SOURCE_KEY:     "Inverter ID",
    config.COL_DC_POWER:       "DC Power (kW)",
    config.COL_AC_POWER:       "AC Power (kW)",
    config.COL_DAILY_YIELD:    "Daily Yield (kWh)",
    config.COL_TOTAL_YIELD:    "Total Yield (kWh)",
}

CLEAN_DATA_HEADERS = {
    "wind":  WIND_HEADERS,
    "solar": SOLAR_HEADERS,
}

WIND_EFF_HEADERS = {
    config.COL_DATETIME:       "Timestamp",
    config.COL_ACTIVE_POWER:   "Active Power (kW)",
    config.COL_WIND_SPEED:     "Wind Speed (m/s)",
    config.COL_THEORETICAL:    "Theoretical Power (kWh)",
    "efficiency_ratio":        "Efficiency Ratio",
}

SOLAR_EFF_HEADERS = {
    config.COL_SOLAR_DATETIME: "Timestamp",
    config.COL_SOURCE_KEY:     "Inverter ID",
    config.COL_DC_POWER:       "DC Power (kW)",
    config.COL_AC_POWER:       "AC Power (kW)",
    "conversion_ratio":        "Conversion Ratio",
}

EFFICIENCY_HEADERS = {
    "wind":  WIND_EFF_HEADERS,
    "solar": SOLAR_EFF_HEADERS,
}


def export(
    clean_df: pd.DataFrame,
    results: dict[str, pd.DataFrame],
    chart_paths: list[Path],
    run_id: str,
    output_dir: Path,
    schema: str,
) -> Path:
    """
    Assemble and save the seven-sheet Excel report.

    Parameters:
        clean_df (pd.DataFrame): cleaned SCADA DataFrame from clean.clean()
        results (dict[str, pd.DataFrame]): analysis results from
            analyse.analyse(). Must contain keys: 'stats', 'efficiency',
            'monthly', 'daily', 'distribution', 'anomalies'.
        chart_paths (list[Path]): list of four .png paths from
            visualise.visualise(), in order:
            [power_trend.png, wind_scatter.png, monthly_bar.png,
             anomaly_timeline.png]
        run_id (str): UUID from clean.clean(), used to filter the
            quality log to this run's entries only
        output_dir (Path): directory to write the report to
        schema (str): "wind" or "solar"

    Returns:
        Path: full path of the written .xlsx file,
              e.g. output/report_2026-05-20.xlsx

    Assumptions:
        - output_dir exists
        - All four chart .png files in chart_paths exist on disk
        - logs/data_quality.log exists and contains entries for run_id
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    wb = Workbook()
    wb.remove(wb.active)  # Remove the default empty sheet

    # Add sheets in required order
    _write_summary(wb.create_sheet("Summary"), results, clean_df, schema)
    _write_dataframe(
        wb.create_sheet("Clean Data"),
        clean_df,
        plain_headers=CLEAN_DATA_HEADERS[schema],
    )
    _write_trend_analysis(wb.create_sheet("Trend Analysis"), results, cfg)
    _write_efficiency_analysis(
        wb.create_sheet("Efficiency Analysis"), results["efficiency"], schema
    )
    _write_charts(wb.create_sheet("Charts"), chart_paths)
    _write_anomalies(wb.create_sheet("Anomaly Report"), results["anomalies"], cfg)
    _write_quality_log(wb.create_sheet("Data Quality Log"), run_id)

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
    ws, results: dict, clean_df: pd.DataFrame, schema: str
) -> None:
    """
    Write the Summary sheet with narrative paragraph and statistics table.

    Component 1 (rows 1-3): Narrative paragraph merged across A1:F3.
    Component 2 (rows 5+): Headline statistics table with plain-English
    labels and styled header.

    Parameters:
        ws: openpyxl Worksheet
        results (dict): analysis results from analyse.analyse()
        clean_df (pd.DataFrame): cleaned SCADA DataFrame
        schema (str): "wind" or "solar"
    """
    # ── Component 1: Narrative paragraph ────────────────────────────
    narrative_text = narrative.build_narrative(results, clean_df, schema)

    ws.merge_cells("A1:F3")
    cell = ws.cell(row=1, column=1, value=narrative_text)
    cell.alignment = Alignment(wrap_text=True, vertical="top")

    # ── Component 2: Headline statistics table (rows 5 onward) ──────
    stats = results["stats"]
    efficiency_df = results["efficiency"]
    cfg = config.SCHEMA_REGISTRY[schema]
    ratio_col = cfg["ratio_name"]
    primary = cfg["primary_power_col"]
    secondary = cfg["secondary_col"]

    # Build plain-English labels for stats columns
    if schema == "wind":
        primary_label = "Active Power (kW)"
        secondary_label = "Wind Speed (m/s)"
        ratio_label = "Mean Efficiency (%)"
    else:
        primary_label = "AC Power (kW)"
        secondary_label = "DC Power (kW)"
        ratio_label = "Mean Conversion Ratio (%)"

    stats_table = [
        ("Metric", "Value"),
        (f"Mean {primary_label}",
         round(stats.loc["mean", primary], 2)),
        (f"Max {primary_label}",
         round(stats.loc["max", primary], 2)),
        (f"Std Dev {primary_label}",
         round(stats.loc["std", primary], 2)),
        (f"Mean {secondary_label}",
         round(stats.loc["mean", secondary], 2)),
        (f"Max {secondary_label}",
         round(stats.loc["max", secondary], 2)),
        (ratio_label,
         round(efficiency_df[ratio_col].mean() * 100, 2)),
        ("Total Rows Analysed", len(efficiency_df)),
        ("Rows Excluded from Analysis",
         len(clean_df) - len(efficiency_df)),
    ]

    for row_idx, (label, value) in enumerate(stats_table, start=5):
        ws.cell(row=row_idx, column=1, value=label)
        ws.cell(row=row_idx, column=2, value=value)

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


def _write_efficiency_analysis(ws, efficiency_df: pd.DataFrame, schema: str) -> None:
    """
    Write the efficiency/conversion DataFrame to the sheet.

    Parameters:
        ws: openpyxl Worksheet
        efficiency_df (pd.DataFrame): efficiency results
        schema (str): "wind" or "solar"
    """
    _write_dataframe(ws, efficiency_df, plain_headers=EFFICIENCY_HEADERS[schema])


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


def _write_quality_log(ws, run_id: str) -> None:
    """
    Write quality log entries for the current run to the sheet.

    Parameters:
        ws: openpyxl Worksheet
        run_id (str): UUID identifying the current run
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
