# Unit 07: Batch Mode

## Goal

Extend `main.py` with `--folder` flag logic that iterates every
`.csv` file in a given directory, runs each through the full
pipeline, concatenates the cleaned DataFrames with a `source_file`
column, and produces one consolidated report — skipping any
malformed file with a plain-English warning without crashing the
run.

---

## Implementation

### 1. What Changes in This Unit

Batch mode is entirely contained in `main.py`. No other module is
modified. The existing single-file pipeline (`--file`) is not
touched — batch mode is an additional code path that calls the
same modules in the same order, wrapped in a loop.

The only structural addition is a `run_batch()` function in
`main.py` alongside the existing `run_single()` function (which
is what the single-file pipeline becomes when refactored in this
unit).

---

### 2. Refactor `main()` into Two Paths

Before adding batch logic, refactor the existing `main()` pipeline
body into a named function `run_single()`. This makes the batch
loop clean — it calls `run_single()` per file rather than
duplicating inline code.

**Refactor `main()` so it dispatches to the correct path:**

```python
def main() -> None:
    """
    Orchestrate the pipeline. Dispatches to run_single() or
    run_batch() based on which flag was provided.
    """
    args = parse_args()

    if args.file and args.folder:
        sys.exit("Error: Provide either --file or --folder, not both.")

    if not args.file and not args.folder:
        sys.exit("Error: You must provide either --file or --folder.")

    if args.file:
        run_single(args.file, args.output)
    else:
        run_batch(args.folder, args.output)
```

---

### 3. `run_single(file_path, output_dir)` — Extracted Pipeline

Extract the existing `main()` pipeline body into `run_single()`.
The function signature changes: it now accepts `file_path` and
`output_dir` as explicit arguments rather than reading from `args`.
This makes it callable from both `main()` (single-file mode) and
`run_batch()` (once per file in the folder).

```python
def run_single(file_path: Path, output_dir: Path) -> None:
    """
    Run the full pipeline on a single CSV file.

    Stages: LOAD → CLEAN → ANALYSE → VISUALISE → EXPORT

    Parameters:
        file_path (Path): path to the SCADA CSV file to process
        output_dir (Path): directory to write the report to

    Returns:
        None

    Side effects:
        - Appends entries to logs/data_quality.log
        - Writes .png files to output/charts/
        - Writes one .xlsx report to output_dir
    """
    # ── LOAD ──────────────────────────────────────────────────────
    try:
        raw_df = ingest.load_csv(file_path)
        ingest.validate_schema(raw_df)
        print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during ingestion: {e}")

    # ── CLEAN ─────────────────────────────────────────────────────
    try:
        rows_before = len(raw_df)
        clean_df, run_id = clean.clean(raw_df)
        rows_after = len(clean_df)
        dropped = rows_before - rows_after
        print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during cleaning: {e}")

    # ── ANALYSE ───────────────────────────────────────────────────
    try:
        results = analyse.analyse(clean_df)
        print("[ANALYSE]")
        for key, result_df in results.items():
            print(f"\n--- {key} ({len(result_df)} rows) ---")
            print(result_df.head())
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during analysis: {e}")

    # ── VISUALISE ─────────────────────────────────────────────────
    try:
        chart_paths = visualise.visualise(results)
        print("[VISUALISE]")
        for path in chart_paths:
            print(f"  Chart saved → {path}")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during visualisation: {e}")

    # ── EXPORT ────────────────────────────────────────────────────
    try:
        print("[EXPORT]")
        report_path = export.export(
            clean_df=clean_df,
            results=results,
            chart_paths=chart_paths,
            run_id=run_id,
            output_dir=output_dir,
        )
        print(f"Report saved → {report_path}")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during export: {e}")
```

Verify that `python main.py --file data/turbine.csv` still works
identically after this refactor before writing any batch logic.

---

### 4. `run_batch(folder_path, output_dir)` — Batch Entry Point

Iterates all `.csv` files in `folder_path`, processes each through
the full pipeline collecting cleaned DataFrames, then produces one
consolidated report from the combined data.

```python
def run_batch(folder_path: Path, output_dir: Path) -> None:
    """
    Run the pipeline on all .csv files in a folder.

    Processes each CSV through ingest and clean independently.
    Concatenates clean DataFrames with a source_file column.
    Produces one consolidated report from the combined data.

    Files that fail ingestion or cleaning are skipped with a
    plain-English warning. Processing continues for remaining files.

    Parameters:
        folder_path (Path): directory containing SCADA CSV files
        output_dir (Path): directory to write the consolidated report to

    Returns:
        None

    Side effects:
        - Appends entries to logs/data_quality.log (one set per file)
        - Writes .png files to output/charts/
        - Writes one consolidated .xlsx report to output_dir
    """
    if not folder_path.exists():
        sys.exit(f"Error: Folder not found — {folder_path}")

    csv_files = sorted(folder_path.glob("*.csv"))

    if not csv_files:
        sys.exit(f"Error: No .csv files found in {folder_path}")

    print(f"[BATCH] Found {len(csv_files)} CSV file(s) in {folder_path}")

    cleaned_frames: list[pd.DataFrame] = []
    last_run_id: str = ""

    for csv_path in csv_files:
        print(f"\n[BATCH] Processing: {csv_path.name}")

        # ── LOAD (per file) ───────────────────────────────────────
        try:
            raw_df = ingest.load_csv(csv_path)
            ingest.validate_schema(raw_df)
            print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")
        except SystemExit as e:
            print(f"[SKIP] {csv_path.name} — {e}")
            continue
        except Exception as e:
            print(f"[SKIP] {csv_path.name} — Unexpected error during ingestion: {e}")
            continue

        # ── CLEAN (per file) ──────────────────────────────────────
        try:
            rows_before = len(raw_df)
            clean_df, run_id = clean.clean(raw_df)
            rows_after = len(clean_df)
            dropped = rows_before - rows_after
            print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
            last_run_id = run_id
        except SystemExit as e:
            print(f"[SKIP] {csv_path.name} — {e}")
            continue
        except Exception as e:
            print(f"[SKIP] {csv_path.name} — Unexpected error during cleaning: {e}")
            continue

        # Add source_file column before collecting
        clean_df = clean_df.copy()
        clean_df.insert(0, "source_file", csv_path.name)
        cleaned_frames.append(clean_df)

    # ── Guard: nothing survived cleaning ─────────────────────────
    if not cleaned_frames:
        sys.exit(
            "Error: No files were successfully processed. "
            "Check the [SKIP] messages above for details."
        )

    # ── Concatenate all cleaned frames ────────────────────────────
    print(f"\n[BATCH] Concatenating {len(cleaned_frames)} cleaned file(s)...")
    consolidated_df = pd.concat(cleaned_frames, ignore_index=True)
    print(f"[BATCH] Consolidated: {len(consolidated_df):,} total rows")

    # ── ANALYSE (on consolidated data) ───────────────────────────
    try:
        results = analyse.analyse(consolidated_df)
        print("[ANALYSE]")
        for key, result_df in results.items():
            print(f"\n--- {key} ({len(result_df)} rows) ---")
            print(result_df.head())
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during analysis: {e}")

    # ── VISUALISE (on consolidated data) ─────────────────────────
    try:
        chart_paths = visualise.visualise(results)
        print("[VISUALISE]")
        for path in chart_paths:
            print(f"  Chart saved → {path}")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during visualisation: {e}")

    # ── EXPORT (consolidated report) ──────────────────────────────
    try:
        print("[EXPORT]")
        report_path = export.export(
            clean_df=consolidated_df,
            results=results,
            chart_paths=chart_paths,
            run_id=last_run_id,
            output_dir=output_dir,
        )
        print(f"Report saved → {report_path}")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during export: {e}")
```

---

### 5. `source_file` Column Behaviour

The `source_file` column is added by `run_batch()` in `main.py`
— not by `ingest.py` or `clean.py`. This keeps those modules
unaware of batch mode, consistent with their defined boundaries.

**Insertion rules:**
- Column name is the string `"source_file"` — hardcoded here
  because it is a pipeline-layer concern, not a SCADA data
  concern and not referenced in `config.py`
- Value is `csv_path.name` — the filename only, not the full path
  (e.g. `"turbine_2018.csv"`, not `"data/turbine_2018.csv"`)
- Inserted at position 0 (leftmost column) using `df.insert()`
  so it is the first column the reader sees in the Clean Data sheet
- Added after cleaning, not before — cleaning operates on the
  raw SCADA schema and must not encounter an unexpected column

---

### 6. Error Handling Philosophy for Batch Mode

In single-file mode, any failure exits the pipeline immediately
with `sys.exit()`. In batch mode, per-file failures must not
abort the run — the failed file is skipped and the run continues.

**The distinction:**
- `[LOAD]` and `[CLEAN]` errors per file → `[SKIP]` warning,
  `continue` to the next file
- `[ANALYSE]`, `[VISUALISE]`, `[EXPORT]` errors on consolidated
  data → `sys.exit()` — these operate on the full dataset and
  there is no recovery path

**Skip message format:**
```
[SKIP] turbine_bad.csv — Error: Schema validation failed.
Missing columns: ['Wind Speed (m/s)']
```

The `[SKIP]` prefix makes skipped files immediately visible in
the terminal output without requiring the user to scroll through
all `[LOAD]`/`[CLEAN]` lines.

---

### 7. `parse_args()` — No Changes Needed

The `--folder` flag was already defined in Unit 1's `parse_args()`
as a `Path` type argument. No changes to argument parsing are
needed. The dispatch logic in `main()` is the only addition.

Confirm `--folder` is already present by running:
```bash
python main.py --help
```
Expected output includes: `--folder FOLDER`.

---

## Dependencies

No new packages. All libraries (`pandas`, `matplotlib`, `seaborn`,
`openpyxl`) were installed in previous units.

---

## Verify When Done

### Setup — Create a Second Test CSV

Batch mode requires at least two CSV files to verify the
consolidation. Create a second CSV by copying and renaming:

```powershell
Copy-Item data\turbine.csv data\turbine_copy.csv
```

This gives you `data/turbine.csv` and `data/turbine_copy.csv`
for testing. Delete `turbine_copy.csv` after verification.

### Single-File Mode Unchanged
- [ ] `python main.py --file data/turbine.csv` still produces a
      report with no errors — refactor did not break anything
- [ ] Output and behaviour are identical to pre-refactor runs

### Argument Validation
- [ ] `python main.py` (no flags) exits with:
      `Error: You must provide either --file or --folder.`
- [ ] `python main.py --file data/turbine.csv --folder data/`
      exits with:
      `Error: Provide either --file or --folder, not both.`
- [ ] `python main.py --folder data/nonexistent/` exits with:
      `Error: Folder not found — data/nonexistent`
- [ ] `python main.py --folder data/empty/` (create an empty
      folder to test) exits with:
      `Error: No .csv files found in data/empty`

### Batch Run — Two Valid Files
- [ ] `python main.py --folder data/` processes both
      `turbine.csv` and `turbine_copy.csv`
- [ ] Terminal shows `[BATCH] Found 2 CSV file(s)` at the start
- [ ] Terminal shows `[BATCH] Processing: turbine.csv` and
      `[BATCH] Processing: turbine_copy.csv` separately
- [ ] Terminal shows `[BATCH] Consolidated: N total rows` where
      N is exactly double the single-file row count
- [ ] One consolidated report is written to `output/`
- [ ] The consolidated report's Clean Data sheet row count equals
      the sum of both input files (verify in Excel)

### `source_file` Column
- [ ] Open the consolidated report's Clean Data sheet — the
      first column is `source_file`
- [ ] `source_file` values are filenames only —
      `turbine.csv` and `turbine_copy.csv`, not full paths
- [ ] Every row has a non-empty `source_file` value
- [ ] Filtering the Clean Data sheet by `source_file` correctly
      separates rows from each origin file

### Graceful Skip on Malformed File
- [ ] Create a malformed CSV: `echo "bad,data" > data\broken.csv`
- [ ] Run `python main.py --folder data/`
- [ ] Terminal shows a `[SKIP] broken.csv —` message with a
      plain-English reason
- [ ] Pipeline continues and produces a consolidated report from
      the two valid files — it does not crash
- [ ] Delete `data\broken.csv` after testing

### Consolidated Report Quality
- [ ] All six sheets are present in the consolidated report
- [ ] Summary sheet narrative reflects the consolidated dataset
      values, not a single file's values
- [ ] Charts are generated from the consolidated data
- [ ] Data Quality Log sheet contains entries from the last
      successfully processed file's `run_id`

### Code Standards
- [ ] No pipeline logic was duplicated — `run_single()` and
      `run_batch()` both call the same `ingest`, `clean`,
      `analyse`, `visualise`, `export` modules
- [ ] `source_file` column is added in `main.py` only —
      not in `ingest.py` or `clean.py`
- [ ] `source_file` value is `csv_path.name`, not `str(csv_path)`
- [ ] All functions have complete docstrings
- [ ] No lateral imports introduced
