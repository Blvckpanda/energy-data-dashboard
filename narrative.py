"""
narrative.py

Owns narrative paragraph generation, shared between export.py
(Excel) and html_export.py (HTML). Produces schema-aware,
plain-English summaries from real computed analysis values.

No files are written. No side effects.
"""

import config


def build_narrative(results: dict, clean_df, schema: str) -> str:
    """
    Build the 3-5 sentence narrative paragraph for the given schema.

    Parameters:
        results (dict): analysis results from analyse.analyse(),
                        including 'anomalies' from detect.detect()
        clean_df: the clean DataFrame for this run
        schema (str): "wind" or "solar"

    Returns:
        str: narrative paragraph text
    """
    if schema == "wind":
        narrative = _build_wind_narrative(results, clean_df)
    else:
        narrative = _build_solar_narrative(results, clean_df)

    anomaly_count = len(results.get("anomalies", []))
    if anomaly_count > 0:
        narrative += (
            f" {anomaly_count} anomalous readings were flagged during this "
            f"period and are detailed in the Anomaly Report."
        )
    else:
        narrative += " No anomalous readings were flagged during this period."

    return narrative


def _build_wind_narrative(results: dict, clean_df) -> str:
    """Wind-specific narrative paragraph from real computed values."""
    stats = results["stats"]
    efficiency_df = results["efficiency"]
    monthly_df = results["monthly"]

    peak_month = monthly_df[config.COL_ACTIVE_POWER].idxmax()
    peak_month_label = peak_month.strftime("%B %Y")
    mean_power = stats.loc["mean", config.COL_ACTIVE_POWER]
    mean_efficiency = efficiency_df["efficiency_ratio"].mean() * 100
    op_hours = round(len(efficiency_df) * 10 / 60)

    return (
        f"This report analyses {op_hours:,} hours of operational wind turbine data. "
        f"The turbine produced a mean active power output of {mean_power:,.1f} kW "
        f"across all operational periods. "
        f"Overall efficiency against the theoretical power curve averaged "
        f"{mean_efficiency:.1f}%, indicating the proportion of available wind energy "
        f"converted to output. "
        f"Peak mean output occurred in {peak_month_label}, suggesting strong seasonal "
        f"wind resource during this period."
    )


def _build_solar_narrative(results: dict, clean_df) -> str:
    """Solar-specific narrative paragraph from real computed values."""
    stats = results["stats"]
    efficiency_df = results["efficiency"]
    distribution_df = results["distribution"]

    mean_power = stats.loc["mean", config.COL_AC_POWER]
    mean_conversion = efficiency_df["conversion_ratio"].mean() * 100
    op_hours = round(len(efficiency_df) * 10 / 60)

    best_inverter = distribution_df["mean"].idxmax()
    best_mean = distribution_df.loc[best_inverter, "mean"]

    return (
        f"This report analyses {op_hours:,} hours of operational solar generation data. "
        f"The plant produced a mean AC power output of {mean_power:,.1f} kW "
        f"across all operational periods. "
        f"Overall DC-to-AC conversion efficiency averaged {mean_conversion:.1f}%, "
        f"indicating the proportion of DC power successfully converted to usable AC. "
        f"The best-performing inverter was {best_inverter}, "
        f"with a mean AC output of {best_mean:,.1f} kW."
    )
