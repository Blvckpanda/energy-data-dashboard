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
    module in sequence.
    """
    args = parse_args()

    # ── Unit 2: Ingestion ─────────────────────────────────────────
    try:
        raw_df = ingest.load_csv(args.file)
        ingest.validate_schema(raw_df)
        print(f"[LOAD] {len(raw_df):,} rows × {len(raw_df.columns)} columns")
    except SystemExit:
        raise
    except Exception as e:
        sys.exit(f"Unexpected error during ingestion: {e}")

    # ── Unit 3: Cleaning ─────────────────────────────────────────────
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


if __name__ == "__main__":
    main()