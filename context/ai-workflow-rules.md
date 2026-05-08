# AI Workflow Rules

## Approach

Build this project incrementally using a spec-driven workflow.
The files in `context/` define what to build, how to build it,
and the current state of progress. Always implement against these
specs. Do not infer or invent behaviour not defined here. If
something is not in a context file, it does not get built.

## Scoping Rules

- Work on one feature unit at a time as listed in
  `context/progress-tracker.md`.
- Implement only what is defined for the current unit.
  Do not build ahead into the next unit.
- Prefer small, verifiable increments over large speculative changes.
- Do not combine changes to more than one module's core
  responsibility in a single implementation step.

## When to Split Work

Split an implementation step if it:

- Touches more than one module's defined responsibility at once
- Combines pipeline logic changes with output formatting changes
- Includes any behaviour not explicitly defined in the context files
- Cannot be verified end-to-end in a single script run

If you cannot run the script and confirm the output before moving
on, the scope is too broad — split it.

## Handling Missing Requirements

- Do not invent product behaviour not defined in the context files.
- If a requirement is ambiguous, stop. Update the relevant file
  in `context/` to resolve it before writing any code.
- If a requirement is missing entirely, add it as an open question
  under `## Open Questions` in `context/progress-tracker.md` and
  wait for resolution before continuing.
- Never silently assume. Surface the ambiguity explicitly.

## Protected Files

Do not modify the following unless explicitly instructed:

- `context/*.md` — All context files are source-of-truth documents.
  Update them only when implementation decisions change what they
  describe — and update them before writing the corresponding code.
- `data/*.csv` — Input files are immutable. The pipeline must never
  write to `data/`.
- `config.py` — Only add new constants when explicitly agreed.
  Do not rename or remove existing constants without updating every
  reference in every module.
- `logs/data_quality.log` — Append-only. Never truncate, overwrite,
  or manually edit this file during development.

## Keeping Docs in Sync

Update the relevant `context/` file whenever implementation
produces a decision that changes what the file describes:

- A module's responsibilities change → update `architecture.md`
- A new code convention is established → update `code-standards.md`
- A feature is added, removed, or descoped → update
  `project-overview.md`
- A unit completes or an open question resolves → update
  `progress-tracker.md`

Update the context file first. Then write the code.

## Before Moving to the Next Unit

All five conditions must be true before starting the next unit:

1. The current unit works end-to-end within its defined scope —
   verified by running the script with a real CSV and inspecting
   the output.
2. No invariant defined in `context/architecture.md` was violated.
3. `context/progress-tracker.md` reflects the completed unit,
   any decisions made, and any new open questions discovered.
4. All new functions have docstrings covering parameters, return
   value, and assumptions.
5. No column names, file paths, or thresholds were hardcoded
   outside `config.py`.
