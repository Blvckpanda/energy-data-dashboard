"""
End-to-end smoke test.

Runs the real run_single() pipeline function from main.py against
a small synthetic CSV, using pytest's tmp_path for full filesystem
isolation. Confirms the pipeline produces a report, charts, and a
log entry without errors — the closest thing to a real user run.
"""

from pathlib import Path
import pandas as pd
import main
import config


def test_run_single_produces_report(wind_df, tmp_path, monkeypatch):
    # Redirect all output paths into the isolated tmp_path
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "CHARTS_DIR", tmp_path / "output" / "charts")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "logs" / "data_quality.log")
    (tmp_path / "output" / "charts").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)

    csv_path = tmp_path / "synthetic_wind.csv"
    wind_df.to_csv(csv_path, index=False)

    main.run_single(csv_path, tmp_path / "output", schema="wind", fmt="excel")

    reports = list((tmp_path / "output").glob("report_*.xlsx"))
    charts = list((tmp_path / "output" / "charts").glob("*.png"))

    assert len(reports) == 1
    assert len(charts) == 4
    assert (tmp_path / "logs" / "data_quality.log").exists()
