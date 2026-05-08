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
