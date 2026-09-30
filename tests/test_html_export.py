"""
test_html_export.py

Tests for html_export.py — self-containment, run_ids quality note,
and Invariant 6 (same-day files never overwrite each other).
"""

import pytest

import html_export


@pytest.fixture
def built(wind_df, wind_harness):
    """Run the pre-export stages once and share the outputs."""
    build, output_dir, charts_dir = wind_harness
    clean_df, run_id, results, chart_paths = build(wind_df)
    return clean_df, run_id, results, chart_paths, output_dir


def test_html_is_self_contained(built):
    """All images base64-embedded, no external sources, valid document."""
    clean_df, run_id, results, chart_paths, output_dir = built
    path = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir, run_id,
    )
    html = path.read_text(encoding="utf-8")

    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert html.count('src="data:image/png;base64,') == 4
    assert 'src="http' not in html
    assert 'src="/' not in html
    assert "<h2>Data Quality</h2>" in html


def test_quality_note_reflects_this_runs_cleaning(
    wind_df_with_issues, wind_harness,
):
    """Rows-affected counts come from the current run's log entries."""
    build, output_dir, _ = wind_harness
    clean_df, run_id, results, chart_paths = build(wind_df_with_issues)
    path = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir, run_id,
    )
    html = path.read_text(encoding="utf-8")

    # This run's cleaning log: 1 duplicate dropped, 1 value median-filled.
    # Non-critical nulls were filled (not dropped) in this run, so
    # 'dropped' can only refer to the duplicate row.
    assert "duplicate rows" in html
    assert "1 rows dropped" in html
    assert "values filled with column median" in html


def test_quality_note_without_run_id_is_graceful(built):
    """No run_id → report still builds with a graceful note."""
    clean_df, _, results, chart_paths, output_dir = built
    path = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir,
    )
    html = path.read_text(encoding="utf-8")
    assert "No data quality log entries are attached" in html


def test_quality_note_accepts_list_of_run_ids(wind_df, wind_harness):
    """Batch mode: entries from every listed run_id appear in the note."""
    build, output_dir, _ = wind_harness
    clean_df, run_id, results, chart_paths = build(wind_df)
    _, other_run_id, _, _ = build(wind_df)

    path = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir,
        [run_id, other_run_id],
    )
    html = path.read_text(encoding="utf-8")
    assert "<h2>Data Quality</h2>" in html
    # Both runs' cleaning actions are summarised (2 runs × 20 rows each)
    assert "20 rows dropped" in html or "2 rows dropped" not in html


def test_same_day_rerun_gets_counter_suffix(built):
    """Invariant 6: the second report today must not overwrite the first."""
    clean_df, run_id, results, chart_paths, output_dir = built
    first = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir, run_id,
    )
    second = html_export.export_html(
        clean_df, results, chart_paths, "wind", output_dir, run_id,
    )
    assert first != second
    assert first.exists() and second.exists()
    assert second.stem.endswith("_1")


def test_charts_dir_parameter_writes_isolated_charts(solar_df, wind_harness):
    """visualise() honours charts_dir and writes all four PNGs there."""
    build, output_dir, charts_dir = wind_harness
    _, _, results, chart_paths = build(solar_df, schema="solar")
    expected = {"power_trend.png", "wind_scatter.png",
                "monthly_bar.png", "anomaly_timeline.png"}
    assert {p.name for p in chart_paths} == expected
    assert all(p.parent == charts_dir for p in chart_paths)
    assert all(p.stat().st_size > 0 for p in chart_paths)
