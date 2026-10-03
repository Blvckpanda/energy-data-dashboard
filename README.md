# Energy Operations Data Dashboard

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?style=flat-square&logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.x-11557C?style=flat-square)
![openpyxl](https://img.shields.io/badge/openpyxl-3.x-217346?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)
![Tests](https://github.com/Blvckpanda/energy-data-dashboard/actions/workflows/tests.yml/badge.svg)

A schema-agnostic Python pipeline that ingests operational SCADA data
from CSV files — Wind Turbine, Solar Power Generation, or Hydro
Turbine — cleans and validates it, runs structured analysis including
anomaly detection, and exports a multi-sheet Excel report and a
self-contained shareable HTML report, both with embedded charts and
plain-English summaries. The pipeline computes efficiency against
reference benchmarks, measures a binned power curve following the
IEC 61400-12-1 methodology for wind, reports solar's performance
ratio under IEC 61724 naming, generates time-series and distribution
visualisations, flags anomalous readings using statistical and
rolling-window methods, and maintains an append-only audit log keyed
by run ID across every execution — directly mirroring data workflows
used in real energy operations. Built as a self-directed portfolio
project to demonstrate practical ETL, data cleaning, analysis, and
reporting skills using industry-standard Python tooling.

---

## Output Preview

![Summary Sheet](docs/screenshots/summary_sheet.png)
![Sample Chart](docs/screenshots/chart_sample.png)
![Terminal Output](docs/screenshots/terminal_output.png)

---

## Stack

| Layer        | Technology            | Role                                          |
| ------------ | ---------------------- | --------------------------------------------- |
| Language     | Python 3.10+           | Runtime, orchestration, all pipeline logic    |
| Data         | Pandas 2.x              | Loading, cleaning, grouping, aggregation      |
| Charting     | Matplotlib + Seaborn   | Figure generation and `.png` export           |
| Excel export | openpyxl 3.x            | Workbook assembly, sheet writing, image embed |
| HTML export  | base64 (stdlib)         | Self-contained single-file report generation  |
| Testing      | pytest                  | Automated regression coverage                 |
| CLI          | argparse (stdlib)      | Argument parsing — no extra dependency        |

---

## Install

**1. Clone the repo**

```bash
git clone https://github.com/Blvckpanda/energy-data-dashboard.git
cd energy-data-dashboard
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

Place a SCADA CSV file in the `data/` folder. Three schemas are
supported:

**Wind Turbine schema (`--schema wind`, the default):**

| Column | Type |
| ------ | ---- |
| `Date/Time` | datetime |
| `LV ActivePower (kW)` | float |
| `Wind Speed (m/s)` | float |
| `Theoretical_Power_Curve (KWh)` | float |
| `Wind Direction (°)` | float |

Dataset: [Wind Turbine SCADA Dataset](https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset)

**Solar Power schema:**

| Column | Type |
| ------ | ---- |
| `DATE_TIME` | datetime |
| `PLANT_ID` | string |
| `SOURCE_KEY` | string |
| `DC_POWER` | float |
| `AC_POWER` | float |
| `DAILY_YIELD` | float |
| `TOTAL_YIELD` | float |

Dataset: [Solar Power Generation Data](https://www.kaggle.com/datasets/anikannal/solar-power-generation-data)

**Hydro Turbine schema (`--schema hydro`):**

| Column | Type |
| ------ | ---- |
| `Timestamp` | datetime |
| `Water_Flow_Rate (m3/s)` | float |
| `Generated_Power (kW)` | float |
| `Theoretical_Potential (kW)` | float |

No public dataset is bundled — synthetic hydro CSVs (10-minute
intervals, same date format as wind) work out of the box. Hydro exists
to prove the registry design: adding it required zero changes to any
pipeline module.

## Run with Docker

No local Python setup required.

**Build:**

```bash
docker build -t energy-dashboard .
```

**Run (PowerShell):**

```powershell
docker run --rm `
  -v ${PWD}/data:/app/data `
  -v ${PWD}/output:/app/output `
  -v ${PWD}/logs:/app/logs `
  energy-dashboard --file data/turbine.csv
```

**Run (bash):**

```bash
docker run --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  energy-dashboard --file data/turbine.csv
```

---

## Usage

**Single file (wind schema — default):**

```bash
python main.py --file data/turbine.csv
```

**Solar or hydro schema:**

```bash
python main.py --file data/solar.csv --schema solar
python main.py --file data/hydro.csv --schema hydro
```

**Batch mode — process all CSVs in a folder:**

```bash
python main.py --folder data/ --schema wind
```

**Choose report format:**

```bash
python main.py --file data/turbine.csv --format html   # HTML only
python main.py --file data/turbine.csv --format both   # Excel + HTML
```

**Help:**

```bash
python main.py --help
```

**Example terminal output:**

```
[LOAD] 52,608 rows × 5 columns
[WARN] Date format inferred — verify output timestamps
[CLEAN] 52,608 rows in → 52,543 rows clean (65 dropped)
[ANALYSE] 3,226 rows excluded from efficiency (zero theoretical or non-positive output)
[ANALYSE]
[DETECT] 47 anomalies flagged (12 threshold, 35 rolling window)
[VISUALISE]
  Chart saved → output\charts\power_trend.png
  Chart saved → output\charts\wind_scatter.png
  Chart saved → output\charts\monthly_bar.png
  Chart saved → output\charts\anomaly_timeline.png
[EXPORT]
Report saved → output\report_2026-07-30.xlsx
```

(The `[WARN]` line appears whenever the date column needs the
fallback parser — it fires on the real wind dataset. A second run on
the same day writes `report_2026-07-30_1.xlsx` — reports are never
overwritten.)

---

## Output

**`output/report_YYYY-MM-DD.xlsx`** — Excel workbook with seven base
sheets (eight for schemas that enable the measured power curve):

| Sheet | Contents |
| ----- | -------- |
| Summary | Narrative paragraph + headline statistics |
| Clean Data | Full cleaned dataset, plain-English headers |
| Trend Analysis | Monthly mean, daily total, and daily mean power |
| Efficiency Analysis | Per-row efficiency/conversion ratios |
| Power Curve (IEC 61400-12-1) | Measured binned power curve (wind schema) |
| Charts | All four embedded chart images |
| Anomaly Report | Flagged anomalous readings with detection method |
| Data Quality Log | Cleaning decisions for this run, keyed by `run_id` |

**`output/report_YYYY-MM-DD.html`** — self-contained single-file
report with the same narrative, statistics, anomaly summary, data
quality note, measured power-curve table (where the schema enables
it), and charts embedded as base64 images. Opens offline, shareable
as one file, deployable to GitHub Pages.

**`output/charts/`** — four standalone chart images:

| File | Chart |
| ---- | ----- |
| `power_trend.png` | Daily power output over time |
| `wind_scatter.png` | Output vs secondary metric, with reference line |
| `monthly_bar.png` | Monthly mean power output |
| `anomaly_timeline.png` | Power trend with anomalies highlighted |

**`logs/data_quality.log`** — append-only CSV audit log, keyed by
`run_id` and `run_timestamp` across every run.

---

## Pipeline Architecture

The pipeline is schema-agnostic, driven by a `SCHEMA_REGISTRY` in
`config.py` that tells every module which columns, thresholds,
labels, analysis interval, scatter reference, and distribution
method apply for the active `--schema`. Adding a schema (hydro was
third) costs one registry entry — no pipeline module changes. Each
module owns exactly one responsibility and is independently
importable. `main.py` is the only file that imports from all other
modules.

```
CSV file(s)
    │
    ▼
ingest.py ──── Schema validation against SCHEMA_REGISTRY
    │
    ▼
clean.py ───── Dedup → type coercion → null handling → date parse
    │                └── logs/data_quality.log (append-only)
    ▼
analyse.py ─── Stats · Efficiency · Monthly · Daily · Distribution
    │
    ▼
detect.py ──── Threshold + rolling-window anomaly detection
    │
    ▼
visualise.py ── Trend · Scatter · Bar · Anomaly timeline → *.png
    │
    ├──▶ export.py ──────▶ output/report_YYYY-MM-DD.xlsx
    └──▶ html_export.py ─▶ output/report_YYYY-MM-DD.html
              (both use narrative.py for shared summary text)
```

**Invariants the codebase never violates:**
- Input files in `data/` are never modified
- `logs/data_quality.log` is append-only — never truncated
- No column name, path, threshold, label, or schema branch exists
  outside `config.py`
- No Python traceback ever reaches the user
- Output filenames always include an ISO date timestamp and never
  overwrite a same-day report
- Adding a schema touches only `config.py`

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

83 tests cover schema validation (including registry integrity),
cleaning rules, efficiency exclusion logic, IEC-style power-curve
binning and data sufficiency, anomaly detection, narrative
construction, chart generation, both report exporters, batch mode,
and end-to-end runs for every registered schema — all on synthetic
data, no dataset required.

## Linting

```bash
pip install -r requirements-dev.txt
ruff check .
```

Ruff (E/F/W/I, line-length 100) gates CI via a dedicated lint job;
the same command runs locally. The one exemption (E402 in
`visualise.py`) is documented in `pyproject.toml`.

---

## Project Structure

```
energy-data-dashboard/
│
├── main.py               # CLI entry point and pipeline orchestrator
├── ingest.py             # CSV loading and schema validation
├── clean.py              # Data cleaning and quality logging
├── analyse.py            # Statistics, aggregations, efficiency
├── detect.py             # Anomaly detection (threshold + rolling)
├── visualise.py          # Chart generation (.png export)
├── export.py             # Excel workbook assembly
├── html_export.py        # Self-contained HTML report assembly
├── narrative.py          # Shared narrative text generation
├── config.py             # All constants + SCHEMA_REGISTRY
├── pyproject.toml        # ruff configuration
├── requirements.txt      # Pinned runtime dependencies
├── requirements-dev.txt  # Test and lint dependencies
├── LICENSE               # MIT
├── CLAUDE.md             # Canonical AI agent rules
│
├── tests/                # pytest suite (62 tests, synthetic data)
├── data/                 # Input CSV files (gitignored)
├── output/               # Generated reports and charts (gitignored)
├── logs/                 # data_quality.log (gitignored)
├── docs/screenshots/     # README images
├── docs/archive/          # Historical build docs (unit specs, tracker)
│
└── context/              # Living architecture and reference docs
    ├── project-overview.md
    ├── architecture.md
    ├── code-standards.md
    └── decisions.md
```

---

## Development Process

This project was built using a spec-driven, incremental workflow —
fourteen build units, each fully specified before any code was
written, with explicit done-when checklists and architecture
invariants enforced throughout. The original unit specs, workflow
rules, and progress tracker are archived under `docs/archive/` as
historical record; the living documents in `context/` describe the
system as it is today, and `context/decisions.md` carries the full
decisions log.

---

## License

MIT — see [LICENSE](LICENSE).
