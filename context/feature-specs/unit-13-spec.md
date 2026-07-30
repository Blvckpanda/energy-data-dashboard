# Unit 13: CI Pipeline

## Goal

Add a GitHub Actions workflow that runs the pytest suite
automatically on every push and pull request to `main`, across two
Python versions, so regressions are caught before merge without
relying on manual verification.

---

## Implementation

### 1. `.github/workflows/tests.yml`

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest -v
```

**Why matrix across two Python versions:** confirms the pipeline
doesn't accidentally depend on a 3.11-only syntax feature while the
README claims `Python 3.10+` support. Catches that class of bug for
free.

**Why `cache: "pip"`:** speeds up repeated CI runs by caching
installed packages between workflow runs — no functional difference,
just faster feedback.

---

### 2. Update `README.md` — Add CI Badge

Add this badge line near the top, alongside the existing badges:

```markdown
![Tests](https://github.com/Blvckpanda/energy-data-dashboard/actions/workflows/tests.yml/badge.svg)
```

This badge turns green/red automatically based on the latest run —
no manual updating required, ever.

---

### 3. Confirm No Hidden Dependencies

The test suite must already be self-contained (synthetic fixtures,
no real dataset, no secrets) from Unit 12. Before writing the
workflow, confirm this holds:

```bash
# Simulate a completely clean environment locally
rm -rf data/* output/* logs/*
pytest -v
```

If this fails, the test suite has a hidden dependency that must be
fixed before CI will work — CI runners never have `data/` populated.

---

## Dependencies

No new packages. GitHub Actions runners provide their own Python
installation via `actions/setup-python`.

---

## Verify When Done

### Workflow Correctness
- [ ] `.github/workflows/tests.yml` is valid YAML — no syntax errors
      reported when pushed
- [ ] Pushing a commit to `main` triggers a visible run under the
      repo's **Actions** tab
- [ ] Both matrix jobs (3.10 and 3.11) complete and pass

### Failure Detection — Critical
- [ ] Temporarily break one test on purpose (e.g. change an
      assertion to something false), commit, push to a branch, open
      a PR — confirm the workflow **fails red** on that PR
- [ ] Revert the deliberate break, push again, confirm the workflow
      **passes green**
- [ ] This proves CI actually catches failures rather than just
      running silently

### Badge
- [ ] The Tests badge appears in `README.md` and renders correctly
      on GitHub (not a broken image icon)
- [ ] Badge colour reflects the actual current state of `main`
      (green if passing)

### Isolation
- [ ] CI run logs show no reference to `data/`, no attempt to
      download a dataset, and no secrets or environment variables
      required
