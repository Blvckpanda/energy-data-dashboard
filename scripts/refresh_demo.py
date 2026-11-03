"""
scripts/refresh_demo.py

Regenerate the committed live-demo report (docs/index.html) from the
real SCADA dataset and stamp it with the git SHA that produced it.

Background: data/ is gitignored by design, so CI can never rebuild
the demo — it is a committed build artefact. Historically refreshing
it meant a two-command ritual from the README (run the pipeline, then
rename today's report over docs/index.html). This script replaces
that ritual with one command and records provenance: an HTML comment

    <!-- demo-sha: <full git SHA> -->

inserted into the generated HTML. The CI "Live demo freshness" job
reads that stamp and fails any change to report-producing code made
without a refreshed demo.

Side effects: writes the pipeline's HTML report to a temporary
directory and overwrites docs/index.html (or --docs target).

Usage:
    python scripts/refresh_demo.py                     # refresh + stamp
    python scripts/refresh_demo.py --file my.csv       # other dataset
    python scripts/refresh_demo.py --commit            # also commit it
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

# scripts/ is not a package and the CLI entry point is `python
# scripts/refresh_demo.py` — rebalance sys.path so root modules are
# importable (see pyproject.toml's E402 exemption for this file).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

# Provenance comment inserted into the generated HTML. The CI
# freshness job greps for exactly this pattern — change both together.
STAMP_FORMAT = "<!-- demo-sha: {sha} -->"
STAMP_RE = r"<!-- demo-sha: [0-9a-f]{40} -->"
ANCHOR = '<meta charset="UTF-8">'


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse and return command-line arguments.

    Parameters:
        argv (list[str] | None): argument list to parse. None uses
            sys.argv (the normal CLI path); tests pass explicit lists.

    Returns:
        argparse.Namespace with attributes:
            file   (Path): SCADA CSV the demo is regenerated from
            schema (str):  a schema name from config.SCHEMA_REGISTRY
            docs   (Path): path to the committed demo report
            commit (bool): additionally `git add` + commit the demo
    """
    parser = argparse.ArgumentParser(
        prog="refresh_demo.py",
        description=(
            "Regenerate the committed live-demo report (docs/index.html) "
            "from the real SCADA dataset and stamp it with the git SHA "
            "that produced it."
        ),
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=config.PROJECT_ROOT / "data" / "turbine.csv",
        help="SCADA CSV to regenerate the demo from (default: "
             "data/turbine.csv — gitignored; keep a local copy).",
    )
    parser.add_argument(
        "--schema",
        choices=sorted(config.SCHEMA_REGISTRY.keys()),
        default="wind",
        help="SCHEMA_REGISTRY schema of --file (default: wind).",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=config.PROJECT_ROOT / "docs" / "index.html",
        help="Path of the committed demo report to overwrite "
             "(default: docs/index.html).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Also `git commit` the refreshed demo report.",
    )
    return parser.parse_args(argv)


def get_head_sha() -> str:
    """
    Return the full SHA of the current HEAD commit.

    Returns:
        str: 40-character git SHA of HEAD

    Raises:
        SystemExit: when not inside a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise SystemExit(
            f"Could not read the current git SHA: {e}. "
            "Run this script from inside the repository checkout."
        )
    return result.stdout.strip()


def generate_report(
    csv_path: Path,
    schema: str,
    work_dir: Path,
    python: str = sys.executable,
) -> Path:
    """
    Run the full pipeline on csv_path and return the HTML report path.

    Calls `python main.py --format html --output work_dir` so the demo
    is always produced by the exact CLI users run — no shortcut logic.

    Parameters:
        csv_path (Path): SCADA CSV to process
        schema (str): a schema name from config.SCHEMA_REGISTRY
        work_dir (Path): directory the pipeline writes the report and
            charts into (own temp dir; never the real output/)
        python (str): interpreter to invoke (defaults to the running
            one, so .venv users get the venv's pandas/matplotlib)

    Returns:
        Path: path to the newest report_*.html in work_dir

    Side effects:
        - Runs the full pipeline: appends to logs/data_quality.log and
          writes .png files under work_dir/charts/

    Assumptions:
        - csv_path exists and is readable
    """
    if not csv_path.is_file():
        raise SystemExit(
            f"Demo dataset not found: {csv_path}. data/ is gitignored by "
            "design — keep a local copy of the real dataset there, or "
            "pass --file to point at it."
        )

    try:
        subprocess.run(
            [
                python, "main.py",
                "--file", str(csv_path),
                "--schema", schema,
                "--format", "html",
                "--output", str(work_dir),
            ],
            check=True,
            cwd=config.PROJECT_ROOT,
            # Windows pipes encode output with cp1252, which crashes on
            # the pipeline's '→' separation arrow — force UTF-8 for the
            # child so captured output matches interactive-terminal runs.
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Pipeline run failed (exit {e.returncode}).")

    reports = sorted(work_dir.glob("report_*.html"), key=_mtime)
    if not reports:
        raise SystemExit(f"Pipeline produced no HTML report in {work_dir}.")
    return reports[-1]


def stamp_html(html: str, generated_on: str, sha: str) -> str:
    """
    Replace any existing provenance stamp and insert the current one.

    Idempotent by design: re-running the script on an already-stamped
    demo leaves exactly one current stamp. The comment is placed right
    after the charset meta tag so it can never affect rendering.

    Parameters:
        html (str): report HTML document
        generated_on (str): ISO date string shown in the stamp
        sha (str): full SHA of the commit the demo is generated from

    Returns:
        str: HTML document containing exactly one current stamp

    Assumptions:
        - html is the pipeline's own HTML, which contains ANCHOR exactly
    """
    without_old = re.sub(STAMP_RE + r"\n?", "", html)
    missing_anchor = ANCHOR not in without_old
    if missing_anchor:
        raise SystemExit(
            "Unexpected: generated report has no "
            f"{ANCHOR!r} marker to anchor the stamp."
        )
    stamp = (
        f"<!-- Generated on {generated_on} by scripts/refresh_demo.py\n"
        f"     {STAMP_FORMAT.format(sha=sha)} -->\n"
    )
    return without_old.replace(ANCHOR, ANCHOR + "\n" + stamp, 1)


def commit_demo(docs_path: Path) -> None:
    """
    Stage and commit docs_path with a fixed message.

    Parameters:
        docs_path (Path): refreshed demo report to commit

    Side effects:
        - Creates a git commit touching docs_path only

    Assumptions:
        - The caller is inside the repository checkout
    """
    try:
        subprocess.run(["git", "add", str(docs_path)], check=True)
        subprocess.run(
            [
                "git", "commit", "-m",
                "Refresh live demo report (scripts/refresh_demo.py)",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Git commit failed (exit {e.returncode}).")


def _mtime(path: Path) -> float:
    """
    Return a file's modification time as a sortable float.

    Parameters:
        path (Path): file to inspect

    Returns:
        float: modification time in seconds since the epoch
    """
    return path.stat().st_mtime


def main() -> None:
    """
    Orchestrate the refresh: generate, stamp, overwrite, maybe commit.
    """
    args = parse_args()
    sha = get_head_sha()

    with tempfile.TemporaryDirectory(
        prefix="refresh_demo_", dir=config.PROJECT_ROOT
    ) as tmp:
        report = generate_report(args.file, args.schema, Path(tmp))
        html = report.read_text(encoding="utf-8")

    stamped = stamp_html(html, generated_on=date.today().isoformat(), sha=sha)
    args.docs.write_text(stamped, encoding="utf-8")
    print(f"Demo refreshed -> {args.docs} (generated at {sha[:7]})")

    if args.commit:
        commit_demo(args.docs)


if __name__ == "__main__":
    main()
