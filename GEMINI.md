# ## Energy Operations Data Dashboard — Agent Context

Read the following files **in full and in this exact order**
before implementing anything or making any architectural decision.
Do not begin writing code until all five files have been read.

1. `context/project-overview.md` — product definition, goals,
   features, core user flow, and explicit scope boundaries
2. `context/architecture.md` — stack, system boundaries, storage
   model, SCADA column reference, and invariants that must never
   be violated
3. `context/code-standards.md` — implementation rules covering
   Python conventions, function docstrings, configuration discipline,
   CLI output format, date parsing strategy, efficiency calculations,
   and file organisation
4. `context/ai-workflow-rules.md` — scoping rules, when to split
   work, how to handle missing or ambiguous requirements, protected
   files, and the verification checklist before moving to the next unit
5. `context/progress-tracker.md` — current unit status, unit
   definitions with done-when checklists, decisions log, and
   resolved open questions

---

## Before Writing Any Code

- Confirm which unit is currently `Not started` in
  `context/progress-tracker.md` and work on that unit only.
- Read the unit's spec file if one exists:
  `context/unit-NN-spec.md` where NN is the unit number.
- Do not implement behaviour from a future unit even if it
  seems convenient to do so now.

---

## Rules That Always Apply

- `config.py` is the single source of truth for all column names,
  file paths, date formats, and thresholds. Never hardcode these
  values anywhere else.
- Every function must have a docstring. No exceptions.
- Input files in `data/` are never modified. Ever.
- `logs/data_quality.log` is append-only. Never truncate it.
- Output filenames always include an ISO date timestamp.
- Modules do not import each other laterally. Only `main.py`
  imports from pipeline modules.
- No Python traceback may reach the user. All exceptions are caught
  in `main.py` and surfaced as plain-English messages.

---

## When to Update Context Files

Update `context/progress-tracker.md` when:

- A unit's status changes (mark it In Progress when starting,
  Complete when all checklist items pass)
- A decision is made that isn't already in the Decisions Log
- An open question is resolved

Update the relevant context file when implementation reveals that
what is documented no longer matches what was built:

- Architecture or boundary changes → `context/architecture.md`
- New or changed code conventions → `context/code-standards.md`
- Feature scope changes → `context/project-overview.md`

**Update the context file before continuing to the next unit.**
A context file that is out of sync with the code is a bug.

---

## Before Moving to the Next Unit

All five conditions must be true:

1. Every checklist item in the current unit's done-when list
   passes — verified by running the script, not by inspection.
2. No invariant in `context/architecture.md` was violated.
3. `context/progress-tracker.md` reflects the completed unit
   and all decisions made during it.
4. Every new function has a docstring.
5. No column name, file path, or threshold was hardcoded
   outside `config.py`.
