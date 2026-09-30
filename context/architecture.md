# Architecture Context

## Stack

| Layer        | Technology           | Role                                           |
| ------------ | -------------------- | ---------------------------------------------- |
| Language     | Python 3.10+         | Runtime, orchestration, all pipeline logic     |
| Data         | Pandas 2.x           | DataFrame loading, cleaning, grouping, stats   |
| Charting     | Matplotlib + Seaborn | Figure generation and `.png` export            |
| Excel export | openpyxl 3.1+        | Workbook assembly, sheet writing, image embed  |
| HTML export  | base64 (stdlib)      | Self-contained single-file report generation   |
| CLI          | argparse (stdlib)    | Argument parsing — no extra dependency         |
| Linting      | ruff (E/F/W/I)       | CI lint gate, same command runs locally        |
| Testing      | pytest               | 62-test suite, fully synthetic data            |
| Environment  | venv / Docker        | Dependency isolation and reproducibility       |

## System Boundaries

- `main.py` — Entry point and orchestrator. Parses CLI args (`--schema`
  choices derive from the registry), creates the output directory,
  calls modules in sequence, handles all top-level errors. The only
  file that imports from all other pipeline modules, and the single
  place run IDs are normalised to a list (the pipeline boundary).

- `ingest.py` — Owns CSV loading and schema validation. Checks for
  all required SCADA columns of the active registry schema before
  returning a raw DataFrame. Does not clean or transform data.

- `clean.py` — Owns deduplication, type coercion, null handling, and
  date parsing, all driven by registry keys. Returns a clean
  DataFrame and a quality-log run ID. Appends the quality log to
  `logs/data_quality.log` (creating `logs/` on first write). Does not
  compute analysis.

- `analyse.py` — Owns summary statistics, power curve efficiency
  ratios, GroupBy aggregations, and time-series resampling (monthly
  mean, daily total, daily mean). Returns a named dict of result
  DataFrames. Distribution analysis dispatches on the registry's
  distribution spec (`bins` / `group_mean`), never the schema name.
  Does not touch files or produce output.

- `detect.py` — Owns anomaly detection: static threshold and rolling
  window on the primary power column, thresholds from `config.py`.
  Returns an anomalies DataFrame. Does not mutate its input.

- `visualise.py` — Owns chart generation and `.png` export. Axis
  labels and the scatter reference kind come from the registry; the
  charts directory is the caller's `charts_dir` parameter (default
  `config.CHARTS_DIR`). Returns saved image file paths.

- `export.py` — Owns Excel workbook assembly (seven sheets). Sheet
  headers come from registry display names. Accepts `run_ids: list`.

- `html_export.py` — Owns self-contained HTML report generation
  (base64-embedded charts, data-quality note). Accepts
  `run_ids: list`; per-day unique filenames (Invariant 6).

- `narrative.py` — Shared narrative text for both exporters. One
  parameterized builder driven by the registry: interval-based
  operational hours and a notable-pattern sentence dispatched on the
  distribution kind. No side effects.

- `config.py` — Single source of truth for all constants and the
  `SCHEMA_REGISTRY`. Contains column names, file paths, date formats,
  numeric thresholds, log field names, and every per-schema key
  (columns, labels, display names, interval, scatter reference,
  distribution spec). Contains no logic. Imported by all other
  modules. Adding a schema touches only this file.

- `data/` — Input CSV files only. Treated as immutable. No script
  ever writes to this directory.

- `output/` — Timestamped `.xlsx` / `.html` reports. Sub-folder
  `output/charts/` holds `.png` chart files.

- `logs/` — Contains `data_quality.log`. Appended by `clean.py`
  after every run. Never truncated or overwritten.

- `context/` — Living reference documents (`project-overview.md`,
  `architecture.md`, `code-standards.md`, `decisions.md`). Never
  modified by the pipeline. Historical build documents live in
  `docs/archive/`.

## Storage Model

- **Memory (DataFrames)**: All intermediate pipeline data. Nothing
  is persisted mid-pipeline. Each run starts clean.

- **File input (`data/`)**: Source SCADA CSV files. Immutable input.
  Never modified by any script.

- **File output (`output/`)**: Timestamped `.xlsx` and `.html`
  reports. Sub-folder `output/charts/` for `.png` chart figures.

- **Append-only log (`logs/data_quality.log`)**: Written by
  `clean.py` after every run. Each entry includes `run_id` (UUID),
  `run_timestamp` (ISO 8601), `column`, `issue_type`, `row_count`,
  and `action_taken`. Never overwritten — append only. In batch
  mode each source file gets its own `run_id`; reports receive all
  of them.

- **No database**: Data volumes do not justify persistence beyond
  flat files. No SQLite, no external database.

## Auth and Access Model

- No authentication. This is a local CLI tool.
- The filesystem is the access boundary. Whoever can run the script
  can use it.
- No user model, no sessions, no permissions layer.

## SCADA Column Reference

Column references throughout the codebase use the constants defined
in `config.py`, never raw strings. Each schema's full column set,
critical/fill split, labels, and thresholds live in its registry
entry — see the `SCHEMA_REGISTRY` docstring in `config.py` for the
authoritative key list.

### Wind (`COL_*` constants)

| Constant Name        | Raw Column Name                 | Type     | Critical | Notes |
| -------------------- | ------------------------------- | -------- | -------- | ----- |
| `COL_DATETIME`       | `Date/Time`                     | datetime | Yes      | Primary: `%Y-%m-%d %H:%M:%S`. Fallback: `mixed`. 10-min intervals. |
| `COL_ACTIVE_POWER`   | `LV ActivePower (kW)`           | float    | Yes      | Rows with `<= 0` are non-operational. Drop nulls. |
| `COL_WIND_SPEED`     | `Wind Speed (m/s)`              | float    | No       | Fill nulls with column median. |
| `COL_THEORETICAL`    | `Theoretical_Power_Curve (KWh)` | float    | No       | Rows where `== 0` are non-operational. Fill nulls with median. |
| `COL_WIND_DIRECTION` | `Wind Direction (°)`            | float    | No       | Fill nulls with column median. Range: 0–360°. |

### Solar (`COL_SOLAR_*` / `COL_PLANT_ID` / `COL_SOURCE_KEY` / `COL_AC_POWER` / `COL_DC_POWER`)

Datetime `%d-%m-%Y %H:%M`, 15-minute intervals, `DATE_TIME` and
`AC_POWER` critical, others median-filled. Conversion ratio is
`AC_POWER / DC_POWER`; the scatter reference is the ideal 1:1 line
(`identity`); distribution groups mean AC power per inverter
(`SOURCE_KEY`).

### Hydro (`COL_HYDRO_*` constants)

Datetime `%Y-%m-%d %H:%M:%S`, 10-minute intervals, `Timestamp` and
`Generated_Power (kW)` critical, flow and theoretical potential
median-filled. Conversion ratio is generated / theoretical; the
scatter reference is the shipped theoretical column (`column`);
distribution bins the flow rate. Hydro has no real dataset — tests
use synthetic frames only.

**Operational period definition:** a row represents normal operation
only when the primary power column AND the reference column exceed
their registry minimums (`min_primary`, `min_reference` — all zero,
exclusive). Rows outside this definition must be excluded from
ratio calculations — not filled, not zeroed, excluded.

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

6. **Output filenames include a timestamp and never overwrite.**
   Format: `report_YYYY-MM-DD.xlsx` / `.html`. Same-day reruns add
   a `_1`, `_2…` counter suffix (enforced for both formats).

7. **Modules do not import each other laterally.** Only `main.py`
   imports from pipeline modules. Pipeline modules import only from
   `config.py` and standard library / third-party packages. The one
   sanctioned exception: both exporters import `narrative.py`, the
   shared text builder.

8. **Efficiency is computed only on operational rows.** Any row at
   or below the registry's `min_primary` / `min_reference` must be
   excluded before computing ratios. These are non-operational
   periods by industry definition. The excluded row count must be
   logged to the terminal.

9. **Schemas are registry-only.** Schema names never appear as
   branches or literals outside `config.py` (the CLI default is the
   one sanctioned string). Behaviour varies only through registry
   keys; a new schema requires a registry entry and nothing else.
