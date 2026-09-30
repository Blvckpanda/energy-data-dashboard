# Unit 09: Solar Schema Support

## Goal

Add a `--schema` flag so `main.py` can process either Wind Turbine
or Solar Power Generation SCADA data through the same pipeline —
driven entirely by a schema registry in `config.py` — with no
duplicated pipeline code and no separate entry points.

---

## Implementation

### 1. `config.py` — Solar Constants + Schema Registry

Add the raw solar column names. Note the solar dataset's date
format differs from wind's — this is a real difference in the
source data, not a design choice.

```python
# ── Solar SCADA Column Names ──────────────────────────────────────
COL_SOLAR_DATETIME = "DATE_TIME"
COL_PLANT_ID       = "PLANT_ID"
COL_SOURCE_KEY     = "SOURCE_KEY"
COL_DC_POWER       = "DC_POWER"
COL_AC_POWER       = "AC_POWER"
COL_DAILY_YIELD    = "DAILY_YIELD"
COL_TOTAL_YIELD    = "TOTAL_YIELD"

SOLAR_DATE_FORMAT = "%d-%m-%Y %H:%M"

SOLAR_CRITICAL_COLUMNS    = [COL_SOLAR_DATETIME, COL_AC_POWER]
SOLAR_MEDIAN_FILL_COLUMNS = [COL_DC_POWER, COL_DAILY_YIELD, COL_TOTAL_YIELD]

CONVERSION_MIN_DC = 0   # exclusive — DC_POWER > 0 required (daylight)
CONVERSION_MIN_AC = 0   # exclusive — AC_POWER > 0 required
```

**Schema Registry** — the single lookup table every module reads
from. This is what makes the pipeline schema-agnostic:

```python
SCHEMA_REGISTRY = {
    "wind": {
        "required_columns": [
            COL_DATETIME, COL_ACTIVE_POWER, COL_WIND_SPEED,
            COL_THEORETICAL, COL_WIND_DIRECTION,
        ],
        "datetime_col":       COL_DATETIME,
        "date_format":        DATE_FORMAT,
        "critical_columns":   CRITICAL_COLUMNS,
        "median_fill_columns": MEDIAN_FILL_COLUMNS,
        "primary_power_col":  COL_ACTIVE_POWER,
        "secondary_col":      COL_WIND_SPEED,
        "reference_col":      COL_THEORETICAL,
        "ratio_name":         "efficiency_ratio",
        "min_primary":        EFFICIENCY_MIN_ACTIVE_POWER,
        "min_reference":      EFFICIENCY_MIN_THEORETICAL,
    },
    "solar": {
        "required_columns": [
            COL_SOLAR_DATETIME, COL_PLANT_ID, COL_SOURCE_KEY,
            COL_DC_POWER, COL_AC_POWER, COL_DAILY_YIELD, COL_TOTAL_YIELD,
        ],
        "datetime_col":       COL_SOLAR_DATETIME,
        "date_format":        SOLAR_DATE_FORMAT,
        "critical_columns":   SOLAR_CRITICAL_COLUMNS,
        "median_fill_columns": SOLAR_MEDIAN_FILL_COLUMNS,
        "primary_power_col":  COL_AC_POWER,
        "secondary_col":      COL_DC_POWER,
        "reference_col":      COL_DC_POWER,
        "ratio_name":         "conversion_ratio",
        "min_primary":        CONVERSION_MIN_AC,
        "min_reference":      CONVERSION_MIN_DC,
    },
}
```

**Note for solar:** `secondary_col` and `reference_col` are both
`COL_DC_POWER` — there is no separate theoretical-curve column like
wind has. `visualise.py` handles this distinction (see §6).

---

### 2. `main.py` — `--schema` Flag

```python
parser.add_argument(
    "--schema",
    choices=["wind", "solar"],
    default="wind",
    help="SCADA schema to use: wind (default) or solar.",
)
```

Pass `args.schema` through to `run_single()` and `run_batch()`.
Both functions gain a `schema: str` parameter, threaded through
every pipeline call (`ingest`, `clean`, `analyse`, `visualise`,
`export`).

---

### 3. `ingest.py` — Schema-Aware Validation

```python
def validate_schema(df: pd.DataFrame, schema: str) -> None:
    """
    ...
    Parameters:
        df (pd.DataFrame): raw DataFrame to validate
        schema (str): "wind" or "solar" — selects the required
                      column list from config.SCHEMA_REGISTRY
    ...
    """
    required = config.SCHEMA_REGISTRY[schema]["required_columns"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(
            f"Error: Schema validation failed for '{schema}' schema.\n"
            f"Missing columns: {missing}\n"
            f"Expected columns: {required}"
        )
```

---

### 4. `clean.py` — Schema-Aware Cleaning

`clean(df, schema)` reads `critical_columns`, `median_fill_columns`,
`datetime_col`, and `date_format` from the registry instead of
hardcoding wind constants. Every internal helper (`_handle_nulls`,
`_parse_datetime`) receives these as parameters rather than reaching
into `config.CRITICAL_COLUMNS` directly.

```python
def clean(df: pd.DataFrame, schema: str) -> tuple[pd.DataFrame, str]:
    cfg = config.SCHEMA_REGISTRY[schema]
    run_id = str(uuid.uuid4())
    run_timestamp = datetime.now(timezone.utc).isoformat()

    df = df.copy()
    df = _remove_duplicates(df, run_id, run_timestamp)
    df = _coerce_numeric(df, cfg, run_id, run_timestamp)
    df = _handle_nulls(df, cfg, run_id, run_timestamp)
    df = _parse_datetime(df, cfg, run_id, run_timestamp)

    return df, run_id
```

`_coerce_numeric` now iterates `cfg["critical_columns"] + cfg["median_fill_columns"]`
minus the datetime column, rather than a hardcoded wind list.

---

### 5. `analyse.py` — Parameterized Analysis + Schema-Specific Distribution

This is the key refactor. Four of the five analysis steps are
identical in *shape* between schemas — only the column names differ,
which the registry already supplies. Only the fifth step (direction
bins vs. inverter comparison) is genuinely different in kind.

```python
def analyse(df: pd.DataFrame, schema: str) -> dict[str, pd.DataFrame]:
    cfg = config.SCHEMA_REGISTRY[schema]
    return {
        "stats":       _compute_stats(df, cfg),
        "efficiency":  _compute_efficiency(df, cfg),
        "monthly":     _compute_monthly(df, cfg),
        "daily":       _compute_daily(df, cfg),
        "distribution": _compute_distribution(df, schema),
    }
```

**Rename:** the fifth result key changes from `wind_bins` to
`distribution` — this is the only breaking rename. Confirm no other
module references `"wind_bins"` by string before making this change
(as of Unit 8, only `analyse.py` and the generic preview loop in
`main.py` touch this key, and the preview loop iterates the dict
generically — no other change needed).

```python
def _compute_stats(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return df[[cfg["primary_power_col"], cfg["secondary_col"]]].describe()


def _compute_efficiency(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    total = len(df)
    operational = df[
        (df[cfg["reference_col"]] > cfg["min_reference"]) &
        (df[cfg["primary_power_col"]] > cfg["min_primary"])
    ].copy()
    excluded = total - len(operational)
    print(f"[ANALYSE] {excluded:,} rows excluded from {cfg['ratio_name']} "
          f"(zero reference or non-positive output)")

    operational[cfg["ratio_name"]] = (
        operational[cfg["primary_power_col"]] / operational[cfg["reference_col"]]
    )
    return operational[[
        cfg["datetime_col"], cfg["primary_power_col"],
        cfg["secondary_col"], cfg["reference_col"], cfg["ratio_name"],
    ]]


def _compute_monthly(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return (
        df.set_index(cfg["datetime_col"])[cfg["primary_power_col"]]
        .resample("MS").mean().to_frame()
    )


def _compute_daily(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return (
        df.set_index(cfg["datetime_col"])[cfg["primary_power_col"]]
        .resample("D").sum().to_frame()
    )


def _compute_distribution(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    if schema == "wind":
        return _compute_wind_bins(df)          # unchanged from Unit 4
    elif schema == "solar":
        return _compute_source_key_distribution(df)


def _compute_source_key_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mean and count of AC_POWER per inverter (SOURCE_KEY).

    Returns:
        pd.DataFrame: index=SOURCE_KEY, columns=['mean', 'count']
    """
    return (
        df.groupby(config.COL_SOURCE_KEY)[config.COL_AC_POWER]
        .agg(["mean", "count"])
    )
```

---

### 6. `visualise.py` — Schema-Aware Labels and Reference Line

Add an axis-label lookup at module level:

```python
AXIS_LABELS = {
    "wind":  {"primary": "Active Power (kW)", "secondary": "Wind Speed (m/s)"},
    "solar": {"primary": "AC Power (kW)",     "secondary": "DC Power (kW)"},
}
```

`visualise(results, schema)` passes `schema` and the registry
config through to each chart helper. The trend and bar charts only
need the schema-aware axis label — the logic is unchanged.

**The scatter chart requires a real design decision:** wind has an
actual theoretical-curve column to plot as a reference line. Solar
does not — `secondary_col` and `reference_col` are the same column
(`DC_POWER`). For solar, plot an idealised 1:1 reference line
(`y = x`) representing perfect DC-to-AC conversion, instead of a
data-derived curve:

```python
def _reference_series(cfg: dict, schema: str, x_values: pd.Series) -> pd.Series:
    """
    Build the reference line values for the scatter chart.

    Wind: the actual theoretical power curve column, sorted by x.
    Solar: an idealised y = x line (100% conversion baseline) —
           there is no separately modelled theoretical column.
    """
    if schema == "wind":
        return None  # handled by existing sorted_df logic in Unit 5
    elif schema == "solar":
        return x_values  # y = x
```

Update `_plot_wind_scatter` (rename to `_plot_scatter` for schema
neutrality) to check `schema` and either use the Unit 5 sorted-curve
logic (wind) or plot a straight diagonal line (solar), with the
legend label changing accordingly: `"Theoretical Power Curve"` for
wind, `"Ideal 1:1 Conversion"` for solar.

---

### 7. `export.py` — Schema-Aware Headers, Narrative, and Sheet Naming

Convert `CLEAN_DATA_HEADERS` and `EFFICIENCY_HEADERS` into
schema-keyed dicts:

```python
CLEAN_DATA_HEADERS = {
    "wind": { ... as defined in Unit 6 ... },
    "solar": {
        config.COL_SOLAR_DATETIME: "Timestamp",
        config.COL_PLANT_ID:       "Plant ID",
        config.COL_SOURCE_KEY:     "Inverter ID",
        config.COL_DC_POWER:       "DC Power (kW)",
        config.COL_AC_POWER:       "AC Power (kW)",
        config.COL_DAILY_YIELD:    "Daily Yield (kWh)",
        config.COL_TOTAL_YIELD:    "Total Yield (kWh)",
    },
}
```

**Sheet rename:** `"Power Curve Analysis"` becomes `"Efficiency
Analysis"` — schema-neutral naming, since "power curve" is
wind-specific terminology. Update this in `export()` and record the
rename in `progress-tracker.md`'s Decisions Log.

**Narrative:** extract two narrative builders,
`_build_wind_narrative(results)` and `_build_solar_narrative(results)`,
dispatched by schema inside `_write_summary`. Solar's narrative
covers: total operational hours, mean AC power output, mean
conversion ratio, and the best-performing inverter (from the
`distribution` result's `mean` column, `idxmax()`).

---

### 8. Verify Wind Mode Is Unaffected

Before testing solar, confirm the default path is unchanged:

```bash
python main.py --file data/turbine.csv
```

Must produce identical output to before this unit — same terminal
lines, same report structure. This is the regression check that
matters most: the registry refactor touches five files, and any
mistake most likely shows up here first.

---

## Dependencies

No new packages. All logic uses `pandas` and stdlib already
installed.

---

## Verify When Done

### Wind Mode — Regression
- [ ] `python main.py --file data/turbine.csv` (no `--schema` flag,
      confirming `default="wind"`) produces identical output to
      pre-Unit-9 behaviour
- [ ] `python main.py --file data/turbine.csv --schema wind` produces
      identical output to the default-flag run

### Solar Mode — New Behaviour
- [ ] Place a solar CSV (Kaggle "Solar Power Generation Data" or
      similar) at `data/solar.csv` with the seven required columns
- [ ] `python main.py --file data/solar.csv --schema solar` runs
      end-to-end with no errors
- [ ] `[LOAD]` line shows 7 columns, not 5
- [ ] Schema validation error test: rename a solar column, confirm
      the error message lists solar's expected columns, not wind's

### Analysis Results
- [ ] `results["distribution"]` for solar has index `SOURCE_KEY`
      and columns `mean`, `count` — not wind's 16-bin structure
- [ ] `results["efficiency"]` for solar contains a `conversion_ratio`
      column, not `efficiency_ratio`
- [ ] No row in solar's efficiency result has `DC_POWER <= 0`

### Charts
- [ ] Solar scatter chart legend reads `"Ideal 1:1 Conversion"` —
      not `"Theoretical Power Curve"`
- [ ] Solar chart axis labels read `"AC Power (kW)"` and
      `"DC Power (kW)"` — no wind terminology visible

### Export
- [ ] Solar report's Clean Data sheet headers match
      `CLEAN_DATA_HEADERS["solar"]` — plain English, no raw
      `DC_POWER`/`AC_POWER` strings
- [ ] Sheet is named `"Efficiency Analysis"` in both wind and
      solar reports (renamed from `"Power Curve Analysis"`)
- [ ] Solar narrative paragraph names the best-performing inverter
      by ID, not a placeholder

### Code Standards
- [ ] No raw column strings appear outside `config.py` in any of
      the five modified files
- [ ] `SCHEMA_REGISTRY` is the only place schema differences are
      defined — no `if schema == "wind"` branches exist in
      `clean.py` (only in `analyse.py`'s `_compute_distribution`
      and `visualise.py`'s scatter reference logic, where the
      difference is genuinely structural, not just column names)
- [ ] `python main.py --schema invalid` is rejected by `argparse`
      itself (choices constraint) with a clean usage error
