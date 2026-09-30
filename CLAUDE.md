# Energy Operations Data Dashboard — Agent Context

This is the **single canonical agent-rules file** for this repo.
`.clinerules/.clinerules.md` is a pointer to it; the original
workflow rules and 14 unit specs are historical documents archived
under `docs/archive/`. Do not duplicate rule text in other files.

## What This Project Is

A schema-agnostic CLI pipeline: SCADA CSVs in (wind / solar / hydro),
cleaned, analysed, anomaly-flagged, and exported as Excel + HTML
reports with charts, a plain-English narrative, and an append-only
quality log. Every schema-specific behaviour is a key in
`SCHEMA_REGISTRY` in `config.py` — adding a schema touches only
config.py.

## Read Before Implementing Anything

In this exact order:

1. `context/project-overview.md` — product definition, schemas,
   features, flow, and explicit scope boundaries
2. `context/architecture.md` — stack, system boundaries, storage
   model, SCADA column reference, invariants that must never be
   violated
3. `context/code-standards.md` — Python conventions, docstrings,
   configuration discipline via the registry, CLI output format,
   date parsing, efficiency rules, lint gate, file organisation
4. `context/decisions.md` — decisions log; check it before making
   an architectural decision, update it after making one

Feature specs from the original build are archived under
`docs/archive/feature-specs/` for historical reference only — they
describe the build process, not current behaviour. When a spec and
the code disagree, the code wins and the docs get updated.

## Rules That Always Apply

- `config.py` is the single source of truth for all column names,
  file paths, thresholds, labels, and schema behaviour. Never
  hardcode these anywhere else, and never branch on a schema name
  outside config.py.
- Every function must have a docstring. No exceptions.
- Input files in `data/` are never modified. Ever.
- `logs/data_quality.log` is append-only. Never truncate it.
- Output filenames always include an ISO date and never overwrite a
  same-day report — the `_1`, `_2…` counter is enforced in BOTH
  exporters.
- Modules do not import each other laterally. Only `main.py`
  imports from pipeline modules (plus the sanctioned
  exporters → narrative.py edge).
- No Python traceback may reach the user. All exceptions are caught
  in `main.py` and surfaced as plain-English messages.
- Do not mutate a caller's DataFrame; tests assert non-mutation.
- `ruff check .` must stay clean (E/F/W/I, line-length 100) — it
  gates CI. When inspecting data files, use
  `head -n 5 data/turbine.csv` or `pd.read_csv(nrows=5)`; never
  read a whole dataset into context.

## Verification Before Finishing Any Change

1. `.venv/Scripts/python.exe -m pytest -q` — all tests green
   (62 as of the registry refactor; synthetic data only, no
   dataset needed).
2. `.venv/Scripts/python.exe -m ruff check .` — clean.
3. No invariant in `context/architecture.md` violated.
4. Any decision made during the change is recorded in
   `context/decisions.md`; any doc the change made untrue is
   updated in the same pass. **A context file out of sync with the
   code is a bug.**
5. No column name, path, threshold, or label hardcoded outside
   `config.py`.
