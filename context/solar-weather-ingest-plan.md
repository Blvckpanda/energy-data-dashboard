# Solar Weather Ingest Plan (true IEC 61724 PR)

Status: implemented 2026-11-07. Option B is active: the report
reports irradiance-normalized output and `nameplate_kw` remains
`None`, so no capacity-normalized claim is made. The gated
performance-ratio calculation is present and covered by a test that
sets a documented nameplate.
Date: 2026-11-07.

This plan unblocks the one deliberately deferred solar claim: a true
IEC 61724 performance ratio, which needs plane-of-array irradiance.
The current `AC/DC Conversion Ratio` stays honest until this lands.

## What the data actually provides

Verified against the Kaggle dataset page (Ani Kannal, Solar Power
Generation Data, two plants in India, 34 days, 15-minute intervals):

- Four files: `Plant_1_Generation_Data.csv`,
  `Plant_1_Weather_Sensor_Data.csv`, and the same pair for plant 2.
- Generation files, one row per inverter per interval (22 inverters
  per plant): `DATE_TIME`, `PLANT_ID`, `SOURCE_KEY`, `DC_POWER`,
  `AC_POWER` (kW), `DAILY_YIELD`, `TOTAL_YIELD`.
- Weather files, plant level, a single sensor array:
  `DATE_TIME`, `PLANT_ID`, `SOURCE_KEY`, `AMBIENT_TEMPERATURE`,
  `MODULE_TEMPERATURE`, `IRRADIATION` (recorded on a 0 to about 1.22
  scale, which is kW/m2; the implemented ingest converts it to W/m2).

Timestamp layouts are mixed in the real files: Plant 1 generation is
`%d-%m-%Y %H:%M`, while Plant 2 generation and both weather files are
`%Y-%m-%d %H:%M:%S`. The ingest accepts either layout per file but
requires the whole file to parse under one of them.

**The dataset documents no nameplate capacity, no module orientation,
and no sensor tilt.** That matters because IEC 61724 PR is
`E_AC / (P_stc * H_poa / 1000)`; without a documented `P_stc` the
metric cannot be claimed.

## Decision gate: nameplate capacity

This is the one point that needs a user decision before a true PR can
be reported.

- **Option A, documented capacity supplied.** Add `nameplate_kw` to the
  new schema's registry entry (a config-only change). PR is computed
  and may carry the IEC 61724 name, with deviations disclosed below.
- **Option B, no documented capacity (default).** Ingest the weather
  data anyway and report an irradiance-normalized output
  (`AC_POWER / IRRADIATION`, kW per W/m2) under a neutral label such as
  "Irradiance-Normalized Output". No IEC claim anywhere.

Recommendation: build the ingest for both, gate the PR calculation and
the IEC wording strictly on `nameplate_kw` being present and sourced.
Do not infer a nameplate from maximum observed power: that would make
the denominator a function of the result and turn a measurement into
an assumption.

## Pipeline design

A new registry schema, `solar_weather`, added in `config.py` only.
The existing seven-column `solar` schema is untouched, so current
generation-file runs and the portfolio demo keep working.

Required columns (exact names, registry validation unchanged):

- `DATE_TIME` (15-minute, same format as solar),
- `PLANT_ID`,
- `AC_POWER`, `DC_POWER`,
- `IRRADIATION`,
- `AMBIENT_TEMPERATURE`, `MODULE_TEMPERATURE`.

Optional/derived: `nameplate_kw` lives in the registry, not the CSV.

### Merge rules

1. Aggregate generation to plant-interval: sum `AC_POWER`, `DC_POWER`,
   `DAILY_YIELD` and `TOTAL_YIELD` across the 22 inverters, grouped by
   `PLANT_ID` and `DATE_TIME`. Count inverters per interval and log
   intervals with fewer than the plant's modal inverter count.
2. Join weather on `(PLANT_ID, DATE_TIME)` only. Never join on
   `SOURCE_KEY`: generation keys are inverter IDs, weather keys are
   sensor IDs, and plant 2 has more than one sensor entry.
3. Keep generation rows with no weather as "no irradiance" and exclude
   them from PR with a logged count; keep weather without generation
   out of the analysis entirely.
4. Do not carry `SOURCE_KEY` into the merged frame; it is meaningless
   after plant-level aggregation.

### Validation and cleaning rules

- Duplicate `(PLANT_ID, DATE_TIME)` in either source: drop duplicates,
  log counts.
- Negative `IRRADIATION`: treat as invalid, log, exclude from PR.
- Night and dawn/dusk: exclude rows with `IRRADIATION` below a
  documented threshold (proposed 50 W/m2) from PR so the ratio is not
  dominated by near-zero denominators. The threshold is a named config
  constant, not a literal.
- PR above 1.2 or below 0 is flagged as an anomaly, never clipped
  silently.
- Timestamps are local, naive, India (no DST). Keep naive for
  consistency with the existing pipeline; state it in the narrative.
- Gaps in the 15-minute series are reported, not forward-filled.

### Computation

With `nameplate_kw` present:

- interval PR = `AC_POWER / (nameplate_kw * IRRADIATION / 1000)`.
- daily PR = sum(AC interval energy) / (nameplate_kw * sum(interval
  irradiance)/1000 / 4), using the 15-minute interval count; the
  formula is implemented once, in `analyse.py`, and unit-tested with a
  hand-computed case.

Without `nameplate_kw`: no PR, no IEC wording; the schema reports
irradiance-normalized output and the methodology note says the
nameplate is not documented.

### Reporting

- `ratio_label`: "Performance Ratio (IEC 61724)" only in Option A;
  "Irradiance-Normalized Output" in Option B.
- Methodology note lists the deviations in both cases: plant-level
  single sensor, orientation/tilt undocumented, no temperature
  correction in this version, 15-minute pre-aggregated rows.
- Narrative mentions plant count and the nameplate source when PR is
  active.

## Tests (synthetic only, no CSVs committed)

- Merge: two inverters plus one weather row produce one row with
  summed AC/DC and the correct interval count.
- PR arithmetic: a hand-computed irradiance and capacity case matches
  to the decimal.
- Threshold: rows below the irradiance constant are excluded and
  counted; no zero-denominator warnings.
- Duplicates, negative irradiance and gaps produce log entries with
  run lineage, exactly like the existing cleaning checks.
- Registry validation: a generation-only file is rejected by the new
  schema with the existing plain-English missing-column error.
- Regression: the seven-column solar schema and its demo behave
  unchanged.

## Deliverables, in order

1. `config.py` registry entry plus constants; no other module changes.
2. `ingest.py` support for a second input file (weather) or a merged
   input mode, decided at implementation time; the CLI gains one flag,
   `--weather-file`, valid only for `solar_weather`.
3. Plant-level aggregation and join, with quality-log entries.
4. PR calculation in `analyse.py`, gated on `nameplate_kw`.
5. Narrative and report wording gated on the same flag.
6. README data section, decisions entry, tests, PR.

## Human steps before implementation

1. Download the four Kaggle CSVs into `data/` (gitignored), keeping the
   original filenames.
2. Decide the capacity question: documented `nameplate_kw` or default
   to the irradiance-normalized label.
3. Confirm the dataset licence terms on the Kaggle page; the README
   already attributes the source. "Data files (c) Original Authors"
   is the stated licence line; verify reuse before publishing derived
   numbers.

## Acceptance criteria

- With `nameplate_kw`: PR reported, labelled IEC 61724, deviations
  disclosed, hand-computed test case exact.
- Without it: no PR value and no IEC claim anywhere in code, docs or
  reports.
- Night rows and zero-irradiance rows never reach the ratio.
- Existing solar and wind behaviours are unchanged; suite and ruff
  green; demo untouched because it is wind-only.

## Risks

- The irradiance sensor's plane and tilt are undocumented; a true PR
  comparison to nameplate would carry that uncertainty. Disclose it.
- Plant 2's sensor-to-inverter mapping is ambiguous; plant-level
  joining sidesteps it, at the cost of losing per-inverter irradiance.
- No temperature correction in v1; module temperature is reported but
  not applied.
- A nameplate supplied later changes reported history; record the value
  and its source in the decision log when it is set.
