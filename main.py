"""
main.py

Entry point and orchestrator for the Energy Operations Data Dashboard.
Parses CLI arguments and calls pipeline modules in sequence.

Both single-file and batch modes share one _run_pipeline() stage
sequence (ANALYSE → DETECT → VISUALISE → EXPORT). Single-file runs
carry one run_id; batch runs carry every file's run_id so reports
include each file's quality-log entries. Run IDs are normalised to
a list once in _run_pipeline — the pipeline boundary — so exporters
always receive lists.

Fully registry-driven: the --schema choices, and every downstream
schema behaviour, come from config.SCHEMA_REGISTRY — adding a schema
requires only a registry entry, no changes to this module.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

import config
import ingest
import clean
import analyse
import visualise
import export
import html_export
import detect


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse and return command-line arguments.

    Parameters:
        argv (list[str] | None): argument list to parse. None uses
            sys.argv (the normal CLI path); tests pass explicit lists.

    Returns:
        argparse.Namespace with attributes:
            file   (Path | None): path to a single CSV file
            folder (Path | None): path to a folder of CSV files
            output (Path):        path to the output directory
            schema (str):         a schema name from
                                  config.SCHEMA_REGISTRY
            format (str):         "excel", "html", or "both"
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
        default=config.OUTPUT_DIR,
        help="Directory to write the report to. Defaults to the "
             "project's output/ directory (config.OUTPUT_DIR).",
    )
    parser.add_argument(
        "--schema",
        choices=sorted(config.SCHEMA_REGISTRY.keys()),
        default="wind",
        help="SCADA schema to use (choices from config.SCHEMA_REGISTRY; "
            "default: wind).",
    )
    parser.add_argument(
        "--format",
        choices=["excel", "html", "both"],
        default="excel",
        help="Report format: excel (default), html, or both.",
    )
    return parser.parse_args(argv)


def run_single(file_path: Path, output_dir: Path, schema: str, fmt: str) -> None:
    """
    Run the full pipeline on a single CSV file.

    LOAD and CLEAN run for this file only; the shared analysis,
    detection, visualisation, and export stages then run on the
    result. The report's quality-log entries are filtered to this
    run's run_id.

    Stages: LOAD → CLEAN → ANALYSE → DETECT → VISUALISE → EXPORT

    Parameters:
        file_path (Path): path to the SCADA CSV file to process
        output_dir (Path): directory to write the report and charts to
        schema (str): a schema name from config.SCHEMA_REGISTRY
        fmt (str): report format — "excel", "html", or "both"

    Returns:
        None

    Side effects:
        - Appends entries to logs/data_quality.log
        - Writes .png files to output_dir/charts/
        - Writes one or more report files to output_dir
    """
    try:
        raw_df = ingest.load_csv(file_path)
        ingest.validate_schema(raw_df, schema)
        print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during ingestion: {e}")

    try:
        rows_before = len(raw_df)
        clean_df, run_id = clean.clean(raw_df, schema)
        rows_after = len(clean_df)
        dropped = rows_before - rows_after
        print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during cleaning: {e}")

    _run_pipeline(clean_df, run_id, output_dir, schema, fmt)


def run_batch(folder_path: Path, output_dir: Path, schema: str, fmt: str) -> None:
    """
    Run the pipeline on all .csv files in a folder.

    Processes each CSV through ingest and clean independently.
    Concatenates clean DataFrames with a source_file column, then
    runs the shared analysis/export stages on the combined data.

    Stages: LOAD → CLEAN (per file) → ANALYSE → DETECT → VISUALISE
    → EXPORT (on consolidated data)

    Files that fail ingestion or cleaning are skipped with a
    plain-English warning. Processing continues for remaining files.
    Every successfully processed file's run_id is carried into the
    consolidated report, so its Data Quality Log sheet lists each
    file's cleaning decisions.

    Parameters:
        folder_path (Path): directory containing SCADA CSV files
        output_dir (Path): directory to write the consolidated report
                           and charts to
        schema (str): a schema name from config.SCHEMA_REGISTRY
        fmt (str): report format — "excel", "html", or "both"

    Returns:
        None

    Side effects:
        - Appends entries to logs/data_quality.log (one set per file)
        - Writes .png files to output_dir/charts/
        - Writes one or more consolidated report files to output_dir
    """
    if not folder_path.exists():
        sys.exit(f"Error: Folder not found — {folder_path}")

    csv_files = sorted(folder_path.glob("*.csv"))

    if not csv_files:
        sys.exit(f"Error: No .csv files found in {folder_path}")

    print(f"[BATCH] Found {len(csv_files)} CSV file(s) in {folder_path}")

    cleaned_frames: list[pd.DataFrame] = []
    run_ids: list[str] = []

    for csv_path in csv_files:
        print(f"\n[BATCH] Processing: {csv_path.name}")

        # ── LOAD (per file) ───────────────────────────────────────
        try:
            raw_df = ingest.load_csv(csv_path)
            ingest.validate_schema(raw_df, schema)
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
            clean_df, run_id = clean.clean(raw_df, schema)
            rows_after = len(clean_df)
            dropped = rows_before - rows_after
            print(f"[CLEAN] {rows_before:,} rows in → {rows_after:,} rows clean ({dropped:,} dropped)")
            run_ids.append(run_id)
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
    print(f"[BATCH] Consolidated: {len(consolidated_df):,} total rows "
          f"from {len(run_ids)} file(s)")

    _run_pipeline(consolidated_df, run_ids, output_dir, schema, fmt)


def _run_pipeline(
    df: pd.DataFrame,
    run_id: str | list[str],
    output_dir: Path,
    schema: str,
    fmt: str,
) -> None:
    """
    Run the shared post-clean stages: ANALYSE → DETECT → VISUALISE
    → EXPORT, writing reports and charts to output_dir.

    This is the pipeline boundary for run IDs: whichever shape the
    caller passes (single string, or a list from batch mode) is
    normalised here — exactly once — into a list[str] that both
    exporters receive.

    Parameters:
        df (pd.DataFrame): clean DataFrame (single file or batch-
                           concatenated with a source_file column)
        run_id (str | list[str]): this run's UUID, or the list of
                                  per-file UUIDs in batch mode
        output_dir (Path): directory to write the report and charts to
        schema (str): a schema name from config.SCHEMA_REGISTRY
        fmt (str): "excel", "html", or "both"

    Returns:
        None

    Side effects:
        - Writes .png files to output_dir/charts/
        - Writes one or more report files to output_dir
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = output_dir / "charts"

    # Single run-ID normalisation point for the whole pipeline
    run_ids: list[str] = [run_id] if isinstance(run_id, str) else list(run_id)

    # ── ANALYSE ───────────────────────────────────────────────────
    try:
        results = analyse.analyse(df, schema)
        print("[ANALYSE]")
        for key, result_df in results.items():
            print(f"\n--- {key} ({len(result_df)} rows) ---")
            print(result_df.head())
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during analysis: {e}")

    # ── DETECT ────────────────────────────────────────────────────
    try:
        results["anomalies"] = detect.detect(df, schema)
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during anomaly detection: {e}")

    # ── VISUALISE ─────────────────────────────────────────────────
    try:
        chart_paths = visualise.visualise(results, schema, charts_dir=charts_dir)
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
        if fmt in ("excel", "both"):
            report_path = export.export(
                clean_df=df,
                results=results,
                chart_paths=chart_paths,
                run_ids=run_ids,
                output_dir=output_dir,
                schema=schema,
            )
            print(f"Report saved → {report_path}")
        if fmt in ("html", "both"):
            html_path = html_export.export_html(
                clean_df=df,
                results=results,
                chart_paths=chart_paths,
                schema=schema,
                output_dir=output_dir,
                run_ids=run_ids,
            )
            print(f"Report saved → {html_path}")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during export: {e}")


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
        run_single(args.file, args.output, args.schema, args.format)
    else:
        run_batch(args.folder, args.output, args.schema, args.format)


if __name__ == "__main__":
    main()
