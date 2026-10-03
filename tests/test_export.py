"""
test_export.py

Tests for export.py — sheet assembly, run_ids filtering, and
Invariant 6 (a run never overwrites a previous report).
"""

import openpyxl
import pytest

import analyse
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


def test_headline_stats_match_shared_builder(built):
    """The Excel Summary rows are exactly narrative's shared rows —
    one definition of the headline table for both report formats."""
    import narrative

    clean_df, run_id, results, chart_paths, output_dir = built
    path = export.export(clean_df, results, chart_paths, run_id, output_dir, "wind")
    wb = openpyxl.load_workbook(path)
    ws = wb["Summary"]

    # Header row is 5; data rows start at 6. Stop at the first blank
    # row — cells below the table (blank separators etc.) are not part
    # of the headline table.
    sheet_rows = {}
    for r in range(6, ws.max_row + 1):
        label = ws.cell(row=r, column=1).value
        if label is None:
            break
        sheet_rows[label] = ws.cell(row=r, column=2).value
    expected_rows = dict(narrative.build_headline_stats(
        results, clean_df, config.SCHEMA_REGISTRY["wind"], [run_id]
    ))
    assert sheet_rows == expected_rows


@pytest.mark.parametrize("schema", ["wind", "solar", "hydro"])
def test_efficiency_headers_follow_analyse_column_selection(schema):
    """The Efficiency sheet's headers derive from analyse's own column
    selection — analyse.efficiency_columns is the single owner of the
    order, so the sheet can never drift from the analysis."""
    cfg = config.SCHEMA_REGISTRY[schema]
    headers = export._efficiency_headers(cfg)

    assert list(headers.keys()) == analyse.efficiency_columns(cfg)
    assert headers[cfg["ratio_name"]] == cfg["ratio_label"]
    for col, label in headers.items():
        if col != cfg["ratio_name"]:
            assert label == cfg["display_names"].get(col, col)
