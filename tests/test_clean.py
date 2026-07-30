"""Tests for clean.py — deduplication, coercion, nulls, dates."""

import clean
import config


def test_clean_removes_duplicates(wind_df_with_issues):
    before = len(wind_df_with_issues)
    clean_df, _ = clean.clean(wind_df_with_issues, schema="wind")
    assert len(clean_df) < before


def test_clean_returns_correct_dtypes(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    assert clean_df[config.COL_DATETIME].dtype.kind == "M"  # datetime64
    assert clean_df[config.COL_ACTIVE_POWER].dtype.kind == "f"  # float


def test_clean_drops_null_critical_column(wind_df_with_issues):
    """Rows with nulls in critical columns are dropped, not filled."""
    clean_df, _ = clean.clean(wind_df_with_issues, schema="wind")
    assert clean_df[config.COL_ACTIVE_POWER].isna().sum() == 0


def test_clean_returns_valid_run_id(wind_df):
    import uuid
    _, run_id = clean.clean(wind_df, schema="wind")
    uuid.UUID(run_id)  # raises ValueError if not a valid UUID — test fails if so


def test_clean_appends_to_log(wind_df, tmp_path, monkeypatch):
    """clean() appends entries to the quality log without truncating it."""
    log_path = tmp_path / "data_quality.log"
    monkeypatch.setattr(config, "LOG_PATH", log_path)

    clean.clean(wind_df, schema="wind")
    first_line_count = len(log_path.read_text().splitlines())

    clean.clean(wind_df, schema="wind")
    second_line_count = len(log_path.read_text().splitlines())

    assert second_line_count > first_line_count
