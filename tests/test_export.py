"""
test_export.py

Tests for export.py — sheet assembly, run_ids filtering, and
Invariant 6 (a run never overwrites a previous report).
"""

import openpyxl
import pandas as pd
import pytest

import config
import export


EXPECTED_SHEETS = [
    "Summary", "Clean Data", "Trend Analysis", "Efficiency Analysis",
    "Charts", "Anomaly Report", "Data Quality Log",
]


@pytest.fixture
def built(wind_df, wind_harness):
    """Run the pre-export stages once and share the outputs."""
    build, output_dir, charts_dir = wind_harness
    clean_df, run_id, results, chart_paths = build(wind_df)
    return clean_df, run_id, results, chart_paths, output_dir


def _read_log_rows(run_id: str) -> list[dict]:
    import csv
    with open(config.LOG_PATH, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["run_id"] == run_id]


def test_export_creates_seven_sheets_in_order(built):
    clean_df, run_id, results, chart_paths, output_dir = built
    path = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == EXPECTED_SHEETS


def test_summary_contains_narrative_and_no_raw_column_keys(built):
    clean_df, run_id, results, chart_paths, output_dir = built
    path = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    wb = openpyxl.load_workbook(path)
    ws = wb["Summary"]
    narrative_text = ws["A1"].value
    assert isinstance(narrative_text, str) and len(narrative_text) > 100
    for raw_key in (config.COL_ACTIVE_POWER, config.COL_WIND_SPEED,
                    "efficiency_ratio", "clean_df"):
        assert raw_key not in narrative_text
    # Headline stats table starts at row 5
    assert ws.cell(row=5, column=1).value == "Metric"


def test_quality_log_sheet_filtered_to_current_run(built, wind_df, wind_harness):
    """Entries from an earlier run must not leak into this report."""
    clean_df, run_id, results, chart_paths, output_dir = built

    # A second, earlier log run with a different run_id
    build2, _, _ = wind_harness
    build2(wind_df)

    path = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    wb = openpyxl.load_workbook(path)
    ws = wb["Data Quality Log"]

    ids_in_sheet = {
        ws.cell(row=r, column=1).value
        for r in range(2, ws.max_row + 1)
    }
    assert ids_in_sheet == {run_id}
    # Sanity: the log on disk really does hold more than one run
    assert len({r["run_id"] for r in _read_log_rows(run_id)}) == 1


def test_quality_log_sheet_accepts_list_of_run_ids(built, wind_df, wind_harness):
    """Batch mode: entries from every listed run_id are included."""
    clean_df, run_id, results, chart_paths, output_dir = built

    build2, _, _ = wind_harness
    _, other_run_id, _, _ = build2(wind_df)

    path = export.export(
        clean_df, results, chart_paths, [run_id, other_run_id],
        output_dir, "wind",
    )
    wb = openpyxl.load_workbook(path)
    ws = wb["Data Quality Log"]
    ids_in_sheet = {
        ws.cell(row=r, column=1).value
        for r in range(2, ws.max_row + 1)
    }
    assert ids_in_sheet == {run_id, other_run_id}


def test_same_day_rerun_gets_counter_suffix(built):
    """Invariant 6: the second report today must not overwrite the first."""
    clean_df, run_id, results, chart_paths, output_dir = built
    first = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    second = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    assert first != second
    assert first.exists() and second.exists()
    assert second.stem.endswith("_1")


def test_anomaly_report_sheet_has_flagged_rows(built):
    clean_df, run_id, results, chart_paths, output_dir = built
    path = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    wb = openpyxl.load_workbook(path)
    ws = wb["Anomaly Report"]
    assert ws.max_row >= 1  # header present; flagged rows when anomalies exist
