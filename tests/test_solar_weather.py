"""
test_solar_weather.py

Synthetic coverage for the solar_weather schema: two-file validation,
strict timestamp parsing, plant-to-inverter weather join, plant-level
aggregation, the irradiance-normalized metric, the nameplate capacity
gate, and a full CLI report run. No real Kaggle CSVs are used or
required.
"""

import re

import openpyxl
import pandas as pd
import pytest

import analyse
import clean
import config
import detect
import ingest
import main
import narrative

PLANT_ONE = "4136001"
PLANT_TWO = "4136002"


@pytest.fixture
def frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Six 15-minute intervals, two plants, two inverters per plant."""
    times = pd.date_range("2020-05-15 06:00", periods=6, freq="15min")
    generation_rows = []
    weather_rows = []

    # Irradiance is supplied in the dataset's recorded kW/m2 scale.
    plant_specs = (
        (PLANT_ONE, 100.0, 110.0, 0.6),
        (PLANT_TWO, 80.0, 90.0, 0.4),
    )
    for plant_id, first_base, second_base, irradiance in plant_specs:
        for index, timestamp in enumerate(times):
            weather_rows.append({
                config.COL_SOLAR_DATETIME: timestamp.strftime(
                    config.SOLAR_DATE_FORMAT
                ),
                config.COL_PLANT_ID: plant_id,
                config.COL_SOURCE_KEY: "SENSOR1",
                config.COL_IRRADIATION: irradiance + index * 0.05,
                config.COL_AMBIENT_TEMPERATURE: 25.0 + index,
                config.COL_MODULE_TEMPERATURE: 35.0 + index,
            })
            for source_key, base in (
                ("INV001", first_base), ("INV002", second_base)
            ):
                ac_power = base + index * 5.0
                generation_rows.append({
                    config.COL_SOLAR_DATETIME: timestamp.strftime(
                        config.SOLAR_DATE_FORMAT
                    ),
                    config.COL_PLANT_ID: plant_id,
                    config.COL_SOURCE_KEY: source_key,
                    config.COL_DC_POWER: ac_power * 1.1,
                    config.COL_AC_POWER: ac_power,
                    config.COL_DAILY_YIELD: ac_power * 10.0,
                    config.COL_TOTAL_YIELD: ac_power * 100.0,
                })

    return pd.DataFrame(generation_rows), pd.DataFrame(weather_rows)


def _clean_merged(
    generation: pd.DataFrame, weather: pd.DataFrame
) -> pd.DataFrame:
    merged = ingest.merge_solar_weather(generation, weather)
    clean_df, _ = clean.clean(merged, schema="solar_weather")
    return clean_df


def _results(clean_df: pd.DataFrame) -> dict:
    results = analyse.analyse(clean_df, schema="solar_weather")
    results["anomalies"] = detect.detect(clean_df, schema="solar_weather")
    return results


def test_registry_contract_declares_weather_and_no_nameplate():
    cfg = config.SCHEMA_REGISTRY["solar_weather"]

    assert cfg["plant_col"] == config.COL_PLANT_ID
    assert cfg["asset_id_col"] == config.COL_SOURCE_KEY
    assert cfg["ratio_name"] == "irradiance_normalized_output"
    assert cfg["ratio_is_percent"] is False
    assert cfg["nameplate_kw"] is None
    assert cfg["min_reference"] == config.IRRADIANCE_MIN_FOR_RATIO
    assert cfg["irradiance_scale_to_wm2"] == 1000.0
    assert "%Y-%m-%d %H:%M:%S" in cfg["alternate_date_formats"]
    for column in cfg["weather_required_columns"]:
        assert column in cfg["display_names"]
    assert "IEC" not in cfg["methodology_note"]


def test_merge_joins_weather_by_plant_and_interval(frames):
    generation, weather = frames

    merged = ingest.merge_solar_weather(generation, weather)

    assert len(merged) == len(generation)
    assert config.COL_IRRADIATION in merged.columns
    assert config.COL_AMBIENT_TEMPERATURE in merged.columns
    assert config.COL_MODULE_TEMPERATURE in merged.columns
    assert merged[config.COL_SOLAR_DATETIME].dtype.kind == "M"

    first = merged[
        (merged[config.COL_PLANT_ID] == PLANT_ONE)
        & (merged[config.COL_SOURCE_KEY] == "INV001")
        & (
            merged[config.COL_SOLAR_DATETIME]
            == pd.Timestamp("2020-05-15 06:00")
        )
    ].iloc[0]
    second_plant = merged[
        (merged[config.COL_PLANT_ID] == PLANT_TWO)
        & (merged[config.COL_SOURCE_KEY] == "INV001")
        & (
            merged[config.COL_SOLAR_DATETIME]
            == pd.Timestamp("2020-05-15 06:00")
        )
    ].iloc[0]

    # Each plant receives its own sensor reading, never the other's,
    # converted from recorded kW/m2 to W/m2.
    assert first[config.COL_IRRADIATION] == 600.0
    assert second_plant[config.COL_IRRADIATION] == 400.0


def test_merge_accepts_iso_timestamps(frames):
    """Plant 2 generation and both weather files use ISO timestamps."""
    generation, weather = frames
    iso_format = "%Y-%m-%d %H:%M:%S"
    generation[config.COL_SOLAR_DATETIME] = pd.to_datetime(
        generation[config.COL_SOLAR_DATETIME],
        format=config.SOLAR_DATE_FORMAT,
    ).dt.strftime(iso_format)
    weather[config.COL_SOLAR_DATETIME] = pd.to_datetime(
        weather[config.COL_SOLAR_DATETIME],
        format=config.SOLAR_DATE_FORMAT,
    ).dt.strftime(iso_format)

    merged = ingest.merge_solar_weather(generation, weather)

    assert len(merged) == len(generation)
    assert merged[config.COL_IRRADIATION].notna().all()


def test_merge_averages_multiple_sensor_rows_for_one_interval(frames):
    generation, weather = frames
    extra = weather.iloc[[0]].copy()
    extra[config.COL_SOURCE_KEY] = "SENSOR2"
    extra[config.COL_IRRADIATION] = 0.7
    weather = pd.concat([weather, extra], ignore_index=True)

    merged = ingest.merge_solar_weather(generation, weather)

    value = merged.loc[
        (merged[config.COL_PLANT_ID] == PLANT_ONE)
        & (merged[config.COL_SOLAR_DATETIME] == pd.Timestamp("2020-05-15 06:00")),
        config.COL_IRRADIATION,
    ].iloc[0]
    assert value == pytest.approx(650.0)


def test_merge_rejects_bad_timestamps(frames):
    generation, weather = frames
    generation.loc[0, config.COL_SOLAR_DATETIME] = "2020-13-01 06:00"

    with pytest.raises(SystemExit) as exc_info:
        ingest.merge_solar_weather(generation, weather)

    message = str(exc_info.value)
    assert "generation file" in message
    assert "match none of the known formats" in message
    assert "not silently dropped" in message


def test_merge_rejects_missing_weather_columns(frames):
    generation, weather = frames
    weather = weather.drop(columns=[config.COL_IRRADIATION])

    with pytest.raises(SystemExit) as exc_info:
        ingest.merge_solar_weather(generation, weather)

    assert config.COL_IRRADIATION in str(exc_info.value)
    assert "weather file" in str(exc_info.value)


def test_merge_rejects_plant_missing_from_weather(frames):
    generation, weather = frames
    weather.loc[weather[config.COL_PLANT_ID] == PLANT_ONE, config.COL_PLANT_ID] = (
        "9999999"
    )

    with pytest.raises(SystemExit) as exc_info:
        ingest.merge_solar_weather(generation, weather)

    message = str(exc_info.value)
    assert PLANT_ONE in message
    assert "No weather rows" in message


def test_merge_rejects_plant_with_no_matching_intervals(frames):
    generation, weather = frames
    plant_one = weather[config.COL_PLANT_ID] == PLANT_ONE
    shifted = pd.to_datetime(
        weather.loc[plant_one, config.COL_SOLAR_DATETIME],
        format=config.SOLAR_DATE_FORMAT,
    ) + pd.Timedelta(days=1)
    weather.loc[plant_one, config.COL_SOLAR_DATETIME] = shifted.dt.strftime(
        config.SOLAR_DATE_FORMAT
    )

    with pytest.raises(SystemExit) as exc_info:
        ingest.merge_solar_weather(generation, weather)

    message = str(exc_info.value)
    assert PLANT_ONE in message
    assert "no generation row that matches" in message


def test_merge_rejects_conflicting_duplicate_generation_keys(frames):
    generation, weather = frames
    duplicate = generation.iloc[[0]].copy()
    duplicate[config.COL_AC_POWER] = duplicate[config.COL_AC_POWER] + 1.0
    generation = pd.concat([generation, duplicate], ignore_index=True)

    with pytest.raises(SystemExit) as exc_info:
        ingest.merge_solar_weather(generation, weather)

    assert "duplicate" in str(exc_info.value).lower()
    assert "double-count" in str(exc_info.value)


def test_clean_accepts_timestamps_already_parsed_by_merge(frames):
    generation, weather = frames
    merged = ingest.merge_solar_weather(generation, weather)

    clean_df, _ = clean.clean(merged, schema="solar_weather")

    assert clean_df[config.COL_SOLAR_DATETIME].dtype.kind == "M"
    assert len(clean_df) == len(merged)


def test_analysis_reports_per_inverter_and_plant_metrics(frames):
    generation, weather = frames
    clean_df = _clean_merged(generation, weather)

    results = _results(clean_df)

    efficiency = results["efficiency"]
    assert len(efficiency) == len(generation)
    first = efficiency[
        (efficiency[config.COL_PLANT_ID] == PLANT_ONE)
        & (efficiency[config.COL_SOURCE_KEY] == "INV001")
    ].iloc[0]
    assert first[config.COL_IRRADIATION] == 600.0
    assert first["irradiance_normalized_output"] == pytest.approx(100.0 / 600.0)

    plant = results["plant_summary"]
    assert len(plant) == 12
    first_plant = plant[
        (plant[config.COL_PLANT_ID] == PLANT_ONE)
        & (
            plant[config.COL_SOLAR_DATETIME]
            == pd.Timestamp("2020-05-15 06:00")
        )
    ].iloc[0]
    assert first_plant[config.COL_AC_POWER] == pytest.approx(210.0)
    assert first_plant[config.COL_IRRADIATION] == pytest.approx(600.0)
    assert first_plant["inverter_count"] == 2
    assert first_plant["irradiance_normalized_output"] == pytest.approx(0.35)

    second_plant = plant[
        (plant[config.COL_PLANT_ID] == PLANT_TWO)
        & (
            plant[config.COL_SOLAR_DATETIME]
            == pd.Timestamp("2020-05-15 06:00")
        )
    ].iloc[0]
    assert second_plant["irradiance_normalized_output"] == pytest.approx(0.425)

    # Without a documented nameplate there is no capacity-normalized
    # result at all, so no standard-based claim can leak into a report.
    assert "performance_ratio" not in results


def test_low_irradiance_intervals_are_excluded_not_filled(frames):
    generation, weather = frames
    weather.loc[0, config.COL_IRRADIATION] = 0.02  # 20 W/m2 after conversion

    clean_df = _clean_merged(generation, weather)
    results = _results(clean_df)

    first_plant = results["plant_summary"].iloc[0]
    assert pd.isna(first_plant["irradiance_normalized_output"])
    assert len(results["efficiency"]) == len(generation) - 2


def test_negative_irradiance_is_excluded_from_the_metric(frames):
    generation, weather = frames
    weather.loc[0, config.COL_IRRADIATION] = -0.01

    clean_df = _clean_merged(generation, weather)
    results = _results(clean_df)

    first_plant = results["plant_summary"].iloc[0]
    assert pd.isna(first_plant["irradiance_normalized_output"])


def test_performance_ratio_is_gated_on_documented_nameplate(
    frames, monkeypatch
):
    generation, weather = frames
    clean_df = _clean_merged(generation, weather)

    monkeypatch.setitem(
        config.SCHEMA_REGISTRY["solar_weather"], "nameplate_kw", 500.0
    )
    results = analyse.analyse(clean_df, schema="solar_weather")

    ratio = results["performance_ratio"]
    first = ratio[
        (ratio[config.COL_PLANT_ID] == PLANT_ONE)
        & (
            ratio[config.COL_SOLAR_DATETIME]
            == pd.Timestamp("2020-05-15 06:00")
        )
    ].iloc[0]
    assert first["nameplate_kw"] == 500.0
    assert first["performance_ratio"] == pytest.approx(210.0 / (500.0 * 0.6))


def test_narrative_uses_plant_hours_and_makes_no_standard_claim(frames):
    generation, weather = frames
    clean_df = _clean_merged(generation, weather)
    results = _results(clean_df)

    text = narrative.build_narrative(results, clean_df, "solar_weather")

    assert "3 hours" in text
    assert "2 plants and 4 inverters" in text
    assert "IEC" not in text
    assert "performance ratio" not in text.lower()
    assert "Irradiance-Normalized Output" in text


def test_headline_ratio_is_plant_level(frames):
    generation, weather = frames
    clean_df = _clean_merged(generation, weather)
    results = _results(clean_df)

    expected = round(
        results["plant_summary"]["irradiance_normalized_output"].mean(), 3
    )
    rows = dict(narrative.build_headline_stats(
        results,
        clean_df,
        config.SCHEMA_REGISTRY["solar_weather"],
        None,
    ))

    label = (
        "Mean "
        + config.SCHEMA_REGISTRY["solar_weather"]["ratio_label"]
    )
    assert rows[label] == expected


def test_run_single_requires_weather_file_for_solar_weather(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main.run_single(
            tmp_path / "generation.csv",
            tmp_path / "output",
            schema="solar_weather",
            fmt="excel",
        )

    assert "--weather-file" in str(exc_info.value)


def test_run_single_rejects_weather_file_for_single_file_schema(
    tmp_path, solar_df
):
    generation_path = tmp_path / "generation.csv"
    solar_df.to_csv(generation_path, index=False)

    with pytest.raises(SystemExit) as exc_info:
        main.run_single(
            generation_path,
            tmp_path / "output",
            schema="solar",
            fmt="excel",
            weather_file=tmp_path / "weather.csv",
        )

    assert "only valid" in str(exc_info.value)


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "CHARTS_DIR", tmp_path / "output" / "charts")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "logs" / "data_quality.log")
    (tmp_path / "logs").mkdir(parents=True)


def test_end_to_end_solar_weather_report(frames, tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    generation, weather = frames

    generation_path = tmp_path / "Plant_1_Generation_Data.csv"
    weather_path = tmp_path / "Plant_1_Weather_Sensor_Data.csv"
    generation.to_csv(generation_path, index=False)
    weather.to_csv(weather_path, index=False)

    output_dir = tmp_path / "output"
    main.run_single(
        generation_path,
        output_dir,
        schema="solar_weather",
        fmt="both",
        weather_file=weather_path,
    )

    reports = list(output_dir.glob("report_*.xlsx"))
    html_reports = list(output_dir.glob("report_*.html"))
    charts = list((output_dir / "charts").glob("*.png"))
    assert len(reports) == 1
    assert len(html_reports) == 1
    assert len(charts) == 4

    wb = openpyxl.load_workbook(reports[0])
    assert wb.sheetnames == [
        "Summary",
        "Clean Data",
        "Trend Analysis",
        "Efficiency Analysis",
        config.PLANT_SUMMARY_SHEET_NAME,
        "Charts",
        "Anomaly Report",
        "Data Quality Log",
    ]

    narrative_text = wb["Summary"]["A1"].value
    assert "IEC" not in narrative_text
    assert "Irradiance-Normalized Output" in narrative_text

    clean_headers = {
        cell.value for cell in wb["Clean Data"][1]
    }
    assert "Irradiance (W/m²)" in clean_headers

    efficiency_headers = {
        cell.value for cell in wb["Efficiency Analysis"][1]
    }
    assert (
        config.SCHEMA_REGISTRY["solar_weather"]["ratio_label"]
        in efficiency_headers
    )

    plant_headers = {
        cell.value for cell in wb[config.PLANT_SUMMARY_SHEET_NAME][1]
    }
    assert "Inverters Reporting" in plant_headers
    assert "Irradiance (W/m²)" in plant_headers

    html = html_reports[0].read_text(encoding="utf-8")
    assert '<h2 id="plant-summary">Plant Summary</h2>' in html
    # Strip embedded images before scanning prose: base64 can contain
    # any three-letter sequence by chance.
    visible_html = re.sub(r'src="data:image/png;base64,[^"]+"', "", html)
    assert "IEC" not in visible_html
