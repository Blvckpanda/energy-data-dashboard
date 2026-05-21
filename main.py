"""
main.py

Entry point and orchestrator for the Energy Operations Data Dashboard.
Parses CLI arguments and calls pipeline modules in sequence.
"""
import argparse
import sys
from pathlib import Path
import ingest
import clean
import analyse
import visualise
import export


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


import pandas as pd

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


if __name__ == "__main__":
    main()
