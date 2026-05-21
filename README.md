# Energy Operations Data Dashboard

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?style=flat-square&logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.x-11557C?style=flat-square)
![openpyxl](https://img.shields.io/badge/openpyxl-3.x-217346?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)

A command-line Python pipeline that ingests Wind Turbine SCADA data
from CSV files, cleans and validates it, runs structured analysis, and
exports a six-sheet Excel report with embedded charts and plain-English
summaries — with zero manual steps in between. The pipeline computes
power curve efficiency against theoretical benchmarks, generates
time-series and wind distribution visualisations, and maintains an
append-only audit log keyed by run ID across every execution, directly
mirroring data workflows used in real energy operations. Built as a
self-directed portfolio project to demonstrate practical ETL, data
cleaning, analysis, and reporting skills using industry-standard Python
tooling.

---

## Output Preview

[Summary Sheet](docs/screenshots/summary_sheet.png) 
[Sample Chart](docs/screenshots/chart_sample.png) 
[Terminal Output](docs/screenshots/terminal_output.png) 

---

## Stack

| Layer        | Technology           | Role                                         |
| ------------ | -------------------- | -------------------------------------------- |
| Language     | Python 3.10+         | Runtime, orchestration, all pipeline logic   |
| Data         | Pandas 2.x           | Loading, cleaning, grouping, aggregation     |
| Charting     | Matplotlib + Seaborn | Figure generation and `.png` export          |
| Excel export | openpyxl 3.x         | Workbook assembly, sheet writing, image embed|
| CLI          | argparse (stdlib)    | Argument parsing — no extra dependency       |

---

## Install

**1. Clone the repo**

```bash
git clone https://github.com/Blvckpanda/energy-dashboard.git
cd energy-dashboard
```

**2. Create and activate a virtual environment**

```bash
# Using venv
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Or using Anaconda
conda create -n energy-dashboard python=3.11
conda activate energy-dashboard
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Add your dataset**

Place your Wind Turbine SCADA CSV file in the `data/` folder.
The file must contain these five columns exactly:

| Column | Type |
| ------ | ---- |
| `Date/Time` | datetime |
| `LV ActivePower (kW)` | float |
| `Wind Speed (m/s)` | float |
| `Theoretical_Power_Curve (KWh)` | float |
| `Wind Direction (degrees)` | float |

A compatible dataset is available on Kaggle:
[Wind Turbine SCADA Dataset](https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset)

---

## Usage

**Single file:**

```bash
python main.py --file data/turbine.csv
```

**Single file with custom output directory:**

```bash
python main.py --file data/turbine.csv --output output/
```

**Batch mode — process all CSVs in a folder:**

```bash
python main.py --folder data/
```

**Help:**

```bash
python main.py --help
```

**Example terminal output:**

```
[LOAD] 52,608 rows × 5 columns
[CLEAN] 52,608 rows in → 52,543 rows clean (65 dropped)
[ANALYSE] 3,226 rows excluded from efficiency (zero theoretical or non-positive output)
[ANALYSE]
[VISUALISE]
  Chart saved → output\charts\power_trend.png
  Chart saved → output\charts\wind_scatter.png
  Chart saved → output\charts\monthly_bar.png
[EXPORT]
Report saved → output\report_2026-05-21.xlsx
```

---

## Output

Each run produces:

**`output/report_YYYY-MM-DD.xlsx`** — six-sheet Excel workbook:

| Sheet | Contents |
| ----- | -------- |
| Summary | Executive narrative paragraph + headline statistics table |
| Clean Data | Full cleaned dataset with plain-English column headers |
| Trend Analysis | Monthly mean and daily total active power aggregations |
| Power Curve Analysis | Per-row efficiency ratios (operational periods only) |
| Charts | All three embedded chart images |
| Data Quality Log | Cleaning decisions for this run, keyed by `run_id` |

**`output/charts/`** — three standalone chart images:

| File | Chart |
| ---- | ----- |
| `power_trend.png` | Daily active power output over time |
| `wind_scatter.png` | Wind speed vs output with theoretical curve overlay |
| `monthly_bar.png` | Monthly mean active power |

**`logs/data_quality.log`** — append-only CSV audit log. Every run
appends structured entries with `run_id`, `run_timestamp`, `column`,
`issue_type`, `row_count`, and `action_taken` — providing full
historical lineage across all runs.

---

## Pipeline Architecture

The pipeline follows a flat modular architecture. Each module owns
exactly one responsibility and is independently importable.
`main.py` is the only file that imports from all other modules.
All column names, file paths, and thresholds are defined once in
`config.py` — never hardcoded in logic.

```
CSV file(s)
    │
    ▼
ingest.py ──── Schema validation against config.py constants
    │
    ▼
clean.py ───── Dedup → type coercion → null handling → date parse
    │                └── logs/data_quality.log (append-only)
    ▼
analyse.py ─── Stats · Efficiency · Monthly · Daily · Wind bins
    │
    ▼
visualise.py ── Trend line · Scatter · Bar → output/charts/*.png
    │
    ▼
export.py ───── Six-sheet .xlsx → output/report_YYYY-MM-DD.xlsx
```

**Invariants the codebase never violates:**
- Input files in `data/` are never modified
- `logs/data_quality.log` is append-only — never truncated
- No column name or path string appears outside `config.py`
- No Python traceback ever reaches the user
- Output filenames always include an ISO date timestamp

---

## Project Structure

```
energy-dashboard/
│
├── main.py              # CLI entry point and pipeline orchestrator
├── ingest.py            # CSV loading and schema validation
├── clean.py             # Data cleaning and quality logging
├── analyse.py           # Statistics, aggregations, efficiency
├── visualise.py         # Chart generation (.png export)
├── export.py            # Excel workbook assembly
├── config.py            # All constants — single source of truth
├── requirements.txt     # Pinned dependencies
├── CLAUDE.md            # AI agent context and workflow rules
│
├── data/                # Input CSV files (gitignored)
├── output/              # Generated reports and charts (gitignored)
│   └── charts/          # .png chart files
├── logs/                # data_quality.log (gitignored)
│
├── docs/
│   └── screenshots/     # README images
│
└── context/             # Project architecture and specification docs
    ├── project-overview.md
    ├── architecture.md
    ├── code-standards.md
    ├── ai-workflow-rules.md
    ├── progress-tracker.md
    └── feature-specs/
        ├── unit-01-spec.md
        ├── unit-02-spec.md
        ├── unit-03-spec.md
        ├── unit-04-spec.md
        ├── unit-05-spec.md
        ├── unit-06-spec.md
        ├── unit-07-spec.md
        └── unit-08-spec.md
```

---

## Development Process

This project was built using a spec-driven, incremental workflow.
Each of the eight build units was fully specified before any code
was written — with explicit done-when checklists, dependency
ordering, and architecture invariants enforced at every step.

The `context/` folder contains the full set of living documents
that defined the project throughout the build: architecture
decisions, code standards, AI agent workflow rules, a decisions
log, and individual spec files for each unit. These documents were
updated in sync with the code at every stage.

---

## License

MIT
