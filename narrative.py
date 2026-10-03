"""
narrative.py

Owns the shared summary content consumed by both exporters:
the narrative paragraph and the headline-statistics rows.
Produces schema-agnostic, plain-English output from real
computed analysis values, so the Excel and HTML reports can
never drift apart in what they claim.

Fully registry-driven: hours per row come from the schema's
interval_minutes, and the notable-pattern sentence dispatches on
the distribution kind — adding a schema requires no changes here.

No files are written. No side effects.
"""

import pandas as pd

import config


def build_headline_stats(
    results: dict,
    clean_df: pd.DataFrame,
    cfg: dict,
    run_ids: list[str] | None = None,
) -> list[tuple[str, float | int]]:
    """
    Build the headline-statistics rows shared by both exporters.

    One definition of the report's headline table: labels are
    registry-driven plain English, values are raw numbers (the
    ratio row is already scaled to percent). Each renderer applies
    its own formatting; the row set and order are identical in
    both report formats. Batch runs append a Source Files Processed
    row equal to the number of run IDs.

    Parameters:
        results (dict): analysis results dict; needs 'stats' and
                        'efficiency'
        clean_df (pd.DataFrame): the clean DataFrame for this run
        cfg (dict): schema config from config.SCHEMA_REGISTRY
        run_ids (list[str] | None): normalised run IDs; more than
            one marks a batch run and adds the source-file count row

    Returns:
        list[tuple[str, float | int]]: (label, value) pairs in
            report order
    """
    stats = results["stats"]
    efficiency_df = results["efficiency"]
    primary = cfg["primary_power_col"]
    secondary = cfg["secondary_col"]

    rows: list[tuple[str, float | int]] = [
        (f"Mean {cfg['primary_label']}", round(stats.loc["mean", primary], 2)),
        (f"Max {cfg['primary_label']}", round(stats.loc["max", primary], 2)),
        (f"Std Dev {cfg['primary_label']}", round(stats.loc["std", primary], 2)),
        (f"Mean {cfg['secondary_label']}", round(stats.loc["mean", secondary], 2)),
        (f"Max {cfg['secondary_label']}", round(stats.loc["max", secondary], 2)),
        (f"Mean {cfg['ratio_label']}",
         round(efficiency_df[cfg["ratio_name"]].mean() * 100, 2)),
        ("Total Rows Analysed", len(efficiency_df)),
        ("Rows Excluded from Analysis",
         len(clean_df) - len(efficiency_df)),
    ]
    # Defensive normalisation: a bare string is a single run's ID
    ids = [run_ids] if isinstance(run_ids, str) else list(run_ids or [])
    if len(ids) > 1:
        rows.append(("Source Files Processed", len(ids)))
    return rows


def power_curve_bin_header(cfg: dict) -> str:
    """
    Plain-English header for the measured power curve's bin column,
    derived from the registry's secondary label (e.g. wind speed
    "Wind Speed (m/s)" → "Wind Speed Bin (m/s)").

    Shared by both exporters so the Excel sheet and the HTML section
    cannot disagree on the label.

    Parameters:
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        str: header for the bin column
    """
    base = cfg["secondary_label"].split(" (")[0]
    unit = cfg["secondary_label"].rsplit("(", 1)[-1].rstrip(")")
    return f"{base} Bin ({unit})"


def power_curve_headers(cfg: dict) -> dict:
    """
    Plain-English headers for the measured power curve's data
    columns — one definition consumed by both exporters (the bin
    column header comes from power_curve_bin_header).

    Parameters:
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        dict: mapping of power-curve DataFrame columns to headers
    """
    reference_display = cfg["display_names"].get(
        cfg["reference_col"], cfg["reference_col"]
    )
    return {
        "mean_secondary": f"Mean {cfg['secondary_label']}",
        "mean_primary":   f"Mean {cfg['primary_label']}",
        "mean_reference": f"Mean {reference_display}",
        "count":          "Samples",
        "sufficient":     "Data Sufficient",
    }


def build_narrative(results: dict, clean_df: pd.DataFrame, schema: str) -> str:
    """
    Build the 3-5 sentence narrative paragraph for the given schema.

    Sentences are assembled from registry-driven fragments: asset
    label, primary metric, ratio label, interval-based operational
    hours, and one notable pattern dispatched on the distribution
    kind. An anomaly sentence is appended when anomalies were
    flagged.

    Parameters:
        results (dict): analysis results from analyse.analyse(),
                        including 'anomalies' from detect.detect()
        clean_df (pd.DataFrame): the clean DataFrame for this run
        schema (str): active schema name in config.SCHEMA_REGISTRY

    Returns:
        str: narrative paragraph text
    """
    cfg = config.SCHEMA_REGISTRY[schema]

    efficiency_df = results["efficiency"]
    stats = results["stats"]
    mean_power = stats.loc["mean", cfg["primary_power_col"]]
    mean_ratio = efficiency_df[cfg["ratio_name"]].mean() * 100
    op_hours = _operational_hours(len(efficiency_df), cfg)

    opening = (
        f"This report analyses {op_hours:,} hours of operational "
        f"{cfg['asset_label'].lower()} data. "
        f"The system produced a mean {cfg['primary_label']} of "
        f"{mean_power:,.1f} across all operational periods. "
        f"Overall {cfg['ratio_label']} against the reference "
        f"averaged {mean_ratio:.1f}%."
    )

    pattern = _notable_pattern(results, cfg)

    narrative = f"{opening} {pattern}"

    # Methodology sentence: registry-driven, present only for schemas
    # that declare one — anchors the analysis to a named industry
    # standard (e.g. IEC 61400-12-1, IEC 61724)
    methodology_note = cfg.get("methodology_note")
    if methodology_note:
        narrative += f" {methodology_note}"

    anomaly_count = len(results.get("anomalies", []))
    if anomaly_count > 0:
        narrative += (
            f" {anomaly_count} anomalous readings were flagged during this "
            f"period and are detailed in the Anomaly Report."
        )
    else:
        narrative += " No anomalous readings were flagged during this period."

    return narrative


def _operational_hours(row_count: int, cfg: dict) -> int:
    """
    Convert a row count into operational hours using the schema's
    interval length.

    Parameters:
        row_count (int): number of operational rows
        cfg (dict): schema config; interval_minutes gives the minutes
                    each row represents

    Returns:
        int: operational hours, rounded to the nearest hour
    """
    return round(row_count * cfg["interval_minutes"] / 60)


def _notable_pattern(results: dict, cfg: dict) -> str:
    """
    Build the notable-pattern sentence, dispatched on the registry's
    distribution kind — not the schema name.

    Kinds:
        "bins"       — peak period of the primary metric by calendar
                       month (e.g. wind's strongest wind-resource
                       month, hydro's wettest month)
        "group_mean" — best-performing unit by mean output
                       (e.g. solar's top inverter)

    Parameters:
        results (dict): analysis results dict
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        str: one plain-English sentence describing a real pattern
    """
    kind = cfg["distribution"]["kind"]
    if kind == "bins":
        return _peak_month_sentence(results, cfg)
    return _top_unit_sentence(results, cfg)


def _peak_month_sentence(results: dict, cfg: dict) -> str:
    """
    Sentence naming the calendar month with the highest mean output.

    Parameters:
        results (dict): analysis results dict; 'monthly' must exist
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        str: plain-English sentence from the computed monthly series
    """
    monthly = results["monthly"]
    primary = cfg["primary_power_col"]
    peak_month = monthly[primary].idxmax()
    return (
        f"Peak mean output occurred in {peak_month.strftime('%B %Y')}, "
        f"suggesting the strongest resource period in this window."
    )


def _top_unit_sentence(results: dict, cfg: dict) -> str:
    """
    Sentence naming the best-performing unit from the grouped
    distribution (e.g. the inverter with the highest mean output).

    Parameters:
        results (dict): analysis results dict; 'distribution' with
                        columns ['mean', 'count'] must exist
        cfg (dict): schema config from config.SCHEMA_REGISTRY

    Returns:
        str: plain-English sentence from the computed distribution
    """
    distribution = results["distribution"]
    unit_label = cfg["display_names"].get(
        cfg["distribution"]["group_col"], "unit"
    )
    best_unit = distribution["mean"].idxmax()
    best_mean = distribution.loc[best_unit, "mean"]
    return (
        f"The best-performing {unit_label} was {best_unit}, "
        f"with a mean output of {best_mean:,.1f}."
    )
