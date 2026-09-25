# National Data Audit

## 1. Purpose

The national data audit verifies the completeness, environmental augmentation, consistency, and reproducibility of the full USGS pesticide dataset before subsequent analysis and modeling.

This audit replaces the earlier two-analyte pilot as the basis for dataset-wide validation. The pilot remains useful as a demonstration of the processing workflow, but conclusions about the complete dataset are based on all **84 analytes**.

The audit currently covers:

- dataset scope and completeness;
- analyte inventory;
- sampling-activity structure;
- environmental-variable coverage;
- comparison of two independent environmental extraction methods; and
- automated dataset validation.

The DC analysis window, DC/NHM-PRMS hydrology, and later spatial extension are outside the current audit and remain pending.

The main audit scripts are:

```text
scripts/08_build_analyte_inventory.py
scripts/10_cross_implementation_audit.py
```

---

## 2. Dataset Scope

The complete base release contains:

| Quantity | Count / Range | Meaning |
|---|---:|---|
| Chemical-result records | 955,728 | Individual analyte results from sampling activities |
| Distinct analytes | 84 | Unique pesticide analytes |
| Published analysis sites | 81 | Distinct analysis-site abbreviations |
| Physical monitoring stations | 82 | Includes the additional historical Illinois River station |
| Sampling activities | 12,896 | Distinct water-sampling events |
| Water years | 2013–2022 | Period represented in the base release |

All 84 analytes are retained.

No pesticide-result row, sampling activity, or analysis site was removed during environmental augmentation. Original pesticide-result values were not interpolated or imputed.

The environmental variables were added to the original pesticide records.

---

## 3. Chemical Results vs. Sampling Activities

The **955,728 rows are not 955,728 independent water samples**.

They represent chemical results from **12,896 sampling activities**.

One water sample collected at a particular site, date, and time can be analyzed for many pesticide chemicals.

For example:

```text
One sampling activity
        │
        ├── Atrazine concentration
        ├── Simazine concentration
        ├── Imidacloprid concentration
        └── other chemical concentrations
        │
        └── one set of environmental conditions
```

Therefore, environmental matching is performed at the **sampling-activity level**.

The environmental values associated with one sampling activity are then joined to all chemical-result records belonging to that activity.

For this reason, environmental coverage in this report is calculated using the **12,896 sampling activities**, rather than the 955,728 chemical-result rows.

---

## 4. Analyte Inventory

The complete analyte inventory is stored in:

```text
data/processed/analyte_list_84.csv
```

All 84 analytes are included regardless of detection frequency or data coverage.

Summary characteristics include:

| Characteristic | Result |
|---|---:|
| Analytes retained | 84 |
| Analytes with no detected site | 0 |
| Minimum chemical-result records per analyte | 3,928 |
| Median records per analyte | approximately 11,500 |
| Maximum records per analyte | 12,780 |

Some analytes were measured at fewer than all 81 analysis sites.

Reporting levels also changed over time for many analytes. These changes are important when interpreting temporal changes in detection rates.

Detailed analyte-level comparisons are provided in:

```text
data/processed/analyte_comparison_full.csv
```

and documented in:

```text
reports/comparative_analyze_analysis_eng.md
```

---

## 5. Environmental Coverage

Six environmental variables were matched to the 12,896 sampling activities.

| Environmental Variable | Matched Activities | Coverage | Missing |
|---|---:|---:|---:|
| Water temperature | 12,780 | 99.1% | 116 |
| Specific conductance | 12,691 | 98.4% | 205 |
| Discharge | 12,679 | 98.3% | 217 |
| Dissolved oxygen | 12,662 | 98.2% | 234 |
| pH | 12,612 | 97.8% | 284 |
| Turbidity | 3,387 | 26.3% | 9,509 |

Five environmental variables therefore have approximately **98–99% activity-level coverage**.

Turbidity has substantially lower coverage at **26.3%** because suitable turbidity observations are unavailable for many site/time combinations.

At the chemical-result level:

```text
902,499 rows (94.4%)
```

have all five higher-coverage environmental variables, while:

```text
236,121 rows (24.7%)
```

also have turbidity.

The dataset is **not restricted to complete cases**. Missing environmental values remain explicitly missing, and all 955,728 pesticide-result records are retained.

---

## 6. Independent Environmental Method Comparison

Two independently implemented environmental extraction methods were compared as a reproducibility check.

The comparison evaluates whether both methods assign the same environmental values to the same pesticide sampling activities.

Overall comparison results were:

| Comparison | Result |
|---|---:|
| Cell-level agreement across six environmental variables | 98.75% |
| Activities identical across all six variables | 12,639 / 12,896 (98.01%) |
| Non-discharge discrepant cells | 969 |
| Activities containing those discrepancies | 257 |

The detailed non-discharge discrepancies are retained in:

```text
data/processed/dataset_discrepancies.csv
```

The complete cross-method exception record, including discharge exceptions, is retained in:

```text
data/interim/environmental_match_exceptions.csv
```

The complete activity-variable comparison identified:

```text
Discharge exceptions:                   145
Other environmental exceptions:         969
                                      -----
Total exceptions:                     1,114
```

High agreement provides evidence that the environmental augmentation is reproducible across the two implementations. However, agreement alone does not prove that a matched value is correct, so discrepancies were investigated separately.

---

## 7. Investigation of Method Differences

The largest non-discharge discrepancies were concentrated in seven site/period blocks:

| Site | Period |
|---|---|
| Sope Creek, GA | 2012–2014 |
| Red River, ND | 2012–2014 |
| Maple Creek, NE | 2012–2014 |
| Truckee River, NV | 2014–2016 |
| Shingle Creek, MN | 2018–2020 |
| Mississippi River, MN | 2018–2020 |
| Sacramento River, CA | 2020–2022 |

The Method 2 retrieval log confirms USGS discrete-data retrieval timeouts for these blocks.

This explains why Method 2 is missing some environmental observations that were successfully obtained by Method 1.

The retrieval failures are documented in:

```text
data/interim/method2_raw_qc/retrieval_log.csv
```

---

## 8. Manual USGS Verification

Two targeted checks were performed using raw USGS records for Sope Creek, Georgia.

### 8.1 Discharge Check

For the sampling event on October 11, 2012, the reviewed USGS gauge record gave:

```text
Discharge = 5.15 cfs
```

at the relevant sampling time.

This agreed with the alternative discharge extraction rather than the original same-activity discharge value of 3.1 cfs.

Based on this validation, the selected discharge values were updated for the affected cases.

A total of:

```text
145 sampling activities
```

were affected by the discharge correction.

### 8.2 Water-Quality Check

For the same Sope Creek sampling activity, raw USGS/WQP records confirmed field measurements for:

```text
Water temperature = 14.9 °C
Dissolved oxygen  = 9.3 mg/L
pH                = 6.6
```

These values were present in the discrete sampling records even though the alternative extraction did not retrieve them.

This confirmed that the discrete environmental measurements obtained by Method 1 should be retained for these non-discharge variables.

The manual checks demonstrate why agreement between implementations alone is insufficient: the original USGS records are the reference when conflicting values require investigation.

Manual verification records are retained in:

```text
outputs/checks/manual_spot_checks.csv
```

---

## 9. Final Environmental Dataset

The final enriched pesticide dataset is:

```text
data/processed/t2_pest_concs_enriched_v2.parquet
```

The environmental values were selected after cross-method comparison and targeted source verification.

The final dataset retains:

- all 955,728 pesticide-result records;
- all 84 analytes;
- all original pesticide-result fields; and
- the six environmental variables where matching data are available.

No missing environmental value was filled by interpolation or carry-forward.

---

## 10. Automated Validation

Automated checks were performed across the complete dataset.

| Validation Check | Result |
|---|---|
| Input/output row count preserved | **PASS** — 955,728 rows |
| Original 14 pesticide columns unchanged | **PASS** |
| Environmental values linked to the correct sampling activity | **PASS** |
| Local time → UTC → local time conversion | **PASS** for all 12,896 activities |
| One consistent environmental feature set per activity | **PASS** |
| Analyte ↔ USGS parameter-code mapping | **PASS** — 1:1 for all 84 analytes |
| Duplicate rows | **PASS** — none identified |

These checks cover the complete dataset rather than a sample of records.

---

## 11. Manual vs. Automated Validation

The two validation approaches serve different purposes.

### Automated Validation

Used to check the entire dataset for:

- row preservation;
- duplicate records;
- activity consistency;
- time conversion;
- analyte/parameter-code mapping; and
- environmental-feature consistency.

### Manual Source Verification

Used for selected discrepancies where the correct environmental value must be checked directly against USGS source records.

Manual verification has not been performed for every environmental observation.

---

## 12. Current Audit Conclusion

The national audit confirms that:

1. the complete **84-analyte dataset** has been retained;
2. the **955,728 chemical-result records** correspond to **12,896 independent sampling activities**;
3. five environmental variables have approximately **98–99% activity-level coverage**, while turbidity coverage is substantially lower;
4. two independent environmental extraction implementations show high overall agreement;
5. the main discrepancy blocks are associated with documented environmental-data retrieval failures;
6. automated structural checks pass across the complete dataset; and
7. remaining provenance and source-verification limitations are explicitly documented rather than hidden or imputed.

The audited dataset therefore provides the current data foundation for the subsequent analyte comparison and modeling stages.

---

## 13. Remaining Work

The following tasks remain outside or incomplete within the current audit:

- separate the full dataset from the required **DC analysis window**;
- complete chemical-identifier and parent/degradate verification;
- complete the systematic monitoring-station crosswalk;
- improve environmental provenance, particularly source timestamps, units, quality flags, and signed time offsets;
- complete additional value-level verification for unresolved discrepancy cases;
- integrate the DC/NHM-PRMS hydrologic data; and
- evaluate the later spatial-extension dataset.

Detailed unresolved items are tracked in:

```text
UNRESOLVED_ISSUES.md
```