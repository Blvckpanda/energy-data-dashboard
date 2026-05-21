"""Utility script to generate required screenshots for the README.

The script creates three PNG files in ``docs/screenshots``:

1. ``summary_sheet.png`` – renders the narrative paragraph from the
   latest Excel report's Summary sheet.
2. ``chart_sample.png`` – copies an existing chart image (monthly bar).
3. ``terminal_output.png`` – runs the pipeline on a single CSV file and
   captures the full terminal output as an image.

These images are used in the final README to demonstrate the project
output without relying on the ``output/`` directory, which is git‑ignored.
"""

import os
import glob
import subprocess
import matplotlib.pyplot as plt
import openpyxl

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "docs", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Summary sheet narrative screenshot
# ---------------------------------------------------------------------------
report_files = sorted(glob.glob(os.path.join(BASE_DIR, "output", "report_*.xlsx")))
if report_files:
    latest_report = report_files[-1]
    wb = openpyxl.load_workbook(latest_report, read_only=True, data_only=True)
    ws = wb["Summary"]
    narrative = ws["A1"].value or ""
    plt.figure(figsize=(8, 6))
    plt.text(0.5, 0.5, narrative, wrap=True, ha="center", va="center", fontsize=10)
    plt.axis("off")
    plt.savefig(os.path.join(SCREENSHOT_DIR, "summary_sheet.png"), bbox_inches="tight")
    plt.close()

# ---------------------------------------------------------------------------
# 2. Chart sample – copy an existing chart image
# ---------------------------------------------------------------------------
source_chart = os.path.join(BASE_DIR, "output", "charts", "monthly_bar.png")
dest_chart = os.path.join(SCREENSHOT_DIR, "chart_sample.png")
if os.path.exists(source_chart):
    with open(source_chart, "rb") as src, open(dest_chart, "wb") as dst:
        dst.write(src.read())

# ---------------------------------------------------------------------------
# 3. Terminal output screenshot
# ---------------------------------------------------------------------------
cmd = [os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe"), "main.py", "--file", "data/turbine.csv"]
result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
output_text = result.stdout + result.stderr
plt.figure(figsize=(8, 6))
plt.text(0.5, 0.5, output_text, wrap=True, ha="center", va="center", fontsize=8)
plt.axis("off")
plt.savefig(os.path.join(SCREENSHOT_DIR, "terminal_output.png"), bbox_inches="tight")
plt.close()

print("Screenshots generated in", SCREENSHOT_DIR)