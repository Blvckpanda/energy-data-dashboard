# Power-Curve Cross-Check (2026-11-05)

Independent validation of the pipeline's binned wind power curve
(`analyse._compute_power_curve`), the D4 follow-up from the project
review. Reproduce it from the repository root with:

```
.venv/Scripts/python.exe scripts/crosscheck_power_curve.py
```

## Method

- Data: the real wind SCADA run, `data/turbine.csv`, loaded and cleaned
  through the pipeline itself (`ingest` + `clean`).
- Frame: 39,267 of 50,530 rows (77.7%) survive the pipeline's own
  operational-row exclusion rule (reference and primary power above the
  registry's minimum thresholds); every implementation sees identical
  rows.
- Implementations compared:
  1. The pipeline curve (pandas `pd.cut(..., right=False)` bins).
  2. A vendored equivalent of OpenOA's `openoa.utils.power_curve.IEC`
     binned-mean algorithm (BSD-3; re-implemented with numpy floor
     arithmetic, no OpenOA install required).
  3. A pandas `pd.cut` reference written independently of (1) and (2).
- Conventions fixed before comparing: identical left-closed/right-open
  0.5 m/s bins, common wind-speed range 0 to 25 m/s, and only bins with
  at least 6 valid samples in the cross-check frame (a stricter bar
  than the registry's 3-sample sufficiency minimum).
- brightwind was rejected for this check: it is a wind
  resource-assessment library, and its power-curve API is not a fit.

## Results

All 43 comparable bins:

| Bin (m/s) | Samples | Pipeline (kW) | OpenOA (kW) | Reference (kW) | OpenOA diff | Reference diff |
|---|---|---|---|---|---|---|
| [3.0, 3.5) | 852 | 27.84 | 27.84 | 27.84 | 0.000% | 0.000% |
| [3.5, 4.0) | 1,499 | 67.50 | 67.50 | 67.50 | 0.000% | 0.000% |
| [4.0, 4.5) | 1,813 | 136.92 | 136.92 | 136.92 | 0.000% | 0.000% |
| [4.5, 5.0) | 1,767 | 232.53 | 232.53 | 232.53 | 0.000% | 0.000% |
| [5.0, 5.5) | 1,823 | 342.82 | 342.82 | 342.82 | 0.000% | 0.000% |
| [5.5, 6.0) | 2,111 | 471.49 | 471.49 | 471.49 | 0.000% | 0.000% |
| [6.0, 6.5) | 2,275 | 624.33 | 624.33 | 624.33 | 0.000% | 0.000% |
| [6.5, 7.0) | 2,332 | 807.60 | 807.60 | 807.60 | 0.000% | 0.000% |
| [7.0, 7.5) | 2,306 | 1,011.59 | 1,011.59 | 1,011.59 | 0.000% | 0.000% |
| [7.5, 8.0) | 2,181 | 1,246.36 | 1,246.36 | 1,246.36 | 0.000% | 0.000% |
| [8.0, 8.5) | 2,031 | 1,491.07 | 1,491.07 | 1,491.07 | 0.000% | 0.000% |
| [8.5, 9.0) | 1,798 | 1,730.01 | 1,730.01 | 1,730.01 | 0.000% | 0.000% |
| [9.0, 9.5) | 1,687 | 1,992.17 | 1,992.17 | 1,992.17 | 0.000% | 0.000% |
| [9.5, 10.0) | 1,549 | 2,229.05 | 2,229.05 | 2,229.05 | 0.000% | 0.000% |
| [10.0, 10.5) | 1,549 | 2,485.14 | 2,485.14 | 2,485.14 | 0.000% | 0.000% |
| [10.5, 11.0) | 1,490 | 2,731.67 | 2,731.67 | 2,731.67 | 0.000% | 0.000% |
| [11.0, 11.5) | 1,361 | 2,965.47 | 2,965.47 | 2,965.47 | 0.000% | 0.000% |
| [11.5, 12.0) | 1,293 | 3,191.32 | 3,191.32 | 3,191.32 | 0.000% | 0.000% |
| [12.0, 12.5) | 1,125 | 3,349.99 | 3,349.99 | 3,349.99 | 0.000% | 0.000% |
| [12.5, 13.0) | 1,068 | 3,459.70 | 3,459.70 | 3,459.70 | 0.000% | 0.000% |
| [13.0, 13.5) | 881 | 3,500.83 | 3,500.83 | 3,500.83 | 0.000% | 0.000% |
| [13.5, 14.0) | 683 | 3,502.75 | 3,502.75 | 3,502.75 | 0.000% | 0.000% |
| [14.0, 14.5) | 547 | 3,517.70 | 3,517.70 | 3,517.70 | 0.000% | 0.000% |
| [14.5, 15.0) | 490 | 3,431.67 | 3,431.67 | 3,431.67 | 0.000% | 0.000% |
| [15.0, 15.5) | 422 | 3,516.39 | 3,516.39 | 3,516.39 | 0.000% | 0.000% |
| [15.5, 16.0) | 361 | 3,495.99 | 3,495.99 | 3,495.99 | 0.000% | 0.000% |
| [16.0, 16.5) | 320 | 3,494.13 | 3,494.13 | 3,494.13 | 0.000% | 0.000% |
| [16.5, 17.0) | 242 | 3,518.86 | 3,518.86 | 3,518.86 | 0.000% | 0.000% |
| [17.0, 17.5) | 217 | 3,541.73 | 3,541.73 | 3,541.73 | 0.000% | 0.000% |
| [17.5, 18.0) | 217 | 3,563.85 | 3,563.85 | 3,563.85 | 0.000% | 0.000% |
| [18.0, 18.5) | 210 | 3,546.27 | 3,546.27 | 3,546.27 | 0.000% | 0.000% |
| [18.5, 19.0) | 190 | 3,546.64 | 3,546.64 | 3,546.64 | 0.000% | 0.000% |
| [19.0, 19.5) | 167 | 3,553.65 | 3,553.65 | 3,553.65 | 0.000% | 0.000% |
| [19.5, 20.0) | 135 | 3,572.18 | 3,572.18 | 3,572.18 | 0.000% | 0.000% |
| [20.0, 20.5) | 97 | 3,563.74 | 3,563.74 | 3,563.74 | 0.000% | 0.000% |
| [20.5, 21.0) | 67 | 3,570.67 | 3,570.67 | 3,570.67 | 0.000% | 0.000% |
| [21.0, 21.5) | 35 | 3,561.57 | 3,561.57 | 3,561.57 | 0.000% | 0.000% |
| [21.5, 22.0) | 21 | 3,561.49 | 3,561.49 | 3,561.49 | 0.000% | 0.000% |
| [22.0, 22.5) | 10 | 3,571.85 | 3,571.85 | 3,571.85 | 0.000% | 0.000% |
| [22.5, 23.0) | 17 | 3,601.63 | 3,601.63 | 3,601.63 | 0.000% | 0.000% |
| [23.0, 23.5) | 12 | 3,601.18 | 3,601.18 | 3,601.18 | 0.000% | 0.000% |
| [23.5, 24.0) | 8 | 3,601.59 | 3,601.59 | 3,601.59 | 0.000% | 0.000% |
| [24.0, 24.5) | 6 | 3,601.12 | 3,601.12 | 3,601.12 | 0.000% | 0.000% |

Overall mean absolute difference vs the pipeline: OpenOA 0.000%,
reference 0.000%. No bin disagrees by more than 2%.

## Conclusion

The pipeline's binned power curve reproduces an independent
OpenOA-equivalent IEC-style binned implementation and a separately
written pandas reference exactly: 0.000% mean absolute difference over
all 43 operational bins between 0 and 25 m/s, with no bin above the 2%
flag threshold. Identical means were expected once the conventions were
fixed (same rows, same left-closed 0.5 m/s bins), and the check confirms
the pipeline implements the binning it claims; an exact match is the
correct result, not a suspicious one, because all three implementations
group the same rows into identical intervals. The known deviations from
a full IEC 61400-12-1 campaign still apply and are disclosed in the
code and the report: nacelle anemometer wind speeds, no air-density or
turbulence correction, and 10-minute pre-aggregated rows.
