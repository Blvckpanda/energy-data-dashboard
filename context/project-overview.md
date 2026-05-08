# Energy Operations Data Dashboard

## Overview

A command-line Python pipeline that ingests raw Wind Turbine SCADA
data from CSV files, cleans and validates it, runs structured analysis
(summary statistics, GroupBy aggregations, time-series resampling),
and exports a multi-sheet Excel report with embedded charts — producing
a professional deliverable readable by non-technical stakeholders
without any manual steps in between.

## Goals

1. Process a valid SCADA CSV end-to-end and produce a timestamped
   `.xlsx` report with a single command.
2. Log every data quality decision (dropped rows, coerced types,
   duplicates) to an append-only quality log with full run lineage.
3. Produce a Summary sheet readable by someone unfamiliar with Python
   or data tooling — plain-English labels, no raw column keys.
4. Support batch mode: process a folder of CSVs and produce one
   consolidated report with a source-file column.
5. Serve as a portfolio artefact demonstrating real-world ETL,
   data cleaning, and reporting skills against an industry dataset.

## Core User Flow

1. Place one or more SCADA CSV files in `data/`.
2. Run: `python main.py --file data/turbine.csv --output output/`
3. Script prints stage confirmations in order:
   `[LOAD] → [CLEAN] → [ANALYSE] → [EXPORT]`
4. Cleaning decisions are printed to the terminal and appended to
   `logs/data_quality.log` with a run timestamp and run ID.
5. Script prints on completion:
   `Report saved → output/report_2026-05-07.xlsx`
6. User opens the Excel file — all sheets, charts, and summaries
   are present and labelled in plain English.

## Features

### Data Ingestion

- Load a single CSV via `--file` flag
- Load all CSVs in a directory via `--folder` flag (batch mode)
- Validate that all required SCADA columns are present before
  any processing begins
- Exit with a plain-English error listing missing columns if
  schema validation fails

### Data Cleaning

- Remove duplicate rows; log count per run
- Coerce numeric columns using `pd.to_numeric(errors='coerce')`
- Handle null values — drop rows with nulls in critical columns,
  fill non-critical columns with column median
- Parse `Date/Time` column using the format defined in `config.py`
- Append all decisions to `logs/data_quality.log` with `run_id`
  and `run_timestamp`

### Analysis

- Summary statistics: mean, median, min, max, std for
  `LV ActivePower (kW)` and `Wind Speed (m/s)`
- Power curve analysis: actual output vs `Theoretical_Power_Curve
  (KWh)` — efficiency ratio per row
- Time-series resampling: hourly, daily, and monthly aggregations
  of active power output
- Wind direction distribution: binned frequency count across
  compass segments
- Results held in a dict of named DataFrames passed to export

### Visualisation

- Trend line: active power output over time
- Scatter plot: wind speed vs actual power output (with theoretical
  curve overlay)
- Bar chart: average daily yield by month
- All charts saved as `.png` to `output/charts/`
- All axes labelled; all titles written in plain English

### Export

- Multi-sheet Excel workbook assembled with openpyxl
- Six sheets in order: Summary, Clean Data, Trend Analysis,
  Power Curve Analysis, Charts, Data Quality Log
- Chart images embedded in the Charts sheet
- Output filename includes ISO date: `report_YYYY-MM-DD.xlsx`

## Scope

### In Scope

- Wind Turbine SCADA CSV ingestion (single file and batch)
- Schema validation against the five SCADA columns in `config.py`
- Data cleaning with an append-only quality log (run_id + timestamp)
- Summary stats, power curve efficiency, and time-series analysis
- Matplotlib + Seaborn chart generation (trend, scatter, bar)
- Multi-sheet Excel export with embedded charts
- CLI via argparse: `--file`, `--folder`, `--output`
- `context/` folder with all project reference documents
- README with install instructions and usage examples

### Out of Scope

- Solar power schema (defined but not implemented in v1)
- Web UI, GUI, or interactive dashboard of any kind
- Live data feeds, API integrations, or database connectors
- User accounts, authentication, or access control
- Automated scheduling or task runners
- Machine learning, forecasting, or predictive analytics
- Cloud hosting or deployment
- Formal test suite or CI pipeline

## Success Criteria

1. `python main.py --file data/turbine.csv` produces a valid `.xlsx`
   in `output/` without errors.
2. Script exits with a plain-English error (not a traceback) when
   a required SCADA column is missing.
3. `logs/data_quality.log` gains new entries after every run,
   each with a unique `run_id` and `run_timestamp`.
4. The Summary sheet is readable by a peer unfamiliar with Python —
   no raw column keys, no unexplained numbers.
5. Batch mode processes a folder of two CSVs and produces a single
   consolidated report with a `source_file` column.
6. Every function in every module has a docstring.
7. No column names, paths, or thresholds appear outside `config.py`.
