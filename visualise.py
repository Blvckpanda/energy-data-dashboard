"""
visualise.py

Owns chart generation and .png export to output/charts/.
Accepts result DataFrames from analyse.py and saves one .png
per chart. Returns a list of saved file paths for use by export.py.

Side effect: writes .png files to output/charts/.
This directory must exist before visualise() is called.
"""

from pathlib import Path
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend — no display window needed
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import config

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)


def visualise(results: dict[str, pd.DataFrame]) -> list[Path]:
    """
    Generate all three charts and save them to output/charts/.

    Parameters:
        results (dict[str, pd.DataFrame]): the full results dict
            from analyse.analyse(). Must contain keys:
            'daily', 'efficiency', 'monthly'.

    Returns:
        list[Path]: list of three Path objects pointing to the
                    saved .png files, in this order:
                    [power_trend.png, wind_scatter.png, monthly_bar.png]

    Assumptions:
        - output/charts/ directory already exists
        - 'daily' DataFrame has a DatetimeIndex and COL_ACTIVE_POWER column
        - 'efficiency' DataFrame has COL_WIND_SPEED, COL_ACTIVE_POWER,
          COL_THEORETICAL columns
        - 'monthly' DataFrame has a DatetimeIndex and COL_ACTIVE_POWER column
    """
    paths = [
        _plot_power_trend(results["daily"]),
        _plot_wind_scatter(results["efficiency"]),
        _plot_monthly_bar(results["monthly"]),
    ]
    return paths


def _plot_power_trend(daily_df: pd.DataFrame) -> Path:
    """
    Generate a line chart of daily total active power over time.

    Parameters:
        daily_df (pd.DataFrame): daily resampled DataFrame from
                                 analyse._compute_daily(). DatetimeIndex,
                                 single column COL_ACTIVE_POWER.

    Returns:
        Path: path to the saved power_trend.png file

    Assumptions:
        - daily_df has a DatetimeIndex
        - output/charts/ directory exists
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        daily_df.index,
        daily_df[config.COL_ACTIVE_POWER],
        linewidth=0.8,
        color=sns.color_palette("muted")[0],
    )

    ax.set_title("Daily Active Power Output Over Time", fontsize=14, pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Active Power (kW)", fontsize=11)
    ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "power_trend.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path


def _plot_wind_scatter(efficiency_df: pd.DataFrame) -> Path:
    """
    Generate a scatter plot of wind speed vs active power output,
    with the theoretical power curve overlaid as a line.

    Parameters:
        efficiency_df (pd.DataFrame): efficiency DataFrame from
                                      analyse._compute_efficiency().
                                      Operational rows only.
                                      Must contain COL_WIND_SPEED,
                                      COL_ACTIVE_POWER, COL_THEORETICAL.

    Returns:
        Path: path to the saved wind_scatter.png file

    Assumptions:
        - efficiency_df contains only operational rows
          (COL_THEORETICAL > 0 and COL_ACTIVE_POWER > 0)
        - output/charts/ directory exists
    """
    # Sort by wind speed so the theoretical curve line renders cleanly
    sorted_df = efficiency_df.sort_values(config.COL_WIND_SPEED)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Actual power — scatter, semi-transparent to show density
    ax.scatter(
        efficiency_df[config.COL_WIND_SPEED],
        efficiency_df[config.COL_ACTIVE_POWER],
        alpha=0.15,
        s=3,
        color=sns.color_palette("muted")[0],
        label="Actual Power Output",
    )

    # Theoretical curve — line over sorted data
    ax.plot(
        sorted_df[config.COL_WIND_SPEED],
        sorted_df[config.COL_THEORETICAL],
        linewidth=1.5,
        color=sns.color_palette("muted")[2],
        label="Theoretical Power Curve",
    )

    ax.set_title(
        "Wind Speed vs Active Power Output (with Theoretical Curve)",
        fontsize=13,
        pad=12,
    )
    ax.set_xlabel("Wind Speed (m/s)", fontsize=11)
    ax.set_ylabel("Power (kW)", fontsize=11)
    ax.legend(fontsize=10)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "wind_scatter.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path


def _plot_monthly_bar(monthly_df: pd.DataFrame) -> Path:
    """
    Generate a bar chart of monthly mean active power output.

    Parameters:
        monthly_df (pd.DataFrame): monthly resampled DataFrame from
                                   analyse._compute_monthly().
                                   DatetimeIndex at MS frequency,
                                   single column COL_ACTIVE_POWER.

    Returns:
        Path: path to the saved monthly_bar.png file

    Assumptions:
        - monthly_df has a DatetimeIndex
        - output/charts/ directory exists
    """
    # Format x-axis labels as "Jan 2018", "Feb 2018", etc.
    labels = monthly_df.index.strftime("%b %Y")

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(
        range(len(monthly_df)),
        monthly_df[config.COL_ACTIVE_POWER],
        color=sns.color_palette("muted")[1],
        edgecolor="white",
        linewidth=0.5,
    )

    ax.set_xticks(range(len(monthly_df)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_title("Monthly Mean Active Power Output", fontsize=14, pad=12)
    ax.set_xlabel("Month", fontsize=11)
    ax.set_ylabel("Mean Active Power (kW)", fontsize=11)

    fig.tight_layout()

    out_path = config.CHARTS_DIR / "monthly_bar.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path