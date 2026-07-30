# Unit 12: Test Suite

## Goal

Add automated `pytest` coverage for the pipeline's core logic —
schema validation, cleaning rules, efficiency exclusion, and anomaly
detection — plus one end-to-end smoke test on synthetic data, so
regressions are caught automatically instead of relying on manual
verification checklists.

---

## Implementation

### 1. Install pytest

```bash
pip install pytest
```

Create `requirements-dev.txt` — testing dependencies are kept
separate from runtime dependencies so a production install doesn't
pull in test tooling:

```
pytest>=8.0,<9.0
```

---

### 2. `tests/` Structure

```
tests/
├── conftest.py          # shared fixtures
├── test_ingest.py
├── test_clean.py
├── test_analyse.py
├── test_detect.py
├── test_config.py
└── test_pipeline_e2e.py
```

No `tests/__init__.py` needed — pytest discovers test files by
naming convention (`test_*.py`), no package structure required.

---

### 3. `conftest.py` — Shared Fixtures

Build small, fully synthetic DataFrames in memory — do not depend
on the real Kaggle CSVs being present. This is what makes the suite
runnable in any environment, including CI, without a dataset.

```python
"""
conftest.py

Shared pytest fixtures: synthetic wind and solar DataFrames used
across the test suite. Fully synthetic — no dependency on real
Kaggle datasets being present in data/.
"""

import pandas as pd
import pytest
import config


@pytest.fixture
def wind_df() -> pd.DataFrame:
    """20 rows of synthetic wind SCADA data, 10-minute intervals."""
    timestamps = pd.date_range("2018-01-01", periods=20, freq="10min")
    return pd.DataFrame({
        config.COL_DATETIME: timestamps.strftime(config.DATE_FORMAT),
        config.COL_ACTIVE_POWER: [100.0 + i * 10 for i in range(20)],
        config.COL_WIND_SPEED: [5.0 + i * 0.2 for i in range(20)],
        config.COL_THEORETICAL: [120.0 + i * 10 for i in range(20)],
        config.COL_WIND_DIRECTION: [45.0 + i * 5 for i in range(20)],
    })


@pytest.fixture
def solar_df() -> pd.DataFrame:
    """20 rows of synthetic solar SCADA data, 15-minute intervals."""
    timestamps = pd.date_range("2020-05-15", periods=20, freq="15min")
    cfg = config.SCHEMA_REGISTRY["solar"]
    return pd.DataFrame({
        config.COL_SOLAR_DATETIME: timestamps.strftime(cfg["date_format"]),
        config.COL_PLANT_ID: ["4136001"] * 20,
        config.COL_SOURCE_KEY: ["INV001"] * 20,
        config.COL_DC_POWER: [200.0 + i * 15 for i in range(20)],
        config.COL_AC_POWER: [190.0 + i * 14 for i in range(20)],
        config.COL_DAILY_YIELD: [1000.0 + i * 50 for i in range(20)],
        config.COL_TOTAL_YIELD: [50000.0 + i * 50 for i in range(20)],
    })


@pytest.fixture
def wind_df_with_issues(wind_df) -> pd.DataFrame:
    """Wind DataFrame with a duplicate row, a null, and a bad string."""
    df = wind_df.copy()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # duplicate
    df.loc[5, config.COL_WIND_SPEED] = None                # null
    df.loc[6, config.COL_ACTIVE_POWER] = "N/A"              # bad string
    return df
```

---

### 4. `test_ingest.py`

```python
"""Tests for ingest.py — schema validation."""

import pytest
import ingest


def test_validate_schema_wind_passes(wind_df):
    """A valid wind DataFrame passes validation without raising."""
    ingest.validate_schema(wind_df, schema="wind")  # should not raise


def test_validate_schema_solar_passes(solar_df):
    """A valid solar DataFrame passes validation without raising."""
    ingest.validate_schema(solar_df, schema="solar")  # should not raise


def test_validate_schema_missing_column_raises(wind_df):
    """Removing a required column triggers SystemExit with a clear message."""
    broken = wind_df.drop(columns=["Wind Speed (m/s)"])
    with pytest.raises(SystemExit) as exc_info:
        ingest.validate_schema(broken, schema="wind")
    assert "Wind Speed (m/s)" in str(exc_info.value)


def test_validate_schema_wrong_schema_flags_all_missing(solar_df):
    """A solar DataFrame validated against the wind schema fails clearly."""
    with pytest.raises(SystemExit):
        ingest.validate_schema(solar_df, schema="wind")
```

---

### 5. `test_clean.py`

```python
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
```

---

### 6. `test_analyse.py`

```python
"""Tests for analyse.py — stats, efficiency, resampling, distribution."""

import config
import clean
import analyse


def test_efficiency_excludes_zero_theoretical(wind_df):
    df = wind_df.copy()
    df.loc[0, config.COL_THEORETICAL] = 0
    clean_df, _ = clean.clean(df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert (results["efficiency"][config.COL_THEORETICAL] > 0).all()


def test_monthly_has_datetime_index(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert results["monthly"].index.dtype.kind == "M"


def test_wind_distribution_shape(wind_df):
    clean_df, _ = clean.clean(wind_df, schema="wind")
    results = analyse.analyse(clean_df, schema="wind")
    assert len(results["distribution"]) <= config.WIND_DIRECTION_BINS


def test_solar_distribution_by_source_key(solar_df):
    clean_df, _ = clean.clean(solar_df, schema="solar")
    results = analyse.analyse(clean_df, schema="solar")
    assert "mean" in results["distribution"].columns
    assert "count" in results["distribution"].columns


def test_solar_efficiency_uses_conversion_ratio(solar_df):
    clean_df, _ = clean.clean(solar_df, schema="solar")
    results = analyse.analyse(clean_df, schema="solar")
    assert "conversion_ratio" in results["efficiency"].columns
```

---

### 7. `test_detect.py`

```python
"""Tests for detect.py — threshold and rolling-window anomaly detection."""

import config
import clean
import detect


def test_threshold_flags_extreme_outlier(wind_df):
    df = wind_df.copy()
    df.loc[10, config.COL_ACTIVE_POWER] = 10_000.0  # extreme spike
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert "threshold" in anomalies["anomaly_type"].values or \
           "both" in anomalies["anomaly_type"].values


def test_rolling_window_flags_sustained_drop(wind_df):
    df = wind_df.copy()
    # Drop a sustained block of values well below the mean
    df.loc[5:15, config.COL_ACTIVE_POWER] = 1.0
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert len(anomalies) > 0


def test_detect_excludes_non_operational_rows(wind_df):
    """Rows at or below min_primary are never flagged as anomalies."""
    df = wind_df.copy()
    df.loc[0, config.COL_ACTIVE_POWER] = 0.0
    clean_df, _ = clean.clean(df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert 0.0 not in anomalies[config.COL_ACTIVE_POWER].values


def test_detect_empty_result_does_not_crash(wind_df):
    """A dataset with no anomalies returns an empty DataFrame, no error."""
    clean_df, _ = clean.clean(wind_df, schema="wind")
    anomalies = detect.detect(clean_df, schema="wind")
    assert anomalies is not None  # empty is fine, None is not
```

---

### 8. `test_config.py`

```python
"""Sanity checks on the schema registry structure itself."""

import config

REQUIRED_KEYS = {
    "required_columns", "datetime_col", "date_format",
    "critical_columns", "median_fill_columns", "primary_power_col",
    "secondary_col", "reference_col", "ratio_name",
    "min_primary", "min_reference",
}


def test_both_schemas_present():
    assert "wind" in config.SCHEMA_REGISTRY
    assert "solar" in config.SCHEMA_REGISTRY


def test_wind_schema_has_all_required_keys():
    assert REQUIRED_KEYS.issubset(config.SCHEMA_REGISTRY["wind"].keys())


def test_solar_schema_has_all_required_keys():
    assert REQUIRED_KEYS.issubset(config.SCHEMA_REGISTRY["solar"].keys())


def test_anomaly_constants_exist():
    assert hasattr(config, "ANOMALY_STD_THRESHOLD")
    assert hasattr(config, "ANOMALY_ROLLING_WINDOW")
    assert hasattr(config, "ANOMALY_ROLLING_DROP_PCT")
    assert 0 < config.ANOMALY_ROLLING_DROP_PCT < 1
```

---

### 9. `test_pipeline_e2e.py` — Smoke Test

This is the highest-value test in the suite — it runs the actual
pipeline function used by `main.py`, on disk, using `tmp_path` so
nothing touches your real `data/`, `output/`, or `logs/` folders.

```python
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
```

**Note:** if `run_single()`'s signature differs slightly from what's
shown here (e.g. parameter order or a `fmt` argument that doesn't
exist yet), adjust the call to match the actual signature in
`main.py` — the test's intent (isolated, real pipeline run, assert
real files exist) matters more than the exact call shape.

---

## Dependencies

- `pytest >= 8.0, < 9.0` — install via `requirements-dev.txt`,
  kept separate from `requirements.txt` (test tooling is not a
  runtime dependency).

---

## Verify When Done

### Setup
- [ ] `requirements-dev.txt` exists with `pytest` pinned
- [ ] `pip install -r requirements-dev.txt` completes without errors
- [ ] `pytest --version` confirms installation

### Test Execution
- [ ] `pytest` run from the project root discovers and runs all
      six test files with zero collection errors
- [ ] All tests pass on a clean checkout — no dependency on real
      Kaggle CSVs, `data/`, or pre-existing `output/`/`logs/` content
- [ ] `pytest -v` shows individual test names and pass status for
      manual review

### Coverage Sanity
- [ ] At least one test per module: `ingest`, `clean`, `analyse`,
      `detect`, `config`
- [ ] The e2e smoke test passes and confirms real files are created
      in an isolated `tmp_path` — not in the real `output/` folder
- [ ] Re-running the full suite twice in a row produces identical
      results — no test leaves state that affects a later run

### Isolation
- [ ] After running `pytest`, `git status` shows no new or modified
      files in `data/`, `output/`, or `logs/` — confirms tests use
      `tmp_path` and `monkeypatch` correctly, not real project paths
- [ ] Tests do not require internet access or a real dataset file

### Code Standards
- [ ] Every test function has a one-line docstring or clear comment
      explaining what it verifies
- [ ] Fixtures in `conftest.py` are reused across files — no
      duplicated synthetic DataFrame construction
- [ ] No hardcoded column name strings in test files — fixtures
      and assertions reference `config.COL_*` constants
