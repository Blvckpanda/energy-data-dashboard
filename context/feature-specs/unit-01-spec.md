# Read 'GEMINI.md' before starting

## Unit 01: Scaffold + Config + CLI Shell

## Goal

Create the complete project skeleton — folder structure, fully
populated `config.py`, `requirements.txt`, `README.md` skeleton,
and a `main.py` CLI shell wired with `argparse` — so that
`python main.py --help` runs cleanly and every subsequent unit has
a verified foundation to build on.

---

## Implementation

### 1. Environment Setup

Create and activate an isolated Python environment before creating
any files. This must be done first — all subsequent installs and
runs happen inside this environment.

**Using venv:**

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

**Using Anaconda:**

```bash
conda create -n energy-dashboard python=3.11
conda activate energy-dashboard
```

Confirm the active Python is 3.10 or higher before continuing:

```bash
python --version
```

---

### 2. Folder Structure

Create the following directories at the project root. All must
exist before any other unit runs — modules reference these paths
via constants in `config.py`.

energy-dashboard/
│
├── data/                  # Input CSVs — never written to by the pipeline
├── output/                # Generated .xlsx reports
│   └── charts/            # Generated .png chart figures
├── logs/                  # data_quality.log — append-only
├── context/               # All .md reference documents
│
├── main.py                # CLI entry point — created in this unit
├── config.py              # All constants — created in this unit
├── ingest.py              # Stub — empty file, created in this unit
├── clean.py               # Stub — empty file, created in this unit
├── analyse.py             # Stub — empty file, created in this unit
├── visualise.py           # Stub — empty file, created in this unit
├── export.py              # Stub — empty file, created in this unit
│
├── requirements.txt       # Pinned dependencies — created in this unit
└── README.md              # Skeleton — created in this unit

Create stub files for all pipeline modules now (`ingest.py`,
`clean.py`, `analyse.py`, `visualise.py`, `export.py`). Each stub
contains only a module-level docstring describing its responsibility.
No functions, no logic, no imports yet. This satisfies Invariant 3
(no logic at module level) from the start and makes each module
importable immediately.

**Example stub — `ingest.py`:**

```python
"""
ingest.py

Owns CSV loading and schema validation.
Checks that all required SCADA columns are present before
returning a raw DataFrame. Does not clean or transform data.
"""
```

---

### 3. `config.py`

`config.py` is the most important file in this unit. Every constant
used by any module in the entire pipeline must be defined here and
only here. This file contains no functions, no logic, and no
imports beyond the standard library.

Write the file in five clearly separated sections:

## Section 1 — SCADA Column Names

These are the five raw column name strings from the Wind Turbine
dataset. No other file in the project may reference these strings
directly — all modules must import the constant.

```python
# ── SCADA Column Names ────────────────────────────────────────────
COL_DATETIME       = "Date/Time"
COL_ACTIVE_POWER   = "LV ActivePower (kW)"
COL_WIND_SPEED     = "Wind Speed (m/s)"
COL_THEORETICAL    = "Theoretical_Power_Curve (KWh)"
COL_WIND_DIRECTION = "Wind Direction (degrees)"

# Columns where null rows are DROPPED (critical)
CRITICAL_COLUMNS = [COL_DATETIME, COL_ACTIVE_POWER]

# Columns where nulls are FILLED with column median (non-critical)
MEDIAN_FILL_COLUMNS = [COL_WIND_SPEED, COL_THEORETICAL, COL_WIND_DIRECTION]
```

## Section 2 — Date Parsing

```python
# ── Date Parsing ──────────────────────────────────────────────────
# Primary format expected in the SCADA CSV (10-minute intervals)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
```

## Section 3 — File Paths

Use `pathlib.Path` for all paths so they work correctly on both
Windows and Unix without string manipulation.

```python
# ── File Paths ────────────────────────────────────────────────────
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DATA_DIR     = PROJECT_ROOT / "data"
OUTPUT_DIR   = PROJECT_ROOT / "output"
CHARTS_DIR   = OUTPUT_DIR / "charts"
LOGS_DIR     = PROJECT_ROOT / "logs"
LOG_PATH     = LOGS_DIR / "data_quality.log"
```

## Section 4 — Quality Log Field Names

These are the exact CSV column headers written to
`logs/data_quality.log`. Defined here so `clean.py` never
hardcodes them.

```python
# ── Quality Log Fields ────────────────────────────────────────────
LOG_FIELD_RUN_ID        = "run_id"
LOG_FIELD_TIMESTAMP     = "run_timestamp"
LOG_FIELD_COLUMN        = "column"
LOG_FIELD_ISSUE_TYPE    = "issue_type"
LOG_FIELD_ROW_COUNT     = "row_count"
LOG_FIELD_ACTION_TAKEN  = "action_taken"

LOG_FIELDS = [
    LOG_FIELD_RUN_ID,
    LOG_FIELD_TIMESTAMP,
    LOG_FIELD_COLUMN,
    LOG_FIELD_ISSUE_TYPE,
    LOG_FIELD_ROW_COUNT,
    LOG_FIELD_ACTION_TAKEN,
]
```

## Section 5 — Analysis Thresholds

Defined now so Unit 4 never introduces a magic number.

```python
# ── Analysis Thresholds ───────────────────────────────────────────
# Number of compass bins for wind direction distribution
WIND_DIRECTION_BINS = 16

# Rows excluded from efficiency if either condition is true:
# COL_THEORETICAL == 0  →  non-operational period
# COL_ACTIVE_POWER <= 0  →  turbine not producing
EFFICIENCY_MIN_THEORETICAL = 0   # exclusive (> 0 required)
EFFICIENCY_MIN_ACTIVE_POWER = 0  # exclusive (> 0 required)
```

---

### 4. `main.py`

`main.py` is the CLI entry point and the only file that will ever
import from all other pipeline modules. In this unit, the pipeline
body is a stub — it parses arguments and prints them back to
confirm the CLI is wired correctly.

**Structure:**

```python
"""
main.py

Entry point and orchestrator for the Energy Operations Data Dashboard.
Parses CLI arguments and calls pipeline modules in sequence.
"""

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """
    Parse and return command-line arguments.

    Returns:
        argparse.Namespace with attributes:
            file   (Path | None): path to a single CSV file
            folder (Path | None): path to a folder of CSV files
            output (Path):        path to the output directory
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Energy Operations Data Dashboard — "
            "ingest SCADA CSV data, clean it, analyse it, "
            "and export a multi-sheet Excel report."
        ),
    )
    parser.add_argument(
        "--file",
        type=Path,
        metavar="FILE",
        help="Path to a single SCADA CSV file to process.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        metavar="FOLDER",
        help="Path to a folder of SCADA CSV files (batch mode).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="OUTPUT",
        default=Path("output"),
        help="Directory to write the Excel report to. Defaults to output/.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Orchestrate the full pipeline: parse args, then call each
    module in sequence. In Unit 1 the pipeline body is a stub.
    """
    args = parse_args()

    # ── Stub: print received arguments and exit ───────────────────
    # This block is replaced unit by unit as modules are implemented.
    print(f"--file   : {args.file}")
    print(f"--folder : {args.folder}")
    print(f"--output : {args.output}")


if __name__ == "__main__":
    main()
```

**Rules that must hold in `main.py` from this unit forward:**

- `parse_args()` and `main()` are separate functions — argument
  parsing is never mixed with pipeline logic.
- `main()` is only called via the `if __name__ == "__main__"` guard.
  This makes the module importable without running the pipeline.
- All top-level error handling will be added to `main()` in Unit 2
  when the first real exception surface becomes possible.

---

### 5. `requirements.txt`

List all four third-party dependencies with pinned major versions.
Do **not** install them in this unit — they are listed here for
reference and will be installed just in time in the unit that
first uses them.

pandas>=2.0,<3.0
matplotlib>=3.8,<4.0
seaborn>=0.13,<1.0
openpyxl>=3.1,<4.0

---

### 6. `README.md`

Write the skeleton now with all structural sections in place.
Content will be filled in Unit 8. Placeholder text must be clearly
marked so it is never left in the final version.

```markdown
# Energy Operations Data Dashboard

> **[PLACEHOLDER — fill in Unit 8]**
> One-paragraph project description for portfolio/CV use.

## Stack

Python · Pandas · Matplotlib · Seaborn · openpyxl

## Install

```bash
pip install -r requirements.txt
```

## Usage

**Single file:**

```bash
python main.py --file data/turbine.csv --output output/
```

**Batch mode (folder of CSVs):**

```bash
python main.py --folder data/ --output output/
```

## Output

> **[PLACEHOLDER — add screenshot of Excel Summary sheet
> or a chart PNG in Unit 8]**

## Project Structure

> **[PLACEHOLDER — fill in Unit 8 once all modules exist]**

---

## Dependencies

- `argparse` — stdlib, no install required. Used in `main.py`
  for CLI argument parsing.
- `pathlib.Path` — stdlib, no install required. Used in
  `config.py` for cross-platform path construction.

No third-party packages are installed in this unit.

---

## Verify When Done

### Structure

- [ ] All seven directories exist: `data/`, `output/`,
      `output/charts/`, `logs/`, `context/`, and the project root
- [ ] All five stub module files exist: `ingest.py`, `clean.py`,
      `analyse.py`, `visualise.py`, `export.py` — each containing
      only a module-level docstring, no logic, no imports
- [ ] `config.py`, `main.py`, `requirements.txt`, and `README.md`
      exist at the project root

### CLI Behaviour

- [ ] `python main.py --help` prints descriptions for all three
      flags: `--file`, `--folder`, `--output`
- [ ] `python main.py --file data/turbine.csv` prints
      `--file : data/turbine.csv` without crashing
- [ ] `python main.py --folder data/ --output output/` prints
      all three received values without crashing
- [ ] `python main.py` (no arguments) runs without crashing —
      all arguments are optional at this stage

### `config.py` Correctness

- [ ] All five `COL_*` constants are defined and match the raw
      SCADA column names exactly (spelling, capitalisation, spaces)
- [ ] `CRITICAL_COLUMNS` contains `COL_DATETIME` and
      `COL_ACTIVE_POWER` — exactly two entries
- [ ] `MEDIAN_FILL_COLUMNS` contains `COL_WIND_SPEED`,
      `COL_THEORETICAL`, `COL_WIND_DIRECTION` — exactly three entries
- [ ] `DATE_FORMAT` is set to `"%Y-%m-%d %H:%M:%S"`
- [ ] `LOG_FIELDS` list contains all six field name constants in
      the correct order
- [ ] All paths (`OUTPUT_DIR`, `CHARTS_DIR`, `LOG_PATH`, etc.) are
      `pathlib.Path` objects — no raw strings
- [ ] `config.py` contains no functions, no classes, no imports
      beyond `pathlib`

### Code Standards

- [ ] No column name string (e.g. `"LV ActivePower (kW)"`) appears
      in any file other than `config.py`
- [ ] No file path string (e.g. `"output/"`) appears in any file
      other than `config.py`
- [ ] Every file is importable with no side effects:
      `python -c "import config"` and
      `python -c "import main"` both run silently
- [ ] `main()` is guarded by `if __name__ == "__main__"`
- [ ] `parse_args()` and `main()` each have a docstring

### Environment

- [ ] `python --version` confirms Python 3.10 or higher inside
      the active environment
- [ ] The virtual environment is active — `which python` (Unix)
      or `where python` (Windows) points inside `.venv/` or
      the conda environment, not the system Python
- [ ] `requirements.txt` lists all four packages with version
      constraints — none are installed yet (confirm with
      `pip show pandas` returning "not found")
