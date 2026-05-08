# Architecture Context

## Stack

| Layer        | Technology           | Role                                           |
| ------------ | -------------------- | ---------------------------------------------- |
| Language     | Python 3.10+         | Runtime, orchestration, all pipeline logic     |
| Data         | Pandas 2.x           | DataFrame loading, cleaning, grouping, stats   |
| Charting     | Matplotlib + Seaborn | Figure generation and `.png` export            |
| Excel export | openpyxl 3.1+        | Workbook assembly, sheet writing, image embed  |
| CLI          | argparse (stdlib)    | Argument parsing — no extra dependency         |
| Environment  | venv / Anaconda      | Dependency isolation and reproducibility       |

## System Boundaries

- `main.py` — Entry point and orchestrator. Parses CLI args, calls
  modules in sequence, handles all top-level errors. The only file
  that imports from all other pipeline modules.

- `ingest.py` — Owns CSV loading and schema validation. Checks for
  all required SCADA columns before returning a raw DataFrame. Does
  not clean or transform data.

- `clean.py` — Owns deduplication, type coercion, null handling, and
  date parsing. Returns a clean DataFrame and a quality log DataFrame.
  Appends the quality log to `logs/data_quality.log`. Does not compute
  analysis.

- `analyse.py` — Owns summary statistics, power curve efficiency
  ratios, GroupBy aggregations, and time-series resampling. Returns a
  named dict of result DataFrames. Does not touch files or produce
  output.

- `visualise.py` — Owns chart generation and `.png` export to
  `output/charts/`. Returns a list of saved image file paths. Does
  not know about Excel or analysis internals.

- `export.py` — Owns workbook assembly, sheet writing, and chart
  image embedding. Receives analysis DataFrames and image paths.
  Returns the final output file path. Does not know how data was
  analysed or charts were produced.

- `config.py` — Single source of truth for all constants. Lives at
  the project root. Contains column names, file paths, date formats,
  numeric thresholds, and log field names. Contains no logic.
  Imported by all other modules.

- `data/` — Input CSV files only. Treated as immutable. No script
  ever writes to this directory.

- `output/` — Timestamped `.xlsx` reports. Sub-folder `output/charts/`
  holds `.png` chart files produced by `visualise.py`.

- `logs/` — Contains `data_quality.log`. Appended by `clean.py`
  after every run. Never truncated or overwritten.

- `context/` — Project reference documents: `project-overview.md`,
  `architecture.md`, `code-standards.md`, `ai-workflow-rules.md`,
  `progress-tracker.md`. Never modified by the pipeline.

## Storage Model

- **Memory (DataFrames)**: All intermediate pipeline data. Nothing
  is persisted mid-pipeline. Each run starts clean.

- **File input (`data/`)**: Source SCADA CSV files. Immutable input.
  Never modified by any script.

- **File output (`output/`)**: Timestamped `.xlsx` reports.
  Sub-folder `output/charts/` for `.png` chart figures.

- **Append-only log (`logs/data_quality.log`)**: Written by
  `clean.py` after every run. Each entry includes `run_id` (UUID),
  `run_timestamp` (ISO 8601), `column`, `issue_type`, `row_count`,
  and `action_taken`. Never overwritten — append only.

- **No database**: Data volumes do not justify persistence beyond
  flat files. No SQLite, no external database.

## Auth and Access Model

- No authentication. This is a local CLI tool.
- The filesystem is the access boundary. Whoever can run the script
  can use it.
- No user model, no sessions, no permissions layer.

## SCADA Column Reference

These are the five canonical columns for the Wind Turbine dataset.
All column references throughout the codebase must use the constant
names defined in `config.py`, not these raw strings.

| Constant Name        | Raw Column Name                 | Type     | Critical | Notes |
| -------------------- | ------------------------------- | -------- | -------- | ----- |
| `COL_DATETIME`       | `Date/Time`                     | datetime | Yes      | Primary: `%Y-%m-%d %H:%M:%S`. Fallback: infer. 10-min intervals. |
| `COL_ACTIVE_POWER`   | `LV ActivePower (kW)`           | float    | Yes      | Rows with `<= 0` are non-operational. Drop nulls. |
| `COL_WIND_SPEED`     | `Wind Speed (m/s)`              | float    | No       | Fill nulls with column median. |
| `COL_THEORETICAL`    | `Theoretical_Power_Curve (KWh)` | float    | No       | Rows where `== 0` are non-operational. Fill nulls with median. |
| `COL_WIND_DIRECTION` | `Wind Direction (degrees)`      | float    | No       | Fill nulls with column median. Range: 0–360°. |

**Critical columns** (`COL_DATETIME`, `COL_ACTIVE_POWER`): rows with
nulls in these columns are dropped entirely during cleaning.

**Non-critical columns** (`COL_WIND_SPEED`, `COL_THEORETICAL`,
`COL_WIND_DIRECTION`): nulls are filled with the column median.

**Operational period definition:** a row represents normal operation
only when `COL_ACTIVE_POWER > 0` AND `COL_THEORETICAL > 0`. Rows
outside this definition must be excluded from efficiency calculations
— not filled, not zeroed, excluded.

## Invariants

1. **Input files are never modified.** The script reads from `data/`
   and writes only to `output/` and `logs/`. These are strictly
   one-way paths.

2. **No hardcoded strings in logic.** Column names, file paths, date
   formats, and numeric thresholds live exclusively in `config.py`.
   A string literal referencing a data column or path anywhere else
   in the codebase is a violation.

3. **No logic at module level.** Every module is importable without
   side effects. Nothing executes on import. `main.py` drives all
   execution.

4. **No silent failures.** Every dropped row, coerced value, or
   skipped file must be counted, printed to the terminal, and
   appended to the quality log. Python tracebacks must not reach
   the user — catch at the top level in `main.py` and surface a
   plain-English message.

5. **The quality log is append-only.** `logs/data_quality.log` is
   never truncated or overwritten. Every entry must include a
   `run_id` and `run_timestamp` so entries from different runs
   remain traceable.

6. **Output filenames include a timestamp.** Format:
   `report_YYYY-MM-DD.xlsx`. A run never silently overwrites a
   previous report.

7. **Modules do not import each other laterally.** Only `main.py`
   imports from pipeline modules. Pipeline modules import only from
   `config.py` and standard library / third-party packages.

8. **Efficiency is computed only on operational rows.** Any row
   where `COL_THEORETICAL == 0` or `COL_ACTIVE_POWER <= 0` must be
   excluded before computing efficiency ratios. These are
   non-operational periods by industry definition. The excluded row
   count must be logged to the terminal.
