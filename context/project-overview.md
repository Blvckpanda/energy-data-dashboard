# Energy Operations Data Dashboard

## Overview

A schema-agnostic command-line Python pipeline that ingests raw
renewable-energy SCADA data — **wind turbine**, **solar plant**, or
**hydro turbine** — from CSV files, cleans and validates it, runs
structured analysis (summary statistics, per-row efficiency ratios,
time-series resampling, distribution analysis) plus statistical and
rolling-window anomaly detection, and exports two deliverables: a
seven-sheet Excel report and a self-contained single-file HTML report,
both with embedded charts and a plain-English narrative summary.

Every schema's columns, labels, thresholds, analysis interval, and
distribution method live in one `SCHEMA_REGISTRY` in `config.py` —
adding a schema requires only column constants and a registry entry;
no pipeline module changes.

Built as a self-directed portfolio project demonstrating practical
ETL, data cleaning, analysis, anomaly detection, and reporting skills
against industry datasets, with an append-only quality log providing
full run lineage.

## Goals

1. Process a valid SCADA CSV end-to-end — any registered schema — and
   produce timestamped `.xlsx` and/or `.html` reports with a single
   command.
2. Log every data quality decision (dropped rows, coerced types,
   duplicates) to an append-only quality log with full run lineage,
   and surface that log in both report formats.
3. Produce summaries readable by someone unfamiliar with Python or
   data tooling — plain-English labels, no raw column keys.
4. Support batch mode: process a folder of CSVs of the same schema
   into one consolidated report; every source file's quality-log
   entries appear in the report.
5. Keep every schema-specific behaviour registry-driven — proven by
   the third schema (hydro) requiring zero pipeline-module changes.
6. Serve as a portfolio artefact with a green CI gate (ruff lint +
   62-test pytest suite across Python 3.10/3.11) and a reproducible
   Docker run.

## Core User Flow

1. Place one or more SCADA CSV files in `data/`.
2. Run: `python main.py --file data/turbine.csv --schema wind`
   (schema choices come from the registry).
3. Script prints stage confirmations in order:
   `[LOAD] → [CLEAN] → [ANALYSE] → [DETECT] → [VISUALISE] → [EXPORT]`
   (batch mode prefixes per-file stages with `[BATCH]` and skips
   unusable files with `[SKIP]`).
4. Cleaning decisions are printed to the terminal and appended to
   `logs/data_quality.log` with a run timestamp and run ID.
5. Script prints on completion:
   `Report saved → output/report_2026-05-07.xlsx` (and `.html` with
   `--format html|both`). Same-day reruns never overwrite — a
   `_1`, `_2…` suffix is added.
6. User opens the report — all sheets/sections, charts, narrative,
   anomaly highlights, and the run's data-quality note are present
   and labelled in plain English.

## Schemas

Each registered schema defines: required columns, datetime format,
critical/median-fill columns, primary/secondary/reference power
columns, ratio name, operational thresholds, plain-English labels and
display names, row interval in minutes, scatter reference kind
(`column` = shipped theoretical curve, `identity` = ideal 1:1 line),
and a distribution spec (`bins` or `group_mean`).

| Schema | Dataset shape | Ratio | Distribution | Interval |
| ------ | ------------- | ----- | ------------ | -------- |
| `wind` | Wind Turbine SCADA (5 columns) | efficiency vs theoretical power curve | 16 wind-direction bins | 10 min |
| `solar` | Solar Power Generation (7 columns, per-inverter) | DC→AC conversion | mean/count per inverter | 15 min |
| `hydro` | Hydro turbine SCADA (4 columns) | generated vs theoretical potential | flow-rate bins | 10 min |

## Features

### Data Ingestion
- Load a single CSV via `--file`, or all CSVs in a folder via
  `--folder` (batch mode; malformed files skipped with `[SKIP]`).
- Validate required columns per schema before any processing;
  plain-English error listing missing columns on failure.

### Data Cleaning
- Deduplicate → coerce numerics → null strategy (drop critical,
  median-fill non-critical) → datetime parse (registry format, with
  `mixed` fallback and `[WARN]` notice).
- All decisions appended to the append-only quality log with
  `run_id` and `run_timestamp`.

### Analysis
- Summary statistics, per-row efficiency/conversion ratio (computed
  only on operational rows — excluded count printed), monthly mean,
  daily total, daily mean, and registry-dispatched distribution
  analysis.

### Anomaly Detection
- Two schema-agnostic methods on the primary power column: static
  threshold (> 2σ) and sustained-drop rolling window (36 intervals,
  20% below the operational mean). Thresholds in `config.py`.

### Visualisation
- Four charts per run: daily total trend, scatter with registry
  reference line, monthly mean bars, and an anomaly timeline drawn
  on the daily mean (anomaly points share the line's units).
- Saved as `.png` under the output directory's `charts/` folder.

### Export
- **Excel**: seven sheets — Summary (narrative + headline stats),
  Clean Data, Trend Analysis, Efficiency Analysis, Charts (embedded),
  Anomaly Report, Data Quality Log (filtered to this run's IDs).
- **HTML**: single self-contained file, charts base64-embedded,
  with narrative, stats, anomaly summary, data-quality note, and
  charts — opens offline, deployable to GitHub Pages.
- Batch reports carry every source file's run ID; the Summary adds a
  Source Files Processed row.

### Tooling
- CLI: `--file`, `--folder`, `--output`, `--schema` (registry-driven
  choices), `--format excel|html|both`.
- Docker: single reproducible container, host volumes for
  data/output/logs.
- CI: ruff lint job gating a pytest matrix on Python 3.10/3.11.

## Scope

### In Scope
- Wind, solar, and hydro SCADA ingestion (single file and batch)
- Registry-driven schema validation, cleaning, analysis, and export
- Append-only quality logging with run lineage, surfaced in reports
- Anomaly detection (threshold + rolling window) with report sheets
- Matplotlib/Seaborn chart generation (four charts per run)
- Excel + self-contained HTML export
- pytest suite (62 tests, fully synthetic data) with ruff gate in CI
- Docker packaging; `context/` reference documents

### Out of Scope
- Web UI, GUI, or interactive dashboard of any kind
- Live data feeds, API integrations, or database connectors
- User accounts, authentication, or access control
- Automated scheduling or task runners
- Machine learning, forecasting, or predictive analytics
- Cloud hosting or deployment
- IEC-standard power-curve / performance-ratio methodologies
  (documented as a future direction; not implemented)

## Success Criteria

1. `python main.py --file data/turbine.csv` produces a valid `.xlsx`
   in `output/` without errors — same for solar and hydro inputs.
2. Script exits with a plain-English error (not a traceback) when a
   required column is missing or the datetime column is unparseable.
3. `logs/data_quality.log` gains new entries after every run, each
   with a unique `run_id` and `run_timestamp`; reports show the
   current run's entries only (all files' entries in batch mode).
4. The narrative summary is readable by a peer unfamiliar with
   Python — no raw column keys, no unexplained numbers; hours
   derived from the schema's true interval.
5. Batch mode processes a folder, skips malformed files with a
   warning, and produces one consolidated report with a
   `source_file` column and every file's run ID in the quality log.
6. Every function in every module has a docstring; `ruff check .`
   is clean in CI.
7. No column names, paths, thresholds, or labels appear outside
   `config.py`; no schema-name branching exists outside it (grep
   verifies both).
8. A same-day rerun never overwrites a previous report (Invariant 6).
