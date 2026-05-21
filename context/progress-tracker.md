# Progress Tracker

## Unit Status

| Unit | Name                          | Status      | Verified |
| ---- | ----------------------------- | ----------- | -------- |
| 1    | Scaffold + Config + CLI Shell | Complete    | Yes      |
| 2    | Ingestion                     | Complete    | Yes      |
| 3    | Cleaning + Quality Log        | Complete    | Yes      |
| 4    | Analysis + Printed Preview    | Complete    | Yes      |
| 5    | Visualisation                 | Complete    | Yes      |
| 6    | Export                        | Complete    | Yes      |
| 7    | Batch Mode                    | Complete    | Yes      |
| 8    | Polish + Git                  | Complete    | Yes      |

---
+-

## Unit Definitions

### Unit 1 — Scaffold + Config + CLI Shell

Create the full folder structure. Write `config.py` with all five
SCADA column constants, output paths, date format string
(`DATE_FORMAT = "%Y-%m-%d %H:%M:%S"`), and log field names.
Create `requirements.txt` with pinned versions — not yet installed.
Write `README.md` skeleton. Wire `argparse` into `main.py` with
`--file`, `--folder`, and `--output` flags. Pipeline body is a stub
that prints received arguments.

**Done when:**

- [x] `python main.py --help` prints all three flags with descriptions
- [x] `python main.py --file data/turbine.csv` prints the received path without crashing
- [x] All directories exist: `data/`, `output/`, `output/charts/`, `logs/`, `c  ontext/`
- [x] `config.py` defines all five `COL_*` constants, `DATE_FORMAT`, `LOG_FIELDS`, `OUTPUT_DIR`, `CHARTS_DIR`, `LOG_PATH`
- [x] No column name or path string appears anywhere except `config.py`
- [x] `requirements.txt` lists `pandas`, `matplotlib`, `seaborn`, `openpyxl` — not yet installed

---

### Unit 2 — Ingestion

Implement `ingest.py`. Load a CSV with `pd.read_csv()`. Validate
that all five SCADA columns defined in `config.py` are present.
Return a raw DataFrame on success. Raise a descriptive error listing
missing columns on failure. Install `pandas` in this unit.

**Done when:**

- [x] `python main.py --file data/turbine.csv` prints `[LOAD] N rows × 5 columns`
- [x] Script exits with a plain-English error — no traceback — when a required column is missing
- [x] Script exits with a plain-English error — no traceback — when the file path does not exist
- [x] `ingest.py` is importable with no side effects
- [x] All column references use `config.COL_*` constants — no raw strings

---

### Unit 3 — Cleaning + Quality Log

Implement `clean.py`. Execute steps in this exact order:

1. Generate `run_id` (UUID4) and `run_timestamp` (ISO 8601) once
   at the top of the run — shared across all log entries for this run.
2. Remove duplicate rows; log count.
3. Coerce all four numeric columns using `pd.to_numeric(errors='coerce')`.
4. Drop rows with nulls in `COL_DATETIME` or `COL_ACTIVE_POWER`
   (critical columns). Fill nulls in `COL_WIND_SPEED`,
   `COL_THEORETICAL`, and `COL_WIND_DIRECTION` with column median
   (non-critical columns).
5. Parse `COL_DATETIME`:
   - Primary: `pd.to_datetime(df[COL_DATETIME], format=config.DATE_FORMAT)`
     where `DATE_FORMAT = "%Y-%m-%d %H:%M:%S"`
   - Fallback: if primary parse raises an error, re-attempt with
     `format='mixed'` and log a warning to the terminal:
     `[WARN] Date format inferred — verify output timestamps`
   - If both fail, raise a descriptive error and exit.
6. Append all decisions to `logs/data_quality.log` as CSV rows with
   `run_id` and `run_timestamp`.

Update `main.py` to call `clean.py` and print the `[CLEAN]` line.

**Done when:**

- [x] Terminal prints: `[CLEAN] N rows in → M rows clean (K dropped)`
- [x] `logs/data_quality.log` contains correctly structured rows with `run_id`, `run_timestamp`, `column`, `issue_type`, `row_count`, `action_taken`
- [x] Running the script twice appends new entries — does not overwrite
- [x] Both runs are distinguishable by `run_id` and `run_timestamp`
- [x] `COL_DATETIME` column is dtype `datetime64` after cleaning
- [x] All four numeric columns are dtype `float64` after cleaning

---

### Unit 4 — Analysis + Printed Preview

Implement `analyse.py`. Produce all five named result DataFrames:

- `stats`: `describe()` for `COL_ACTIVE_POWER` and `COL_WIND_SPEED`
- `efficiency`: per-row ratio of `COL_ACTIVE_POWER` to
  `COL_THEORETICAL`. Before computing, filter out all rows where
  `COL_THEORETICAL == 0` or `COL_ACTIVE_POWER <= 0`. These represent
  non-operational periods. Do not fill or replace — exclude entirely.
  Log excluded row count to terminal:
  `[ANALYSE] N rows excluded from efficiency (zero theoretical or non-positive output)`
- `monthly`: monthly mean `COL_ACTIVE_POWER` resampled from `COL_DATETIME`
- `daily`: daily total `COL_ACTIVE_POWER` resampled from `COL_DATETIME`
- `wind_bins`: frequency count of `COL_WIND_DIRECTION` across
  16 compass segments (0–360° in 22.5° bins)

Update `main.py` to call `analyse.py`, print `[ANALYSE]`, and print
a 5-row terminal preview of each result key for immediate verification.

**Done when:**

- [x] Terminal prints `[ANALYSE]` and a 5-row preview of all five result keys
- [x] `stats` contains mean, std, min, max for both `COL_ACTIVE_POWER` and `COL_WIND_SPEED`
- [x] `efficiency` contains no rows where `COL_THEORETICAL == 0` or `COL_ACTIVE_POWER <= 0`
- [x] Terminal prints the count of rows excluded from efficiency
- [x] `monthly` and `daily` are datetime-indexed with one row per period
- [x] `wind_bins` contains exactly 16 bins covering 0–360°
- [x] At least two values spot-checked manually against the raw CSV

---

### Unit 5 — Visualisation

Implement `visualise.py`. Produce three charts saved to
`output/charts/` as `.png`:

- `power_trend.png` — trend line: daily `COL_ACTIVE_POWER` over time
- `wind_scatter.png` — scatter: `COL_WIND_SPEED` vs `COL_ACTIVE_POWER`
  with `COL_THEORETICAL` overlaid as a distinct series with a legend
- `monthly_bar.png` — bar: monthly mean `COL_ACTIVE_POWER`

All axes labelled. All titles in plain English. Install `matplotlib`
and `seaborn` in this unit.

**Done when:**

- [x] Three `.png` files exist in `output/charts/` — non-zero file sizes
- [x] Each chart has labelled x-axis and y-axis with no raw column key names
- [x] Each chart title is a plain-English sentence
- [x] `wind_scatter.png` shows actual and theoretical as distinct series with a legend
- [x] Charts render correctly on full dataset (50,530 rows)
- [x] Charts render correctly on a 500-row slice (tested with head(500))

---

### Unit 6 — Export

Implement `export.py`. Assemble an openpyxl workbook with six
sheets in this exact order:

1. **Summary** — Two components in sequence:
   - Narrative paragraph (3–5 sentences) generated programmatically
     from analysis results. Must cover: total operational hours
     analysed, mean active power output, overall efficiency ratio,
     and one notable pattern (e.g. peak output month or dominant
     wind direction). Written in plain English. No raw column key
     names or Python variable names visible.
   - Headline statistics table below the narrative: mean, max, and
     std for `COL_ACTIVE_POWER` and `COL_WIND_SPEED`; overall
     efficiency ratio; total rows analysed; rows excluded from
     efficiency.
2. **Clean Data** — full cleaned DataFrame
3. **Trend Analysis** — `monthly` and `daily` DataFrames
4. **Power Curve Analysis** — `efficiency` DataFrame
5. **Charts** — all three `.png` figures embedded as images
6. **Data Quality Log** — quality log entries filtered to this
   run's `run_id` only

Write to `output/report_YYYY-MM-DD.xlsx`. Install `openpyxl` in
this unit.

**Done when:**

- [x] `output/report_YYYY-MM-DD.xlsx` created with today's date in filename
- [x] Workbook opens in Excel with all six sheets in correct order
- [x] Summary sheet contains narrative paragraph above the statistics table
- [x] Narrative references real computed values — not placeholder text
- [x] No raw `COL_*` key names or Python variable names visible anywhere in the workbook
- [x] Charts sheet shows all three embedded images (not linked)
- [x] Data Quality Log sheet shows only entries from the current run
- [x] Running the script twice produces two separate timestamped files

---

### Unit 7 — Batch Mode

Add `--folder` flag logic to `main.py`. When `--folder` is passed,
iterate all `.csv` files in the directory, run each through the full
pipeline, concatenate cleaned DataFrames, add a `source_file` column,
produce one consolidated report. A single malformed or
missing-column CSV must not crash the run — skip it with a
plain-English warning and continue.

**Done when:**

- [ ] `python main.py --folder data/` processes every `.csv` in the folder
- [ ] Consolidated row count equals the exact sum of all valid input CSVs
- [ ] `source_file` column correctly identifies the origin of every row
- [ ] A folder containing one malformed CSV skips it with a warning and continues
- [ ] Consolidated report contains all six sheets with data from all valid sources

---

### Unit 8 — Polish + Git

Write the final `README.md`: one-paragraph portfolio description,
install instructions (`pip install -r requirements.txt`), usage
examples for `--file` and `--folder` modes, at least one embedded
screenshot of a generated chart or the Excel Summary sheet. Review
Git history — one commit per unit, imperative commit messages.
Resolve or formally defer all remaining open questions in this file.

**Done when:**

- [ ] A peer can clone the repo, run `pip install -r requirements.txt`, and execute the pipeline on first attempt
- [ ] README includes at least one screenshot of real output
- [ ] `git log --oneline` shows at minimum 8 commits, one per unit
- [ ] All open questions below are resolved or formally deferred with a note
- [ ] All 8 units show as complete in the Unit Status table above

---

## Decisions Log

| Date       | Decision | Rationale |
| ---------- | -------- | --------- |
| 2026-05-07 | Wind Turbine SCADA schema for v1 | Real industry dataset; five well-defined columns; power curve enables meaningful analysis |
| 2026-05-07 | Quality log is append-only | Immutable audit trail; `run_id` + `run_timestamp` makes entries traceable across runs |
| 2026-05-07 | `context/` subfolder for reference docs | Keeps project root clean; separates pipeline code from reference material |
| 2026-05-07 | `config.py` stays at project root | Imported by all pipeline modules; root placement avoids relative import issues |
| 2026-05-07 | openpyxl over xlsxwriter | Supports read + write; better image embedding for chart export |
| 2026-05-07 | argparse over click | No extra dependency; sufficient for this scope |
| 2026-05-07 | No database | Data volumes don't justify it; CSV-in, Excel-out is sufficient for v1 |
| 2026-05-07 | `DATE_FORMAT = "%Y-%m-%d %H:%M:%S"` as primary; `format='mixed'` as fallback | Standard SCADA export format at 10-minute intervals; fallback handles edge cases; terminal warning issued if fallback fires |
| 2026-05-07 | Exclude `COL_THEORETICAL == 0` and `COL_ACTIVE_POWER <= 0` from efficiency | Industry KPI standard: efficiency metrics cover normal operational periods only; zero theoretical = non-operational interval; excluded count logged to terminal |
| 2026-05-07 | Summary sheet includes a programmatic narrative paragraph | Non-technical readers need context; executive summary drives decisions; raw tables alone are insufficient; narrative generated from real computed values |
| 2026-05-20 | `pd.read_csv()` called with no additional arguments in `load_csv()` | Spec explicitly prohibits date parsing or type coercion in `ingest.py` — those belong to `clean.py`. No encoding flag, no dtype hints. |
| 2026-05-20 | `SystemExit` used for error propagation in `ingest.py` | Keeps error handling simple and consistent with `main.py`'s pattern: `SystemExit` passes through the top-level try/except, all other exceptions are caught and re-raised as clean messages. |
| 2026-05-20 | Fallback uses `format='mixed'` instead of `infer_datetime_format=True` | `infer_datetime_format` is deprecated in pandas 2.3.3. The CSV has varying date string formats (some `%m %d %Y %H:%M`, some `%d %m %Y %H:%M`), so `format='mixed'` is the modern replacement that correctly handles non-uniform datetime strings. |
| 2026-05-20 | `clean()` returns `(clean_df, run_id)` tuple | `run_id` is returned to `main.py` so `export.py` (Unit 6) can filter the quality log to the current run's entries when writing the Data Quality Log sheet. |
| 2026-05-20 | `_append_log` uses `csv.DictWriter` with `mode="a"` | Stdlib `csv` module avoids adding a new dependency. `DictWriter` with `config.LOG_FIELDS` as `fieldnames` ensures columns are always written in the correct order. `mode="a"` guarantees append-only behaviour — header only written on first call when file doesn't exist. |
| 2026-05-20 | Internal helpers use private `_` prefix naming | Convention distinguishes public API (`clean`) from internal helpers — only public functions called by `main.py`. |
| 2026-05-20 | `_compute_efficiency` is the only internal helper with a `print()` call | The efficiency exclusion count is defined in `code-standards.md` as required terminal output and is logically inseparable from the computation — no other internal helper prints anything. |
| 2026-05-20 | `analyse.py` uses `pd.cut(bins=config.WIND_DIRECTION_BINS)` with `sort=False` | `value_counts(sort=False)` preserves natural bin order (0→360) essential for directional (non-ranked) wind data. |
| 2026-05-20 | `visualise.py` uses `matplotlib.use("Agg")` before importing pyplot | Non-interactive backend required for headless server compatibility and prevents pop-up chart windows during pipeline runs. |
| 2026-05-20 | `plt.close(fig)` called after every `fig.savefig()` | Prevents memory accumulation — on a full 50,530-row dataset, unclosed figures silently consume hundreds of MB. |
| 2026-05-20 | Scatter uses `alpha=0.15`, `s=3` for 50K-row efficiency dataset | Without low alpha and small point size, the scatter renders as a solid black mass. These values show the data density distribution clearly. |

---

## Open Questions

| # | Question | Raised | Resolved |
| - | -------- | ------ | -------- |
| 1 | What is the exact `Date/Time` format in the SCADA CSV? | 2026-05-07 | 2026-05-20 — The CSV contains mixed date formats. Primary: `%Y-%m-%d %H:%M:%S`. Fallback: `format='mixed'` (replaced deprecated `infer_datetime_format=True` for pandas 2.3.3 compatibility). Terminal warning issued if fallback fires. See Unit 3. |
| 2 | Should efficiency exclude rows where `COL_THEORETICAL == 0`? | 2026-05-07 | 2026-05-07 — Yes. Exclude all rows where `COL_THEORETICAL == 0` OR `COL_ACTIVE_POWER <= 0`. Exclude entirely — do not fill. Log excluded count. See Unit 4. |
| 3 | Should the Summary sheet include a written narrative paragraph? | 2026-05-07 | 2026-05-07 — Yes. 3–5 sentences, generated from real analysis values. Covers: operational hours, mean output, efficiency ratio, one notable pattern. Appears above the stats table. See Unit 6. |