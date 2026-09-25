# Validation Summary — Phase 1

## 1. Purpose

This report summarizes the validation status of the Phase 1 national pesticide dataset.

It separates:

- completed validation;
- partially completed validation; and
- remaining work.

Detailed methods and results are documented in the corresponding audit and methodology reports.

---

## 2. Completed Validation

### 2.1 Dataset Scope and Structure

| Check | Result | Status |
|---|---|---|
| Chemical-result records | 955,728 | PASS |
| Distinct analytes | 84 | PASS |
| Analyte-to-USGS parameter-code mapping | 1:1 for all 84 analytes | PASS |
| Sampling activities | 12,896 | PASS |
| Published analysis sites | 81 | PASS |
| Physical monitoring stations | 82 | PASS |
| Water years | 2013–2022 | PASS |

The difference between 81 analysis sites and 82 physical stations is associated with the historical Illinois River station mapping.

---

### 2.2 Pesticide Data

Dataset-wide detection and reporting-level summaries were successfully generated.

| Item | Result |
|---|---:|
| Nondetected records | 78.4% |
| Detected/other records | 21.6% |
| Analytes with reporting-level changes over time | 80 of 84 |

Detailed results are stored in:

```text
outputs/tables/censoring_summary.csv
data/processed/analyte_list_84.csv
```

---

### 2.3 Environmental Coverage

Environmental matching was evaluated using the 12,896 unique sampling activities.

| Variable | Coverage |
|---|---:|
| Water temperature | 99.1% |
| Specific conductance | 98.4% |
| Discharge | 98.3% |
| Dissolved oxygen | 98.2% |
| pH | 97.8% |
| Turbidity | 26.3% |

Five environmental variables therefore have high activity-level coverage, while turbidity remains substantially less complete.

Detailed results are stored in:

```text
outputs/tables/environmental_coverage_summary.csv
```

---

### 2.4 Cross-Method Validation

Two independent environmental extraction implementations were compared.

The comparison showed:

| Check | Result |
|---|---:|
| Cell-level agreement | 98.75% |
| Activities identical across all six variables | 12,639 of 12,896 |
| Non-discharge discrepant cells | 969 |
| Activities containing non-discharge discrepancies | 257 |

The complete activity-variable exception record additionally contains **145 discharge exceptions**, giving **1,114 total environmental exceptions**.

The non-discharge discrepancies are stored in:

```text
data/processed/dataset_discrepancies.csv
```

The complete exception record is stored in:

```text
data/interim/environmental_match_exceptions.csv
```

The major non-discharge discrepancy blocks correspond to documented USGS retrieval timeouts in the Method 2 extraction.

Detailed interpretation is provided in:

```text
reports/National_Data_Audit_EN.md
reports/Environmental_Augmentation_Methods.md
```

---

### 2.5 Method 2 Reproduction

The independently obtained Method 2 extraction output was compared with:

```text
data/raw/dataset_2013_2022_G.csv
```

The comparison produced:

```text
12,896 activities
6 environmental variables
0 value differences
0 coverage differences
```

This confirms that the available Method 2 implementation reproduces the previously generated Method 2 environmental dataset.

---

### 2.6 All-Analyte Analysis

All 84 analytes were evaluated using the same comparison workflow.

The analysis includes:

- record and sampling-activity counts;
- site and temporal coverage;
- detection and nondetection patterns;
- reporting-level changes;
- environmental matching;
- concentration distributions;
- spatial-temporal patterns; and
- environmental relationships.

The main outputs are:

```text
data/processed/analyte_comparison_full.csv
data/processed/analyte_env_relationships.csv
```

For the environmental relationship analysis:

```text
Possible relationships = 1,008
Testable relationships = 985
FDR-significant relationships (q < 0.05) = 726
```

Benjamini-Hochberg FDR correction is used to account for multiple testing.

---

### 2.7 Automated Integrity Checks

Automated integrity checks were performed on the complete dataset.

The checks include:

- row-count preservation;
- preservation of original pesticide fields;
- duplicate detection;
- activity consistency;
- environmental-value consistency within activities;
- timestamp conversion;
- analyte/parameter-code mapping; and
- environmental join integrity.

The automated validation output is stored in:

```text
outputs/checks/automated_checks.csv
```

No failed integrity check is currently reported.

---

### 2.8 Manual Source Verification

Two targeted source checks were completed against USGS records for the Sope Creek discrepancy case:

1. discharge; and
2. water temperature, dissolved oxygen, and pH.

These checks confirmed that cross-method disagreement must be resolved using the original source record and the defined matching rule rather than simply selecting the method with greater coverage.

Results are stored in:

```text
outputs/checks/manual_spot_checks.csv
```

---

## 3. Partially Complete Validation

### 3.1 Environmental Provenance

Environmental values and basic matching information are available, but complete provenance is not available for every matched value.

Fields that remain incomplete include:

- source observation timestamp;
- source time zone;
- original unit;
- quality flag;
- retrieval date; and
- traceable source query.

Detailed provenance status is documented in:

```text
reports/Environmental_Augmentation_Methods.md
```

---

### 3.2 Discrepancy Verification

The major Method 2 retrieval failures have been identified from the retrieval log.

However, direct value-level verification against raw USGS records has not yet been completed for every discrepant site/period block.

Unresolved cases remain documented rather than being silently corrected.

---

### 3.3 Station Crosswalk

The distinction between:

```text
81 published analysis sites
82 physical monitoring stations
```

has been identified.

The Illinois River historical station case is documented, but a complete systematic station-crosswalk review remains pending.

---

## 4. Remaining Phase 1 Work

The main remaining tasks are:

The main remaining tasks are:

1. Complete the missing environmental source/provenance information where possible.
2. Check the remaining environmental-data differences against the original USGS records.
3. Verify that each analysis site is linked to the correct physical USGS station.
4. Review unusual environmental values and confirm them before making any changes.
5. Verify changes in laboratory methods and pesticide reporting limits.
6. Separate the data that fall within the required DC time period.
7. Collect and connect the DC/NHM-PRMS hydrologic data with the pesticide observations.
8. Extend the upstream basin/HUC12 analysis from the three pilot stations to the national sites.
9. Compare the separate imidacloprid dataset with the national dataset without combining them.

Detailed unresolved items are tracked in:

```text
UNRESOLVED_ISSUES.md
```

---

## 5. Source Verification Rule

Cross-method agreement is a **reproducibility check**, not final proof that an environmental value is correct.

When two methods disagree, the resolution should be based on:

```text
Original source record
        +
Correct monitoring station
        +
Sampling/source timestamps
        +
Environmental parameter and unit
        +
Defined matching rule
```

A value should not be selected simply because one method has greater coverage.

If the available evidence is insufficient, the case remains flagged as unresolved.

---

## 6. Validation Status

| Validation Area | Status |
|---|---|
| Dataset scope | COMPLETE |
| Sampling-activity structure | COMPLETE |
| Analyte inventory | COMPLETE |
| Environmental coverage | COMPLETE |
| Cross-method comparison | COMPLETE |
| Method 2 reproduction | COMPLETE |
| All-84-analyte comparison | COMPLETE |
| Automated integrity checks | COMPLETE |
| Manual source verification | PARTIAL |
| Environmental provenance | PARTIAL |
| Station crosswalk | PARTIAL |
| DC-window analysis | PENDING |
| DC/NHM-PRMS integration | PENDING |
| National basin/HUC12 extension | PENDING |

Phase 1 therefore has a validated national pesticide and environmental dataset structure, while provenance completion, additional source verification, and DC-related integration remain as the main outstanding tasks.