# Unit 08: Polish + Git

## Goal

Write a portfolio-ready `README.md` that lets a complete stranger
clone the repo and run the pipeline successfully on their first
attempt — and review the Git history so it tells a clear,
unit-by-unit story of how the project was built.

---

## Implementation

### 1. Take Screenshots Before Writing Anything

The README requires at least one real screenshot of actual output.
Take these now, before writing the README, so you have them ready
to embed.

**Screenshot 1 — Excel Summary Sheet (required):**
Open the most recent report in `output/`. Navigate to the Summary
sheet. Capture the full sheet showing the narrative paragraph and
the statistics table. Save as `docs/screenshots/summary_sheet.png`.

**Screenshot 2 — One chart (required):**
Open `output/charts/monthly_bar.png` or `wind_scatter.png` in an
image viewer. Capture or copy the image. Save as
`docs/screenshots/chart_sample.png`.

**Screenshot 3 — Terminal output (recommended):**
Run `python main.py --file data/turbine.csv` and capture the full
terminal output from `[LOAD]` to `Report saved →`. Save as
`docs/screenshots/terminal_output.png`.

Create the `docs/screenshots/` folder to hold these:

```powershell
mkdir docs\screenshots
```

Screenshots go in `docs/screenshots/` — not in `output/` (which
is gitignored) and not at the project root (which would clutter it).

---

### 2. Write `README.md`

Replace the skeleton `README.md` from Unit 1 entirely. The final
README has seven sections in this order:

---

#### Section 1 — Title and Badge Line

```markdown
# Energy Operations Data Dashboard

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![pandas](https://img.shields.io/badge/pandas-2.x-green)
![openpyxl](https://img.shields.io/badge/openpyxl-3.x-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
```

---

#### Section 2 — One-Paragraph Description

Write this yourself — it must reflect your project accurately and
read as a portfolio statement, not a template.

It must cover all four of these points in plain English:

- What the tool does (ingest, clean, analyse, export)
- What data it works with (Wind Turbine SCADA CSV data)
- What the output is (multi-sheet Excel report with embedded charts)
- Why it's relevant (mirrors real energy-sector data workflows)

**Target length:** 4–6 sentences. No bullet points. Written as
prose for a technical recruiter or industrial training assessor.

**Example structure (do not copy verbatim — write your own):**

> A command-line Python pipeline that processes Wind Turbine SCADA
> data from CSV files and produces a structured Excel report with
> embedded charts and plain-English analysis. The pipeline cleans
> raw operational data, computes power curve efficiency against
> theoretical benchmarks, and generates time-series and
> distribution visualisations — mimicking data workflows used in
> real energy operations. Built as a self-directed portfolio project
> to demonstrate practical ETL, data analysis, and reporting skills
> using industry-standard Python tooling.

---

#### Section 3 — Screenshot

Embed the Summary sheet screenshot immediately after the
description so anyone landing on the repo sees real output before
reading further:

```markdown
## Output Preview

![Summary Sheet](docs/screenshots/summary_sheet.png)
![Sample Chart](docs/screenshots/chart_sample.png)
```

---

#### Section 4 — Stack

```markdown
## Stack

| Layer        | Technology           |
| ------------ | -------------------- |
| Language     | Python 3.10+         |
| Data         | Pandas 2.x           |
| Charting     | Matplotlib + Seaborn |
| Excel export | openpyxl 3.x         |
| CLI          | argparse (stdlib)    |
```

---

#### Section 5 — Install

```markdown
## Install

**1. Clone the repo:**
git clone https://github.com/YOUR_USERNAME/energy-dashboard.git
cd energy-dashboard

**2. Create and activate a virtual environment:**

# Using venv
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Or using Anaconda
conda create -n energy-dashboard python=3.11
conda activate energy-dashboard

**3. Install dependencies:**
pip install -r requirements.txt

**4. Add your dataset:**
Place your Wind Turbine SCADA CSV file in the data/ folder.
The file must contain these columns:
- Date/Time
- LV ActivePower (kW)
- Wind Speed (m/s)
- Theoretical_Power_Curve (KWh)
- Wind Direction (degrees)

A compatible dataset is available on Kaggle:
https://www.kaggle.com/datasets/berkerisen/wind-turbine-scada-dataset
```

---

#### Section 6 — Usage

```markdown
## Usage

**Single file:**
python main.py --file data/turbine.csv

**Single file with custom output directory:**
python main.py --file data/turbine.csv --output output/

**Batch mode (process all CSVs in a folder):**
python main.py --folder data/

**Help:**
python main.py --help
```

Then embed the terminal output screenshot:

```markdown
### Terminal Output

![Terminal Output](docs/screenshots/terminal_output.png)
```

Then describe what the pipeline produces:

```markdown
### Output

Each run produces:
- `output/report_YYYY-MM-DD.xlsx` — six-sheet Excel report:
  - **Summary** — narrative paragraph + headline statistics
  - **Clean Data** — full cleaned dataset
  - **Trend Analysis** — monthly and daily aggregations
  - **Power Curve Analysis** — efficiency ratios (operational periods only)
  - **Charts** — embedded trend, scatter, and bar charts
  - **Data Quality Log** — cleaning decisions for this run
- `output/charts/` — three standalone chart images:
  - `power_trend.png` — daily active power over time
  - `wind_scatter.png` — wind speed vs output with theoretical overlay
  - `monthly_bar.png` — monthly mean active power
- `logs/data_quality.log` — append-only audit log across all runs
```

---

#### Section 7 — Project Structure

```markdown
## Project Structure

energy-dashboard/
├── main.py              # CLI entry point and pipeline orchestrator
├── ingest.py            # CSV loading and schema validation
├── clean.py             # Data cleaning and quality logging
├── analyse.py           # Statistics, aggregations, efficiency
├── visualise.py         # Chart generation (.png)
├── export.py            # Excel workbook assembly
├── config.py            # All constants — single source of truth
├── requirements.txt     # Pinned dependencies
│
├── data/                # Input CSV files (not tracked in git)
├── output/              # Generated reports and charts (not tracked)
├── logs/                # data_quality.log (not tracked)
├── docs/
│   └── screenshots/     # README images
└── context/             # Project architecture and spec documents
```

---

### 3. Review and Clean the Git History

Before making the Unit 8 commit, review the full Git log:

```powershell
git log --oneline
```

**Expected output (8 commits minimum, most recent first):**
```
abc1234 Implement batch mode for folder processing
def5678 Implement Excel report export
ghi9012 Implement visualisation and chart export
jkl3456 Implement analysis and printed preview
mno7890 Implement cleaning pipeline and quality log
pqr1234 Implement ingestion module and schema validation
stu5678 Add project scaffold, config, and CLI shell
```

**If any commit messages are vague** (e.g. `fix`, `update`,
`wip`, `stuff`, `changes`) and have not been pushed yet, amend
them:

```powershell
# Amend the most recent unpushed commit message
git commit --amend -m "Correct imperative message here"
```

For older unpushed commits, use interactive rebase:
```powershell
git rebase -i HEAD~N   # N = number of commits to review
```

**Do not rewrite history for commits already pushed to GitHub.**
If all 7 previous commits are already pushed, accept them as-is
and make sure the Unit 8 commit message is clean.

---

### 4. Update `context/progress-tracker.md`

Before the final commit, update the progress tracker manually:

- Mark Unit 8 as `Complete` and `Verified` in the Unit Status table
- Confirm all 8 units show `Complete` in the status table
- Review the Open Questions section — each question must be either:
  - Marked `Resolved` with the resolution date and decision, or
  - Marked `Deferred` with a one-line note explaining why

All three questions were resolved earlier in the project. Confirm
the resolved dates and decisions are filled in — they should be
from previous sessions but double-check nothing is blank.

---

### 5. Final Commit

Stage everything including screenshots, updated README, and
updated progress tracker:

```powershell
git add .
git status
```

Confirm staged files include:
- `README.md`
- `docs/screenshots/summary_sheet.png`
- `docs/screenshots/chart_sample.png`
- `docs/screenshots/terminal_output.png`
- `context/progress-tracker.md`

Confirm `output/`, `data/`, and `logs/` do NOT appear in
`git status` — they are gitignored.

Then commit and push:

```powershell
git commit -m "Finalise README and polish for portfolio"
git push origin main
```

---

### 6. Verify the GitHub Repo Presentation

After pushing, open your GitHub repo in a browser and check:

- The README renders correctly — screenshots display as images,
  not broken links
- The stack table renders correctly
- Code blocks render with syntax highlighting
- The repo description (the one-line subtitle under the repo name
  on GitHub) is set — click the gear icon next to "About" and
  add: `Python pipeline for Wind Turbine SCADA data analysis and Excel reporting`
- Add relevant topics under the "About" gear:
  `python`, `pandas`, `data-analysis`, `etl`, `excel`, `energy`,
  `scada`, `matplotlib`, `openpyxl`

Topics make the repo discoverable and signal intentional
project framing to anyone viewing your portfolio.

---

## Dependencies

No new packages. This unit contains no pipeline code.

---

## Verify When Done

### README Content
- [ ] README opens on GitHub and renders without broken images
      or malformed markdown
- [ ] The description paragraph is 4–6 sentences of original
      prose — not copied from this spec
- [ ] Description covers: what it does, what data it uses,
      what it produces, why it's relevant
- [ ] At least one screenshot of real output is visible on the
      README (not a placeholder or broken link)
- [ ] Install section includes all four steps: clone, venv,
      pip install, add dataset
- [ ] Usage section shows both `--file` and `--folder` examples
- [ ] Output section correctly describes all six Excel sheets
      and three chart files
- [ ] Project structure section matches the actual folder layout
- [ ] No placeholder text remains (no `[PLACEHOLDER]` tags,
      no `YOUR_USERNAME` unless GitHub username was substituted)

### Clone Test — Critical
- [ ] On a second machine or in a fresh folder, clone the repo:
      `git clone https://github.com/YOUR_USERNAME/energy-dashboard.git`
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `python main.py --file data/turbine.csv` produces a report
      with no errors and no additional setup
- [ ] If a second machine is not available: delete `.venv/`,
      create a fresh environment, install from `requirements.txt`,
      and run — same result expected

### Git History
- [ ] `git log --oneline` shows at minimum 8 commits
- [ ] Every commit message is imperative and descriptive
      (starts with a verb: Add, Implement, Finalise)
- [ ] No commit messages are vague: no `fix`, `update`, `wip`,
      `changes`, `stuff`, or single-word messages
- [ ] Most recent commit is
      `Finalise README and polish for portfolio`

### Progress Tracker
- [ ] All 8 units show `Complete` and `Verified` in the
      Unit Status table in `context/progress-tracker.md`
- [ ] All three open questions show a `Resolved` date and
      resolution — no blank cells in the Resolved column
- [ ] Decisions Log contains at minimum the 10 entries recorded
      across the build

### GitHub Repo
- [ ] Repo is set to Public
- [ ] Repo has a one-line description set under "About"
- [ ] At least 5 topic tags are added
- [ ] `data/`, `output/`, and `logs/` folders do not appear in
      the repo file browser — confirmed gitignored
- [ ] `context/` folder is visible and all `.md` files are
      readable on GitHub — this is a portfolio differentiator

### Portfolio Readiness
- [ ] A technical recruiter can understand what the project does
      from the README alone without opening any code
- [ ] A peer unfamiliar with the project can run it successfully
      using only the README instructions
- [ ] The repo communicates intentional engineering decisions —
      the `context/` folder, `CLAUDE.md`, and structured commit
      history all signal deliberate process, not just output
