# Code Standards

## General

- Keep modules small and single-purpose. One module, one job.
  If a module needs a comment to explain what a section of it
  does, that section should be its own function.
- Fix root causes. Do not layer workarounds on top of bad data
  or broken logic.
- Do not mix unrelated concerns in one function or module.
- Explicit over implicit. If something is dropped, coerced, or
  skipped — print it to the terminal and record it in the log.

## Python

- Target Python 3.10+. Use type hints on all function signatures.
- Avoid bare `except`. Catch specific exception types and re-raise
  with a plain-English message at the module boundary.
- Validate all external input (CSV content, CLI arguments) at the
  system boundary — in `ingest.py` and `main.py` — before passing
  data downstream.
- Do not use mutable default arguments. Do not use global state.
- Do not modify DataFrames in place. Return new DataFrames or
  explicit `.copy()` where mutation is necessary.

## Functions

- Every function must have a docstring. Minimum content:
  - What the function does (one sentence)
  - Parameters: name, type, and meaning
  - Return value: type and meaning
  - Assumptions: what the function expects to be true about
    its inputs
- Functions must do one thing. A function that needs an internal
  comment to explain a section should split that section out.
- Functions must not produce side effects beyond their documented
  return value, with two explicit exceptions:
  - `clean.py` functions append to `logs/data_quality.log`
  - `export.py` and `visualise.py` functions write to `output/`
  Both are documented in their respective module docstrings.

## Configuration

- All column names, file paths, numeric thresholds, date format
  strings, and log field names live in `config.py` only.
- Reference column names using their constant:
  `config.COL_ACTIVE_POWER`, not `"LV ActivePower (kW)"`.
- When adding a new constant, add it to `config.py` first, then
  reference the constant. Never the other way around.
- Do not rename existing constants without updating every reference
  across all modules.

## Quality Log Standards

- Every log entry written by `clean.py` must include:
  - `run_id`: a UUID generated once at the start of each run
  - `run_timestamp`: ISO 8601 datetime of the run start
  - `column`: the column the issue was found in (or `"row"` for
    whole-row operations like deduplication)
  - `issue_type`: one of `duplicate`, `null`, `type_coercion`,
    `date_parse_failure`
  - `row_count`: number of rows affected
  - `action_taken`: one of `dropped`, `filled_median`, `coerced`,
    `flagged`
- Log entries are appended as CSV rows to `logs/data_quality.log`.
  The file is never truncated. If the file does not exist, create
  it with a header row on first write.

## CLI and Terminal Output

- Use `argparse` for all CLI argument handling. Do not read
  `sys.argv` directly outside of `main.py`.
- Print stage markers in this exact format:
  `[LOAD]`, `[CLEAN]`, `[ANALYSE]`, `[EXPORT]`
- Print counts on a single line immediately after each stage:
  `[CLEAN] 52,608 rows in → 51,943 rows clean (665 dropped)`
- Print the full output path on successful completion:
  `Report saved → output/report_2026-05-07.xlsx`
- Never let a Python traceback reach the user. Catch at the
  top level in `main.py` and print a plain-English message with
  enough context to diagnose the problem.

## Date Parsing

- Always attempt the primary format first:
  `pd.to_datetime(series, format=config.DATE_FORMAT)`
  where `DATE_FORMAT = "%Y-%m-%d %H:%M:%S"`.
- If the primary parse raises an exception, re-attempt with
  `pd.to_datetime(series, infer_datetime_format=True)`.
- If the fallback fires, print a terminal warning immediately:
  `[WARN] Date format inferred — verify output timestamps`
- If both fail, raise a descriptive error and exit. Do not silently
  produce a column of NaT values.
- After parsing, the `COL_DATETIME` column must be dtype `datetime64`
  before the DataFrame is passed to any downstream module.

## Efficiency Calculations

- Before computing any efficiency ratio, filter the working DataFrame
  to operational rows only:
  `df = df[(df[config.COL_THEORETICAL] > 0) & (df[config.COL_ACTIVE_POWER] > 0)]`
- Do not replace zero values with NaN or a sentinel — exclude the
  rows entirely so they cannot affect any downstream statistic.
- Print the excluded count immediately after filtering:
  `[ANALYSE] N rows excluded from efficiency (zero theoretical or non-positive output)`
- Never compute a ratio on a DataFrame that has not had this filter
  applied.

## Summary Sheet Narrative

- The Summary sheet must open with a narrative paragraph before any
  tables or numbers appear.
- The paragraph must be generated programmatically from real computed
  values — not hardcoded placeholder text.
- Minimum content: total operational hours analysed, mean active power
  output (kW), overall efficiency ratio (%), and one notable pattern
  derived from the data (e.g. peak output month, dominant wind
  direction quadrant).
- Length: 3–5 sentences. Written for a non-technical reader.
- No raw column key names, Python variable names, or numeric indices
  may appear anywhere on the Summary sheet. Use plain-English labels.

## File Organisation

- `main.py` — Project root. Entry point only.
- `ingest.py` — Project root. Load and validate.
- `clean.py` — Project root. Clean and log.
- `analyse.py` — Project root. Statistics and aggregations.
- `visualise.py` — Project root. Chart generation.
- `export.py` — Project root. Excel assembly.
- `config.py` — Project root. All constants. No logic.
- `context/` — All `.md` reference documents. Never modified
  by the pipeline.
- `data/` — Input CSVs only. Never written to.
- `output/` — Generated `.xlsx` reports.
- `output/charts/` — Generated `.png` chart figures.
- `logs/` — `data_quality.log`. Append-only.
- `requirements.txt` — Project root. Pinned dependencies.
- `README.md` — Project root. Usage documentation.
