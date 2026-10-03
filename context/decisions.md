# Decisions Log

Decisions that shaped the codebase, oldest first. Entries from
2026-05-07 through 2026-07-30 were carried over from the original
build's progress tracker (now archived at
`docs/archive/progress-tracker.md`); later entries are new.

| Date       | Decision | Rationale |
| ---------- | -------- | --------- |
| 2026-05-07 | Wind Turbine SCADA schema for v1 | Real industry dataset; five well-defined columns; power curve enables meaningful analysis |
| 2026-05-07 | Quality log is append-only | Immutable audit trail; `run_id` + `run_timestamp` makes entries traceable across runs |
| 2026-05-07 | `context/` subfolder for reference docs | Keeps project root clean; separates pipeline code from reference material |
| 2026-05-07 | `config.py` stays at project root | Imported by all pipeline modules; root placement avoids relative import issues |
| 2026-05-07 | openpyxl over xlsxwriter | Supports read + write; better image embedding for chart export |
| 2026-05-07 | argparse over click | No extra dependency; sufficient for this scope |
| 2026-05-07 | No database | Data volumes don't justify it; CSV-in, Excel-out is sufficient for v1 |
| 2026-05-07 | `DATE_FORMAT` primary; `format='mixed'` fallback | Standard SCADA export at 10-minute intervals; fallback handles edge cases with a terminal warning |
| 2026-05-07 | Exclude non-operational rows from efficiency | Industry KPI standard: ratio metrics cover normal operational periods only; excluded count logged |
| 2026-05-07 | Summary sheet includes a programmatic narrative | Non-technical readers need context; generated from real computed values |
| 2026-05-20 | `pd.read_csv()` with no extra arguments in `load_csv()` | Spec prohibits date parsing or coercion in `ingest.py` — those belong to `clean.py` |
| 2026-05-20 | `SystemExit` for error propagation in `ingest.py` | Passes through the top-level pattern cleanly; all other exceptions re-raised as plain-English messages |
| 2026-05-20 | Fallback uses `format='mixed'` | `infer_datetime_format` deprecated in pandas 2.3.3; handles the CSV's mixed date strings |
| 2026-05-20 | `clean()` returns `(clean_df, run_id)` tuple | `run_id` returned so exporters can filter the quality log to the current run |
| 2026-05-20 | `_append_log` uses `csv.DictWriter`, `mode="a"` | Stdlib only; header written only on first call; append-only guaranteed |
| 2026-05-20 | Private `_` prefix for internal helpers | Distinguishes public API (called by `main.py`) from internals |
| 2026-05-20 | `_compute_efficiency` is the only printing helper | The exclusion count is required terminal output, inseparable from the computation |
| 2026-05-20 | `pd.cut(...)` with `sort=False` for bins | Preserves natural bin order for directional (non-ranked) data |
| 2026-05-20 | `matplotlib.use("Agg")` before pyplot import | Headless compatibility; prevents pop-ups during runs |
| 2026-05-20 | `plt.close(fig)` after every `savefig()` | Prevents memory accumulation on 50K-row datasets |
| 2026-05-20 | Scatter uses `alpha=0.15`, `s=3` | Shows density instead of a solid mass at 50K points |
| 2026-07-29 | `--schema` flag over separate entry points | One pipeline, one entry point; extensible without duplication |
| 2026-07-29 | Anomaly thresholds in config, not CLI flags | Consistent with the all-thresholds-in-config invariant |
| 2026-07-29 | HTML report is a self-contained single file | Base64 charts; shareable offline; GitHub Pages deployable |
| 2026-07-29 | `SCHEMA_REGISTRY` dict over per-schema conditionals | One dict tells every module which columns, thresholds, and labels apply |
| 2026-07-29 | "Power Curve Analysis" sheet renamed "Efficiency Analysis" | Schema-neutral name works for wind and solar |
| 2026-07-29 | `wind_bins` result key renamed `distribution` | Generic key for any schema's distribution analysis |
| 2026-07-29 | Solar scatter uses ideal 1:1 line | No theoretical reference exists; y=x is the correct baseline |
| 2026-07-29 | Deduplicate efficiency columns when secondary == reference | Solar's DC_POWER is both; duplicate selection breaks visualise |
| 2026-07-29 | `detect.py` uses `isin()` for anomaly_type classification | `str.contains('threshold')` misses `'both'` |
| 2026-07-29 | `[DETECT]` prints after `[ANALYSE]`, before `[VISUALISE]` | `anomalies` must exist before the 4th chart reads it |
| 2026-07-29 | Narrative extracted to `narrative.py`, shared by exporters | Single source of truth for summary text |
| 2026-07-29 | `--format` flag over subcommands | Consistent with `--schema`; `main.py` stays one entry point |
| 2026-07-29 | Plain-English label lookup in html_export, not raw config names | "Mean Efficiency" instead of "Mean efficiency_ratio" |
| 2026-07-29 | Test suite uses fully synthetic DataFrames | Runs in any environment, including CI, without Kaggle CSVs |
| 2026-07-29 | e2e test monkeypatches config paths for isolation | Charts and logs go to tmp_path, never real project dirs |
| 2026-07-30 | CI matrix across Python 3.10 and 3.11 | Confirms the README's Python 3.10+ claim is actually tested |
| 2026-07-30 | Test suite has zero hidden dataset dependencies | Verified by clearing data/ output/ logs/ and re-running |
| 2026-07-30 | visualise creates the charts dir at runtime | Fixes Docker volume-mount bug overwriting build-time dirs |
| 2026-07-30 | Dockerfile copies source files individually | Keeps image minimal; no tests/context/docs in the container |
| 2026-09-30 | Registry-driven schemas; third schema (hydro) added | Made the schema-agnostic claim literal: labels, display names, interval, scatter kind, and distribution spec are registry keys; adding a schema touches only config.py |
| 2026-09-30 | `interval_minutes` registry key; hours derived from it | Solar (15-min) hours were overstated 1.5× by hardcoded 10-min math |
| 2026-09-30 | Anomaly timeline plots daily mean, not daily total | Instantaneous anomaly points share units with the curve they overlay |
| 2026-09-30 | Run IDs normalised once in `main._run_pipeline` | Exporters always receive `list[str]`; no repeated isinstance checks |
| 2026-09-30 | Both exporters take per-day unique filenames | Restores Invariant 6 for HTML, which silently overwrote same-day reports |
| 2026-09-30 | Batch mode carries every file's run_id into reports | A consolidated report must show each source file's cleaning decisions |
| 2026-09-30 | `charts_dir` parameter on `visualise()` | Charts follow `--output`; default `config.CHARTS_DIR` preserves compat |
| 2026-09-30 | HTML report gains a Data Quality note section | Closes the spec'd-but-missing Unit 11 item; both formats now surface cleaning decisions |
| 2026-09-30 | Shared `_run_pipeline` stage in main.py | Single-file and batch modes share ANALYSE→DETECT→VISUALISE→EXPORT; removes duplicated stage code |
| 2026-09-30 | ruff (E/F/W/I) gates CI via a lint job | Catches drift pytest cannot; one per-file E402 exemption for Agg ordering |
| 2026-09-30 | Docs consolidated: overview/architecture/standards/decisions live; unit specs archived | The 14-unit build process finished; shrinking the sync surface keeps docs honest |
| 2026-09-30 | MIT LICENSE file added | README and badge already claimed MIT; the file makes it real |
| 2026-10-03 | `analyse.efficiency_columns()` owns the efficiency column order | `export._efficiency_headers` re-derived the same selection-and-dedup as `_compute_efficiency`; one owner (with a parity test over all schemas) means the Efficiency sheet can never drift from the analysis |
| 2026-10-03 | `_print_load_summary()` shared by both run modes | Same pattern as `_print_clean_summary`: one definition of the `[LOAD]` line, byte-identical console output verified against a pre-refactor real-data run |
| 2026-10-03 | Measured power curve on IEC 61400-12-1-style bins, opt-in via registry | `power_curve_bin_width` + `power_curve_min_samples` in a schema's registry entry enable the binned curve (wind: 0.5 m/s bins, ≥3 samples ≈ the standard's 30 minutes per bin); no schema-name branch. Deviations from a full IEC campaign are disclosed in the code and the narrative, not hidden |
| 2026-10-03 | Solar ratio renamed "Performance Ratio" (IEC 61724 naming) | Industry-credible naming; the AC/DC computation is unchanged and the narrative states the scope honestly (no irradiance/temperature corrections on this dataset). Hydro claims no standard — no methodology note in its registry entry |
| 2026-10-03 | Power-curve report surface shared by both exporters | Optional 8th Excel sheet + HTML section named from one constant (`config.POWER_CURVE_SHEET_NAME`); headers come from one builder in `narrative.py`; the scatter's reference line prefers the measured curve over the shipped theoretical one |
| 2026-10-03 | GitHub Pages serves a committed report at `docs/index.html` | The demo must show real numbers, but `data/` is gitignored by design — so the self-contained HTML is generated locally from the real wind dataset and committed as a build artefact; refresh is manual and documented in the README's Live demo section. Pages serves `main` `/docs` (no Jekyll needed for a single file) |
