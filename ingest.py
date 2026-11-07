"""
ingest.py

Owns CSV loading and schema validation.
Checks that all required SCADA columns for the active schema are
present before returning a raw DataFrame. Does not clean or transform
data.

The solar_weather schema takes two files. merge_solar_weather()
validates both contracts, parses their timestamps strictly, checks
that every plant appears in both files, and joins plant-level weather
readings onto each inverter row by (PLANT_ID, DATE_TIME). It rejects
malformed input with a plain-English error instead of dropping rows.
"""

from pathlib import Path

import pandas as pd

import config


def load_csv(file_path: Path) -> pd.DataFrame:
    """
    Load a CSV file and return the raw DataFrame.

    Uses pd.read_csv() with no additional arguments — date parsing
    and type coercion belong to clean.py, not here.

    Parameters:
        file_path (Path): Path to the CSV file to load.

    Returns:
        pd.DataFrame: Raw contents of the CSV, no transforms applied.

    Raises:
        SystemExit: If the file does not exist or cannot be read.
    """
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        raise SystemExit(f"Error: File not found — {file_path}")
    except Exception as e:
        raise SystemExit(f"Error: Could not read file — {file_path}\nReason: {e}")


def validate_schema(
    df: pd.DataFrame, schema: str, role: str = "generation"
) -> None:
    """
    Validate that the DataFrame contains all required columns for the
    given schema.

    Compares the DataFrame columns against the column list from
    config.SCHEMA_REGISTRY for the active schema. Does not check
    column order or dtypes — those belong to clean.py.

    Parameters:
        df (pd.DataFrame): Raw DataFrame to validate.
        schema (str): a schema name from config.SCHEMA_REGISTRY.
        role (str): "generation" validates required_columns;
                    "weather" validates weather_required_columns for
                    schemas that accept a second input file.

    Returns:
        None: If all required columns are present.

    Raises:
        SystemExit: With a plain-English message listing the missing
                    and expected columns.
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    key = "weather_required_columns" if role == "weather" else "required_columns"
    if key not in cfg:
        raise SystemExit(
            f"Error: Schema '{schema}' has no {role} file contract."
        )

    required = cfg[key]
    missing = [col for col in required if col not in df.columns]

    if not missing:
        return

    file_label = "weather" if role == "weather" else "SCADA"
    raise SystemExit(
        f"Error: Schema validation failed for '{schema}' {file_label} file.\n"
        f"Missing columns: {missing}\n"
        f"Expected columns: {required}"
    )


def load_solar_weather(
    generation_path: Path,
    weather_path: Path,
    schema: str = "solar_weather",
) -> pd.DataFrame:
    """
    Load, validate and join a generation file and a weather file.

    Convenience wrapper around load_csv(), validate_schema() and
    merge_solar_weather() for callers that hold paths rather than
    DataFrames. main.run_single() loads and prints each file
    separately, so it uses the lower-level functions directly.

    Parameters:
        generation_path (Path): inverter-level generation CSV
        weather_path (Path): plant-level weather sensor CSV
        schema (str): schema name; defaults to solar_weather

    Returns:
        pd.DataFrame: per-inverter rows with plant weather joined on
                      (PLANT_ID, DATE_TIME)
    """
    generation_df = load_csv(generation_path)
    weather_df = load_csv(weather_path)
    validate_schema(generation_df, schema)
    validate_schema(weather_df, schema, role="weather")
    return merge_solar_weather(generation_df, weather_df, schema)


def merge_solar_weather(
    generation_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    schema: str = "solar_weather",
) -> pd.DataFrame:
    """
    Join plant-level weather readings onto inverter-level generation.

    The join key is (PLANT_ID, DATE_TIME). SOURCE_KEY is deliberately
    not part of the join: generation rows identify inverters while
    weather rows identify sensor panels, so those values never match.

    Validation is strict where the input is malformed and explicit
    where data is merely incomplete:
      - missing columns raise the schema error from validate_schema
      - unparseable timestamps raise, naming the file and row count
      - plants present in only one file raise
      - duplicate generation keys raise (summing them would inflate AC)
      - multiple weather rows for one plant interval are averaged
      - partial weather coverage is printed; affected rows keep NaN
        irradiance and are excluded from the ratio, never filled

    Parameters:
        generation_df (pd.DataFrame): raw generation CSV contents
        weather_df (pd.DataFrame): raw weather CSV contents
        schema (str): schema name; must declare weather_required_columns

    Returns:
        pd.DataFrame: one row per inverter per interval, with the
                      weather measure columns appended and the
                      datetime column parsed to datetime64
    """
    cfg = config.SCHEMA_REGISTRY[schema]
    if "weather_required_columns" not in cfg:
        raise SystemExit(
            f"Error: Schema '{schema}' does not accept a weather file."
        )

    validate_schema(generation_df, schema)
    validate_schema(weather_df, schema, role="weather")

    datetime_col = cfg["datetime_col"]
    plant_col = cfg["plant_col"]
    source_col = cfg["asset_id_col"]
    measure_cols = cfg["weather_measure_columns"]

    generation = _parse_timestamps(generation_df, cfg, "generation")
    weather = _parse_timestamps(weather_df, cfg, "weather")

    generation[plant_col] = generation[plant_col].astype(str).str.strip()
    weather[plant_col] = weather[plant_col].astype(str).str.strip()
    generation[source_col] = generation[source_col].astype(str).str.strip()

    if (generation[plant_col] == "").any():
        raise SystemExit(
            "Error: Generation file contains blank PLANT_ID values; "
            "every row must name its plant."
        )

    generation = _drop_exact_duplicates(generation, "generation")
    weather = _drop_exact_duplicates(weather, "weather")

    duplicate_keys = generation.duplicated(
        [plant_col, source_col, datetime_col], keep=False
    )
    if duplicate_keys.any():
        examples = generation.loc[
            duplicate_keys, [plant_col, source_col, datetime_col]
        ].head(3)
        raise SystemExit(
            "Error: Generation file has "
            f"{int(duplicate_keys.sum()):,} rows sharing "
            "(PLANT_ID, SOURCE_KEY, DATE_TIME) with different values.\n"
            f"Examples:\n{examples.to_string(index=False)}\n"
            "Fix the duplicates; summing them would double-count power."
        )

    _validate_plants(generation, weather, plant_col)
    weather = _coerce_weather_measures(weather, measure_cols)
    weather = _convert_irradiance_units(weather, cfg)
    weather = _handle_negative_irradiance(weather, cfg)
    weather = _aggregate_weather(weather, cfg)

    _report_unmatched_weather(generation, weather, cfg)

    merged = generation.merge(
        weather,
        on=[plant_col, datetime_col],
        how="left",
        validate="many_to_one",
        sort=False,
    )

    missing_irradiance = merged[cfg["reference_col"]].isna()
    if missing_irradiance.any():
        print(
            f"[MERGE] {int(missing_irradiance.sum()):,} generation rows "
            "have no concurrent irradiance reading; they are kept but "
            "excluded from the normalized output"
        )

    usable_by_plant = merged.groupby(plant_col)[cfg["reference_col"]].apply(
        lambda values: values.notna().any()
    )
    unusable = sorted(usable_by_plant[~usable_by_plant].index.tolist())
    if unusable:
        raise SystemExit(
            "Error: Plant(s) " + ", ".join(unusable) + " have no "
            "generation row that matches a weather reading. Check the "
            "PLANT_ID values and timestamps in both files; no rows were "
            "dropped silently."
        )

    _report_interval_gaps(generation, cfg)

    return merged.sort_values(
        [plant_col, datetime_col, source_col]
    ).reset_index(drop=True)


def _parse_timestamps(
    df: pd.DataFrame, cfg: dict, role: str
) -> pd.DataFrame:
    """
    Parse one input file's timestamps, rejecting every bad row.

    The real dataset ships two timestamp layouts: Plant 1 generation
    is day-first, while Plant 2 generation and both weather files are
    ISO. Each file must parse completely under one known format; a
    file that mixes layouts, or uses an unknown one, raises instead of
    being coerced row by row.
    """
    datetime_col = cfg["datetime_col"]
    formats = [cfg["date_format"]] + list(
        cfg.get("alternate_date_formats", [])
    )

    parsed = None
    used_format = None
    for candidate_format in formats:
        candidate = pd.to_datetime(
            df[datetime_col], format=candidate_format, errors="coerce"
        )
        if candidate.notna().all():
            parsed = candidate
            used_format = candidate_format
            break

    if parsed is None:
        examples = df[datetime_col].astype(str).head(3).tolist()
        raise SystemExit(
            f"Error: {role} file has timestamps that match none of the "
            f"known formats {formats}. Examples: {examples}. "
            "Fix these rows and rerun; they are not silently dropped."
        )

    if used_format != cfg["date_format"]:
        print(
            f"[MERGE] {role} timestamps parsed with alternate format "
            f"'{used_format}'"
        )

    parsed_df = df.copy()
    parsed_df[datetime_col] = parsed
    return parsed_df


def _drop_exact_duplicates(df: pd.DataFrame, role: str) -> pd.DataFrame:
    """Drop fully identical rows, reporting the count."""
    duplicate = df.duplicated()
    if not duplicate.any():
        return df
    print(
        f"[MERGE] Dropped {int(duplicate.sum()):,} fully duplicate "
        f"{role} row(s)"
    )
    return df.loc[~duplicate].copy()


def _validate_plants(
    generation: pd.DataFrame, weather: pd.DataFrame, plant_col: str
) -> None:
    """Require every plant in one file to appear in the other."""
    generation_plants = set(generation[plant_col])
    weather_plants = set(weather[plant_col])

    only_generation = sorted(generation_plants - weather_plants)
    if only_generation:
        raise SystemExit(
            "Error: No weather rows for plant(s) "
            + ", ".join(only_generation)
            + ". The weather file must cover every plant in the "
            "generation file."
        )

    only_weather = sorted(weather_plants - generation_plants)
    if only_weather:
        raise SystemExit(
            "Error: No generation rows for weather plant(s) "
            + ", ".join(only_weather)
            + ". Check that both files use the same PLANT_ID values."
        )


def _coerce_weather_measures(
    weather: pd.DataFrame, measure_cols: list[str]
) -> pd.DataFrame:
    """Coerce weather measurements to numeric, reporting bad values."""
    weather = weather.copy()
    for col in measure_cols:
        before = int(weather[col].isna().sum())
        weather[col] = pd.to_numeric(weather[col], errors="coerce")
        newly_missing = int(weather[col].isna().sum()) - before
        if newly_missing > 0:
            print(
                f"[MERGE] {newly_missing:,} non-numeric weather value(s) "
                f"in {col} set to missing and excluded from the metric"
            )
    return weather


def _convert_irradiance_units(
    weather: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """
    Convert recorded irradiance to W/m2 using the registry's scale.

    The Kaggle sensor files record values between 0 and about 1.22,
    which is kW/m2. Without this conversion the 50 W/m2 threshold
    would reject every daylight row. The scale is explicit in the
    registry and printed, never inferred from the data at runtime.
    """
    scale = float(cfg.get("irradiance_scale_to_wm2", 1.0))
    if scale == 1.0:
        return weather

    irradiation_col = cfg["reference_col"]
    converted = weather.copy()
    converted[irradiation_col] = converted[irradiation_col] * scale
    print(
        f"[MERGE] Irradiance converted to W/m2 with x{scale:g} "
        "(source records kW/m2)"
    )
    return converted


def _handle_negative_irradiance(
    weather: pd.DataFrame, cfg: dict
) -> pd.DataFrame:
    """Treat negative irradiance as invalid rather than physical."""
    irradiation_col = cfg["reference_col"]
    negative = weather[irradiation_col] < 0
    if not negative.any():
        return weather

    weather = weather.copy()
    weather.loc[negative, irradiation_col] = float("nan")
    print(
        f"[MERGE] {int(negative.sum()):,} negative irradiance "
        "reading(s) set to missing and excluded from the metric"
    )
    return weather


def _aggregate_weather(weather: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Reduce weather to one row per plant interval for a safe join."""
    plant_col = cfg["plant_col"]
    datetime_col = cfg["datetime_col"]
    measure_cols = cfg["weather_measure_columns"]

    multiple_sensors = weather.duplicated(
        [plant_col, datetime_col], keep=False
    )
    if multiple_sensors.any():
        intervals = weather.loc[
            multiple_sensors, [plant_col, datetime_col]
        ].drop_duplicates()
        print(
            f"[MERGE] {len(intervals):,} plant interval(s) carry more "
            "than one weather sensor row; their readings are averaged"
        )

    return weather.groupby(
        [plant_col, datetime_col], as_index=False
    )[measure_cols].mean()


def _report_unmatched_weather(
    generation: pd.DataFrame, weather: pd.DataFrame, cfg: dict
) -> None:
    """Report weather intervals that no generation row reaches."""
    plant_col = cfg["plant_col"]
    datetime_col = cfg["datetime_col"]
    generation_keys = generation[[plant_col, datetime_col]].drop_duplicates()
    unmatched = weather[[plant_col, datetime_col]].merge(
        generation_keys,
        on=[plant_col, datetime_col],
        how="left",
        indicator=True,
    )
    count = int((unmatched["_merge"] == "left_only").sum())
    if count > 0:
        print(
            f"[MERGE] {count:,} weather interval(s) have no generation "
            "row and do not enter the report"
        )


def _report_interval_gaps(generation: pd.DataFrame, cfg: dict) -> None:
    """Print gaps longer than the schema's interval; never fill them."""
    plant_col = cfg["plant_col"]
    datetime_col = cfg["datetime_col"]
    expected = pd.Timedelta(minutes=cfg["interval_minutes"])

    for plant_id, group in generation.groupby(plant_col):
        times = group[datetime_col].drop_duplicates().sort_values()
        gaps = times.diff().dropna()
        gap_count = int((gaps > expected).sum())
        if gap_count > 0:
            print(
                f"[MERGE] Plant {plant_id}: {gap_count:,} gap(s) longer "
                f"than {cfg['interval_minutes']} minutes reported, not filled"
            )
