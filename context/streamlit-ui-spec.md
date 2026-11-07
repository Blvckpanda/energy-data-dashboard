# Streamlit UI Spec (pre-implementation)

Status: proposed, not implemented.
Date: 2026-11-07.

This is the spec for the confirmed next unit: a thin Streamlit UI in
this repository, layered over the existing pipeline. It is not code.
Its job is to settle the decisions that would otherwise be revisited
mid-implementation, above all the Python version floor.

## Goal

Give the pipeline a web face that a recruiter or reviewer can use
without a terminal:

- pick a schema (wind, solar, hydro) from the registry,
- upload a CSV, or load the local demo dataset when present,
- run the existing pipeline and see the same numbers the CLI produces,
- read the narrative, KPI statistics, anomalies, quality note and
  power curve, view the four charts,
- download the Excel and self-contained HTML reports.

The UI is a presentation layer. It contains no analysis logic and no
schema-specific branches; everything comes from `config.SCHEMA_REGISTRY`
and the pipeline modules.

## Decision 1: Python floor (settled here)

Streamlit 1.66 (released 2026-10-14) requires Python >= 3.11 because
Python 3.10 reached end of life in October 2026. Community Cloud
defaults to Python 3.12 and only offers versions still receiving
security updates.

**Decision: raise the project floor to Python >= 3.11 and move the CI
matrix to 3.11 and 3.12.** Implementation details:

- `pyproject.toml`: `requires-python = ">=3.11"` (and any classifier
  updates).
- CI: replace the 3.10 leg with 3.12, keeping 3.11 as the floor.
- `Dockerfile`: base image `python:3.12-slim`.
- `context/architecture.md` stack row changes from "Python 3.10+" to
  "Python 3.11+".

Alternatives considered and rejected:

- **Pin Streamlit 1.65.x** to keep 3.10: keeps a dead runtime alive,
  loses security fixes, and leaves Cloud out of reach because Cloud
  only supports maintained Python versions.
- **Separate UI-only environment on 3.11+** while core stays on 3.10:
  two environments to install, test and document, for no user benefit;
  the pipeline itself runs unchanged on 3.11 and 3.12.

Consequence to state in the README: Python 3.10 users lose support.
Nothing in the codebase requires 3.10.

## Prerequisite unit: the pipeline facade

Today `main._run_pipeline(df, run_id, output_dir, schema, fmt)` prints
progress, writes reports and returns `None`. The UI cannot read those
values, and importing `main` to trigger prints is wrong for a web app.

Extract a facade module, `pipeline.py`, with one pure-ish entry point:

```python
def run(df, schema, output_dir, run_id=None, fmt="both"):
    """Run ANALYSE -> DETECT -> VISUALISE -> EXPORT.

    Returns a dict with results, chart_paths, report_paths and
    run_ids. Writes charts and reports under output_dir; performs
    no printing.
    """
```

`main._run_pipeline` becomes a thin wrapper that calls `pipeline.run`
and prints the same summaries it does today. The CLI's observable
behaviour must not change: same files, same order, same messages.

This extraction ships as its own PR, with no Streamlit dependency, and
is guarded by the existing end-to-end tests. The UI unit depends on it.

## Decision 2: dependencies

Streamlit stays out of the core `requirements.txt`:

- `requirements-ui.txt`: `streamlit>=1.66,<2.0`, plus `-r requirements.txt`.
- Core installs keep working for CLI and Docker users exactly as today.
- The UI-only CI job installs the UI requirements.

## UI design

Single file, `ui/app.py`, plus `ui/__init__.py`. No other UI modules
until one file becomes unwieldy.

- **Sidebar**: schema select from `config.SCHEMA_REGISTRY` keys, file
  uploader (`st.file_uploader`, CSV), "Use local demo data" checkbox
  enabled only when `data/turbine.csv` exists, output format picker
  (Excel / HTML / both), Run button.
- **Main area**, after a run: KPI cards from the shared headline
  statistics builder, narrative paragraph, then tabs: Anomalies,
  Data Quality, Power Curve (wind only, hidden when absent), Charts.
- **Downloads**: `st.download_button` for the generated `.xlsx` and
  `.html` files.
- **State**: the parsed upload is cached with `st.cache_data` keyed on
  file hash plus schema; a run writes into a per-session
  `tempfile.TemporaryDirectory`, so nothing lands in the repository.
- **Errors**: validation and pipeline errors surface through
  `st.error` with the pipeline's existing plain-English messages.
  No tracebacks in the UI.

No JavaScript, no custom components, no external assets. Charts are the
pipeline's own PNGs shown with `st.image`; the downloadable HTML keeps
its base64 embedding.

## Testing

- `tests/test_pipeline_facade.py`: facade returns results, chart paths
  and report paths for a synthetic frame; `main` behaviour unchanged.
- `tests/test_ui_app.py` using `streamlit.testing.v1.AppTest`: schema
  list renders, invalid upload shows a plain error, a synthetic valid
  run reaches the KPI section. AppTest needs no browser.
- CI gains one `ui` job (Python 3.12) running
  `pip install -r requirements-ui.txt && pytest tests/test_ui_app.py`.
  The core jobs stay as they are, at 3.11 and 3.12 after the floor
  change.

## Deployment

Streamlit Community Cloud, public repository, public app. Verified
limits and behaviour as of 2026-11-07:

- 690 MB minimum / 2.7 GB maximum RAM, 0.078 to 2 CPU cores;
- the app sleeps after 12 hours without visitors and wakes on a click;
- one private app per account, no custom domains;
- Debian 11 environment, Python 3.12 by default, version selectable
  from maintained releases;
- dependencies come from `requirements*.txt`, so the UI requirements
  file must be the app's requirements file and must pin Streamlit.

Deployment is a human step: create the app from the repository, set
`ui/app.py` as the entrypoint, Python 3.12, and note the sleep caveat
in the README. The memory profile of a full wind run (50,530 rows,
four PNGs) fits the 2.7 GB ceiling; the spec requires an actual local
memory measurement before deploying, recorded in the PR.

## Deliverables, in order

1. Python floor change (3.11+), CI matrix 3.11/3.12, Docker 3.12.
2. Pipeline facade extraction, no behaviour change.
3. UI implementation, UI requirements file, CI UI job, README section.
4. Community Cloud deployment, human step, link added to README.

## Acceptance criteria

- `streamlit run ui/app.py` opens locally and runs each schema on
  synthetic input without touching the repository working tree.
- For the same CSV, the UI's headline numbers match the CLI's report.
- Downloads match the CLI's generated files in content.
- Core suite green at 3.11 and 3.12, ruff clean, UI tests green.
- Failure paths show readable messages, never tracebacks.
- The deployed app wakes from sleep and runs within Cloud limits.

## Out of scope

Authentication, user accounts, persistence, multi-user sessions,
scheduled runs, cloud storage, forecasting, and any restructuring of
the pipeline beyond the facade extraction.
