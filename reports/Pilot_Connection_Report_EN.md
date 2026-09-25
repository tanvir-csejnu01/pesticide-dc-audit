# Pilot Connection Report

## 1. Purpose

The earlier pilot study tested the data-processing and Data Companion (DC) connection workflow using two pesticide analytes:

- Atrazine
- Imidacloprid

The pilot used three USGS monitoring stations:

| Station | USGS Station ID | Atrazine Records | Imidacloprid Records | Intersecting HUC12 Units |
|---|---|---:|---:|---:|
| South Fork Iowa River, IA | 05451210 | 199 | 200 | 21 |
| Maple Creek, NE | 06800000 | 205 | 204 | 24 |
| Contentnea Creek, NC | 02091500 | 199 | 194 | 50 |

These values are reported in the Student Task Brief and have not yet been independently verified against the original pilot files.

---

## 2. Pilot Data Structure

According to the Student Task Brief, the pilot contains:

```text
1,201 pesticide chemical-result records
3 monitoring stations
2 analytes
95 HUC12 units
11,020 monthly HUC12 records
348 basin-month records
```

All 1,201 pesticide records reportedly have:

- three DC environmental/hydrologic inputs; and
- same-day mean discharge.

The DC data are monthly. Therefore, pesticide samples collected within the same month can share the same monthly DC values.

The DC join does not create finer temporal resolution than the original monthly DC data.

---

## 3. Basin Connection

The pilot connects pesticide monitoring stations with upstream HUC12 units.

Conceptually:

```text
Upstream HUC12 units
        │
        │ monthly DC information
        ▼
Basin-level monthly features
        │
        ▼
USGS monitoring station
        │
        ▼
Pesticide observations
```

The three pilot basins contain a total of 95 intersecting HUC12 units:

```text
South Fork Iowa River = 21
Maple Creek           = 24
Contentnea Creek      = 50
                      ----
Total                 = 95
```

These HUC12 records are aggregated to basin-month features before being connected to the pesticide observations.

---

## 4. Basin Boundaries

The pilot reportedly uses NLDI catchment/outlet-based basin boundaries.

The reported differences between calculated basin areas and published drainage areas are approximately:

| Station | Reported Area Difference |
|---|---:|
| South Fork Iowa River | +0.46% |
| Maple Creek | +0.96% |
| Contentnea Creek | −0.04% |

The three pilot basin polygons reportedly do not overlap.

These values indicate close area agreement, but the outlet placement and basin boundaries should still be verified against the original pilot files.

---

## 5. Known Discharge Gap

The Student Task Brief reports one known daily-discharge gap for South Fork Iowa River:

```text
20 August 2017
```

This missing daily discharge causes the previous 30-day mean discharge to be unavailable for four chemical-result rows associated with two sampling events.

---

## 6. Connection to the National Dataset

The pilot and national analyses serve different purposes.

| Pilot | National Analysis |
|---|---|
| 2 analytes | 84 analytes |
| 3 monitoring stations | 81 published analysis sites |
| Demonstrates the DC connection workflow | Evaluates the complete pesticide dataset |
| 1,201 chemical-result records | 955,728 chemical-result records |
| Pilot-scale basin analysis | Dataset-wide audit and modeling preparation |

The pilot therefore demonstrates how pesticide observations can be connected with upstream DC information.

However, the two pilot analytes should not be treated as the final modeling targets solely because they were used in the pilot.

The national analysis first evaluates all 84 analytes using common coverage, detection, environmental, and data-quality criteria.

---

## 7. Current Status

The original pilot files are not currently available in this workstream.

Therefore, the numerical results in this report are retained from the Student Task Brief and should be treated as **reported pilot results rather than independently reproduced results**.

Once the original pilot files are available, the main items requiring verification are:

- pilot pesticide-record counts;
- HUC12 counts and basin aggregation;
- DC-variable coverage;
- basin-area agreement;
- monitoring-station/basin connections; and
- pilot discharge values relative to the current national environmental dataset.

Detailed unresolved items are tracked in:

```text
UNRESOLVED_ISSUES.md
```