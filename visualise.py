"""
visualise.py

Owns chart generation and .png export to output/charts/.
Accepts result DataFrames from analyse.py and saves one .png
per chart. Returns a list of saved file paths for use by export.py.

Schema-aware: axis labels and scatter reference series vary by
schema, sourced from config.SCHEMA_REGISTRY.

Side effect: writes .png files to the charts directory
(config.CHARTS_DIR by default, or the charts_dir parameter).
"""

from pathlib import Path
import os
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend — no display window needed
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import config

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)

AXIS_LABELS = {
    "wind":  {"primary": "Active Power (kW)",  "secondary": "Wind Speed (m/s)"},
    "solar": {"primary": "AC Power (kW)",      "secondary": "DC Power (kW)"},
}


def visualise(
    results: dict[str, pd.DataFrame],
    schema: str,
    charts_dir: Path | None = None,
) -> list[Path]:
    """
    Generate all four charts and save them to the charts directory.

    Parameters:
        results (dict[str, pd.DataFrame]): the full results dict
            from analyse.analyse(). Must contain keys:
            'daily', 'daily_mean', 'efficiency', 'monthly', 'anomalies'.
        schema (str): "wind" or "solar" — selects axis labels and
                      scatter reference series logic.
        charts_dir (Path | None): directory to write .png files to.
            Defaults to config.CHARTS_DIR when None.

    Returns:
        list[Path]: list of four Path objects pointing to the
                    saved .png files, in this order:
                    [power_trend.png, wind_scatter.png, monthly_bar.png,
                     anomaly_timeline.png]
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    labels = AXIS_LABELS[schema]
    out_dir = config.CHARTS_DIR if charts_dir is None else Path(charts_dir)

    # Ensure the charts directory exists (critical when running under
    # Docker with host volume mounts that overwrite build-time dirs)
    os.makedirs(out_dir, exist_ok=True)

    paths = [
        _plot_power_trend(results["daily"], labels["primary"], out_dir),
        _plot_scatter(results["efficiency"], cfg, schema, labels, out_dir),
        _plot_monthly_bar(results["monthly"], labels["primary"], out_dir),
        _plot_anomaly_timeline(
            results["daily_mean"], results["anomalies"], cfg,
            labels["primary"], out_dir,
        ),
    ]
    return paths


def _plot_power_trend(
    daily_df: pd.DataFrame, axis_label: str, out_dir: Path
) -> Path:
    """
    Generate a line chart of daily total primary power over time.

    Parameters:
        daily_df (pd.DataFrame): daily resampled DataFrame
        axis_label (str): plain-English y-axis label
        out_dir (Path): directory to save the .png file to

    Returns:
        Path: path to the saved power_trend.png file
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        daily_df.index,
        daily_df.iloc[:, 0],  # single-column DataFrame
        linewidth=0.8,
        color=sns.color_palette("muted")[0],
    )

    ax.set_title("Daily Power Output Over Time", fontsize=14, pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel(axis_label, fontsize=11)
    ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()

    out_path = out_dir / "power_trend.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path


def _plot_scatter(
    efficiency_df: pd.DataFrame,
    cfg: dict,
    schema: str,
    labels: dict,
    out_dir: Path,
) -> Path:
    """
    Generate a scatter plot of secondary vs primary power.

    Wind: actual vs theoretical power curve (data-derived reference line).
    Solar: AC vs DC power with ideal 1:1 conversion reference line.

    Parameters:
        efficiency_df (pd.DataFrame): efficiency/conversion result
        cfg (dict): schema config from SCHEMA_REGISTRY
        schema (str): "wind" or "solar"
        labels (dict): axis labels dict
        out_dir (Path): directory to save the .png file to

    Returns:
        Path: path to the saved wind_scatter.png file
    """
    sorted_df = efficiency_df.sort_values(cfg["secondary_col"])

    fig, ax = plt.subplots(figsize=(10, 6))

    # Actual values — scatter
    ax.scatter(
        efficiency_df[cfg["secondary_col"]],
        efficiency_df[cfg["primary_power_col"]],
        alpha=0.15,
        s=3,
        color=sns.color_palette("muted")[0],
        label="Actual Output",
    )

    # Reference line
    if schema == "wind":
        # Wind: data-derived theoretical power curve
        ax.plot(
            sorted_df[cfg["secondary_col"]],
            sorted_df[cfg["reference_col"]],
            linewidth=1.5,
            color=sns.color_palette("muted")[2],
            label="Theoretical Power Curve",
        )
        title = "Secondary Metric vs Primary Power Output (with Theoretical Curve)"
    else:
        # Solar: ideal 1:1 line (y = x) representing perfect conversion
        x_vals = sorted_df[cfg["secondary_col"]]
        ax.plot(
            x_vals, x_vals,
            linewidth=1.5,
            color=sns.color_palette("muted")[2],
            label="Ideal 1:1 Conversion",
        )
        title = "DC Power vs AC Power Output (with Ideal Conversion Line)"

    ax.set_title(title, fontsize=13, pad=12)
    ax.set_xlabel(labels["secondary"], fontsize=11)
    ax.set_ylabel(labels["primary"], fontsize=11)
    ax.legend(fontsize=10)

    fig.tight_layout()

    out_path = out_dir / "wind_scatter.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path


def _plot_monthly_bar(
    monthly_df: pd.DataFrame, axis_label: str, out_dir: Path
) -> Path:
    """
    Generate a bar chart of monthly mean primary power output.

    Parameters:
        monthly_df (pd.DataFrame): monthly resampled DataFrame
        axis_label (str): plain-English y-axis label
        out_dir (Path): directory to save the .png file to

    Returns:
        Path: path to the saved monthly_bar.png file
    """
    labels = monthly_df.index.strftime("%b %Y")

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.bar(
        range(len(monthly_df)),
        monthly_df.iloc[:, 0],
        color=sns.color_palette("muted")[1],
        edgecolor="white",
        linewidth=0.5,
    )

    ax.set_xticks(range(len(monthly_df)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_title("Monthly Mean Power Output", fontsize=14, pad=12)
    ax.set_xlabel("Month", fontsize=11)
    ax.set_ylabel(axis_label, fontsize=11)

    fig.tight_layout()

    out_path = out_dir / "monthly_bar.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path


def _plot_anomaly_timeline(
    daily_mean_df: pd.DataFrame,
    anomalies_df: pd.DataFrame,
    cfg: dict,
    axis_label: str,
    out_dir: Path,
) -> Path:
    """
    Generate a daily-mean trend line with anomalies highlighted.

    The line is the daily mean (not daily total) so anomaly points —
    instantaneous readings in primary-power units — share the same
    magnitude as the curve they overlay.

    Parameters:
        daily_mean_df (pd.DataFrame): daily-mean resampled DataFrame
        anomalies_df (pd.DataFrame): output of detect.detect()
        cfg (dict): schema config from SCHEMA_REGISTRY
        axis_label (str): plain-English y-axis label
        out_dir (Path): directory to save the .png file to

    Returns:
        Path: path to the saved anomaly_timeline.png file
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        daily_mean_df.index, daily_mean_df[cfg["primary_power_col"]],
        linewidth=0.8, color=sns.color_palette("muted")[0], zorder=1,
    )

    if not anomalies_df.empty:
        ax.scatter(
            anomalies_df[cfg["datetime_col"]],
            anomalies_df[cfg["primary_power_col"]],
            color="crimson", s=12, zorder=2, label="Anomaly",
        )
        ax.legend()

    ax.set_title("Power Output with Anomalies Highlighted", fontsize=14, pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel(axis_label, fontsize=11)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()

    out_path = out_dir / "anomaly_timeline.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path
