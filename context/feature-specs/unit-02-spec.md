# Read 'CLAUDE.md' before starting

## Unit 02: Ingestion

## Goal

Implement `ingest.py` so that the pipeline can load a SCADA CSV
file, validate its schema against the five required column constants
in `config.py`, and return a raw DataFrame ready for cleaning —
with `main.py` updated to call it and print a `[LOAD]` confirmation
to the terminal.

---

## Implementation

### 1. `ingest.py` — Structure

`ingest.py` owns exactly two responsibilities: loading the file
and validating the schema. Nothing else. It does not clean, coerce,
parse dates, or transform data in any way.

The module contains two functions and nothing else at module level:

```text
load_csv(file_path)      → pd.DataFrame
validate_schema(df)      → None  (raises on failure)
```

Full module structure:

```python
"""
ingest.py

Owns CSV loading and schema validation.
Checks that all required SCADA columns are present before
returning a raw DataFrame. Does not clean or transform data.
"""

import pandas as pd
from pathlib import Path
import config


def load_csv(file_path: Path) -> pd.DataFrame:
    ...


def validate_schema(df: pd.DataFrame) -> None:
    ...
```

---

### 2. `load_csv(file_path)`

Loads the CSV at `file_path` using `pd.read_csv()` and returns
the raw DataFrame. Raises a descriptive error if the file does
not exist or cannot be read.

**Behaviour:**

- Accept a `pathlib.Path` object as the argument (already typed
  as `Path` by `argparse` in `main.py`)
- Call `pd.read_csv(file_path)` with no additional arguments —
  do not parse dates here, do not coerce types here; that belongs
  to `clean.py`
- If the file does not exist, catch `FileNotFoundError` and raise
  a `SystemExit` with this exact message format:
  `Error: File not found — {file_path}`
- If pandas raises any other read error (e.g. `pd.errors.ParserError`
  for a corrupt or non-CSV file), catch it and raise a `SystemExit`
  with this format:
  `Error: Could not read file — {file_path}\nReason: {error message}`
- On success, return the raw DataFrame without printing anything.
  `main.py` handles all terminal output.

**Docstring must cover:**

- What it does
- Parameter: `file_path` (`Path`) — path to the CSV file to load
- Returns: `pd.DataFrame` — raw contents of the CSV, no transforms applied
- Raises: `SystemExit` if file not found or unreadable

---

### 3. `validate_schema(df)`

Checks that the DataFrame contains all five required SCADA columns.
Raises a descriptive error if any are missing.

**Behaviour:**

- The required column list must be built from `config.py` constants
  — never from raw strings:

  ```python
  REQUIRED_COLUMNS = [
      config.COL_DATETIME,
      config.COL_ACTIVE_POWER,
      config.COL_WIND_SPEED,
      config.COL_THEORETICAL,
      config.COL_WIND_DIRECTION,
  ]
  ```

- Compare `REQUIRED_COLUMNS` against `df.columns.tolist()`
- If all five are present, return `None` silently
- If any are missing, raise a `SystemExit` with this exact format:

  ```text
  Error: Schema validation failed.
  Missing columns: ['LV ActivePower (kW)', 'Wind Speed (m/s)']
  Expected columns: ['Date/Time', 'LV ActivePower (kW)', 'Wind Speed (m/s)',
                     'Theoretical_Power_Curve (KWh)', 'Wind Direction (degrees)']
  ```

  The missing and expected lists must be derived from the config
  constants — the actual raw string values will appear in the message
  because that's what `df.columns` contains, but the list you
  compare against must come from config.
- Do not check column order, only presence
- Do not check column dtypes — that belongs to `clean.py`

**Docstring must cover:**

- What it does
- Parameter: `df` (`pd.DataFrame`) — raw DataFrame to validate
- Returns: `None` if all required columns are present
- Raises: `SystemExit` with a plain-English message listing missing
  and expected columns

---

### 4. Update `main.py`

Replace the Unit 1 stub body in `main()` with real ingestion logic.
`main.py` owns all terminal output — `ingest.py` functions return
or raise, they never print.

**Replace the stub block with:**

```python
def main() -> None:
    """
    Orchestrate the full pipeline: parse args, then call each
    module in sequence.
    """
    args = parse_args()

    # ── Unit 2: Ingestion ─────────────────────────────────────────
    raw_df = ingest.load_csv(args.file)
    ingest.validate_schema(raw_df)
    print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")

    # ── Units 3–8: stubs (to be replaced in subsequent units) ─────
```

**Import to add at the top of `main.py`:**

```python
import ingest
```

**Terminal output format for this unit:**

```text
[LOAD] 52,608 rows × 5 columns
```

The row count must use comma-separated thousands formatting
(`{n:,}`). The column count is the raw integer — no formatting.

---

### 5. Error handling boundary

All `SystemExit` calls raised inside `ingest.py` will naturally
propagate up and exit with the provided message. However, `main.py`
must also wrap the ingestion block in a top-level `try/except` to
catch any unexpected exception that wasn't anticipated in `ingest.py`
and prevent a raw traceback from reaching the user:

```python
try:
    raw_df = ingest.load_csv(args.file)
    ingest.validate_schema(raw_df)
    print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")
except SystemExit:
    raise   # Let clean SystemExit messages through as-is
except Exception as e:
    sys.exit(f"Unexpected error during ingestion: {e}")
```

This pattern — `SystemExit` passes through, all other exceptions
are caught and re-raised as clean messages — will be reused for
every subsequent stage in `main.py`.

---

## Verify When Done

### Installation

- [ ] `python -c "import pandas; print(pandas.__version__)"` prints
      a `2.x` version string
- [ ] `pip show matplotlib` returns "not found" — confirming
      just-in-time install discipline is intact

### File Loading

- [ ] `python main.py --file data/turbine.csv` prints
      `[LOAD] 52,608 rows × 5 columns` (row count may vary
      by dataset version — confirm it's non-zero)
- [ ] `python main.py --file data/doesnotexist.csv` exits with
      `Error: File not found — data/doesnotexist.csv`
      and no Python traceback visible
- [ ] `python main.py --file data/turbine.csv` with a non-CSV
      file (rename any `.txt` file to test) exits with
      `Error: Could not read file —` and no traceback

### Schema Validation

- [ ] Temporarily rename a column in the CSV header row and rerun —
      the script exits with a message listing the missing column
      by name, and all expected columns are listed. Restore the
      header after testing.
- [ ] The missing columns list in the error derives from config
      constants — verified by checking `ingest.py` source contains
      no raw column name strings

### Code Standards

- [ ] `ingest.py` contains exactly two functions: `load_csv` and
      `validate_schema`
- [ ] Both functions have complete docstrings (what, parameters,
      return, raises)
- [ ] Both functions have type hints on all parameters and
      return values
- [ ] `python -c "import ingest"` runs silently with no output —
      confirming no side effects on import
- [ ] No raw column name strings appear anywhere in `ingest.py`
      — all column references go through `config.COL_*`
- [ ] `main.py` is the only file that prints to the terminal
      (`ingest.py` contains no `print()` calls)

### Pipeline Integrity

- [ ] `python main.py --file data/turbine.csv` still prints the
      `--file`, `--folder`, `--output` stub lines from Unit 1 —
      confirm the stub was cleanly replaced, not duplicated
- [ ] `python -c "import config; import ingest"` runs silently —
      both modules importable with no side effects
