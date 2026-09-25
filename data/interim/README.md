# Interim Data

The `data/interim/` directory contains intermediate datasets, provenance records, quality-control (QC) summaries, and cross-method comparison results generated during the environmental data extraction and validation workflow.

These files are retained to make the environmental augmentation process transparent, traceable, and reproducible. They are **not the final pesticide-analysis datasets**. Final processed datasets are stored in `data/processed/`.

Two independent environmental extraction methods were used. Their results are retained separately so that environmental values can be compared at the sampling-activity level before preparing and validating the final environmental dataset.

---

## Directory Structure

```text
data/interim/
│
├── method1_activity_features.parquet
├── method2_activity_features.parquet
├── method2_environmental_matches.parquet
├── environmental_match_exceptions.csv
│
├── method2_match_method_summary.csv
├── method2_missing_reason_summary.csv
├── method2_provenance_completeness.csv
├── method2_provenance_validation.csv
│
├── method1_raw_qc/
│   ├── feature_coverage_by_site_year.csv
│   ├── feature_coverage_summary.csv
│   ├── retrieval_log.csv
│   └── sites_check.csv
│
└── method2_raw_qc/
    ├── feature_coverage_summary.csv
    ├── feature_source_summary.csv
    ├── retrieval_log.csv
    └── time_gap_summary.csv
```

---

# 1. Activity-Level Environmental Feature Files

## `method1_activity_features.parquet`

This file contains the activity-level environmental variables independently obtained using **Method 1**.

Each pesticide sampling activity is associated, where available, with six primary environmental variables:

- discharge,
- water temperature,
- dissolved oxygen,
- pH,
- specific conductance, and
- turbidity.

The purpose of this file is to preserve the Method 1 results independently from Method 2 so that the two environmental extraction procedures can be compared directly.

The file also retains the original Method 1 discharge values rather than replacing them with values selected from Method 2.

---

## `method2_activity_features.parquet`

This file contains the corresponding activity-level environmental variables independently obtained using **Method 2**.

It provides the Method 2 environmental feature set for the pesticide sampling activities and serves as the independent counterpart to `method1_activity_features.parquet`.

The two activity-level files are used for cross-method validation before preparation of the final environmental feature dataset.

---

## `method2_environmental_matches.parquet`

This file is the detailed **long-format Method 2 environmental matching and provenance table**.

Instead of storing only the final environmental values, it records environmental matching information separately for each sampling activity and environmental variable.

The table contains **77,376 activity-variable records**, corresponding to:

```text
12,896 sampling activities × 6 environmental variables
= 77,376 activity-variable records
```

Its purpose is to preserve information about **how each Method 2 environmental value was obtained**, rather than retaining only the final matched value.

Depending on availability, the provenance information includes fields related to:

- sampling activity,
- site,
- environmental variable,
- matched environmental value,
- environmental data source,
- source station,
- parameter information,
- observation timestamp,
- time zone,
- original and standardized units,
- matching method,
- temporal offset,
- permitted matching window,
- aggregation information,
- retrieval status,
- quality/provenance information, and
- missing-data information.

This file therefore provides the detailed provenance record associated with the Method 2 environmental matching workflow.

---

# 2. Cross-Method Environmental Comparison

## `environmental_match_exceptions.csv`

This file contains cases where Method 1 and Method 2 do not produce equivalent environmental results.

The file identifies information such as:

- sampling activity,
- site,
- water year,
- sampling date,
- environmental variable,
- Method 1 value,
- Method 2 value,
- numerical difference, and
- exception type.

The comparison identified **1,114 environmental matching exceptions**:

- **145 discharge exceptions**
- **969 exceptions involving the other environmental variables**

An exception can occur when:

1. both methods return values but the values differ;
2. Method 1 is missing while Method 2 has a value; or
3. Method 2 is missing while Method 1 has a value.

The 969 non-discharge exceptions correspond to the environmental discrepancies summarized in:

`data/processed/dataset_discrepancies.csv`

The 145 discharge exceptions are retained because the final augmented dataset uses the selected Method 2 discharge values in those cases, while `method1_activity_features.parquet` preserves the independently obtained Method 1 discharge values.

Therefore, `environmental_match_exceptions.csv` provides an explicit audit trail of disagreements between the two independent environmental extraction methods.

---

# 3. Method 2 Matching and Provenance Summaries

## `method2_match_method_summary.csv`

This file summarizes the environmental matching methods used by Method 2.

For each environmental variable, it reports the number of records associated with the different matching strategies or outcomes.

Depending on data availability, matching strategies can include:

- same-activity discrete measurements,
- nearest continuous observations within the permitted matching window,
- same-date daily values, and
- other permitted fallback procedures.

Its purpose is to show **how environmental values were obtained**, rather than reporting only overall feature coverage.

---

## `method2_missing_reason_summary.csv`

This file summarizes missing environmental values in the Method 2 matching/provenance output.

The summary contains information related to:

- environmental variable,
- missing reason,
- retrieval or matching status, and
- number of affected records.

Its purpose is to distinguish successfully matched observations from cases where an environmental value could not be assigned.

Where a detailed original missing reason was not preserved, the limitation is retained explicitly rather than assigning an unsupported explanation.

---

## `method2_provenance_completeness.csv`

This file evaluates the completeness of the provenance fields contained in `method2_environmental_matches.parquet`.

For each provenance field, it reports information such as:

- number of available values,
- number of missing values, and
- percentage available.

Its purpose is to determine whether sufficient provenance information is available to trace the environmental values back to their sources and matching procedures.

This is important because the audit requires not only the final environmental value but also evidence describing **where the value came from and how it was associated with the pesticide sampling activity**.

---

## `method2_provenance_validation.csv`

This file contains structural and consistency checks applied to the Method 2 provenance dataset.

The validation checks include information such as:

- expected number of pesticide sampling activities,
- number of unique activities represented,
- expected activity-variable combinations, and
- other provenance structure checks.

Each validation record contains the check, its calculated result, and a status such as `PASS` or `INFO`.

Its purpose is to provide a compact validation record showing whether the provenance table has the expected structure.

---

# 4. Method 1 Raw Quality-Control Files

The `method1_raw_qc/` directory contains diagnostic and QC outputs generated during the Method 1 environmental extraction process.

These files are retained for audit and reproducibility purposes.

## `method1_raw_qc/feature_coverage_by_site_year.csv`

This file reports environmental-variable availability by **monitoring site and water year**.

Coverage is evaluated for the environmental variables used in the Method 1 workflow.

Its purpose is to identify spatial or temporal coverage gaps that could be hidden by an overall dataset-wide coverage percentage.

For example, an environmental variable may have high overall coverage while still having substantial missingness at a particular site or during a particular water year.

---

## `method1_raw_qc/feature_coverage_summary.csv`

This file provides the overall Method 1 environmental feature coverage across the pesticide sampling activities.

For each environmental variable, it summarizes information such as:

- total sampling activities,
- number with an available value,
- number without an available value,
- percentage available, and
- source or matching information where applicable.

Depending on the variable and available USGS data, Method 1 values can originate from strategies such as:

- discrete measurement associated with the same sampling activity,
- nearest continuous observation,
- daily observation, and
- discrete time-matched observation.

This file therefore provides a high-level summary of both environmental-data coverage and the Method 1 extraction results.

---

## `method1_raw_qc/retrieval_log.csv`

This file is used to record environmental-data retrieval issues encountered during Method 1.

In the current audit package, the file contains no populated retrieval records.

It is retained as part of the Method 1 QC structure so that retrieval failures can be documented consistently if the extraction workflow is rerun.

An empty retrieval log should therefore be interpreted as **no retrieval issues recorded in this log**, rather than as an environmental dataset.

---

## `method1_raw_qc/sites_check.csv`

This file contains monitoring-site information used to verify the USGS sites involved in the environmental retrieval process.

The table covers the analysis sites and includes site-level information such as:

- monitoring location identifier,
- monitoring location name,
- state,
- drainage area, and
- time-zone information.

Its purpose is to verify that environmental retrieval is associated with the intended USGS monitoring locations and to provide a site-level QC reference.

---

# 5. Method 2 Raw Quality-Control Files

The `method2_raw_qc/` directory contains diagnostic outputs generated during the independent Method 2 environmental extraction.

These files document environmental feature availability, source selection, retrieval problems, and temporal matching behavior.

## `method2_raw_qc/feature_coverage_summary.csv`

This file summarizes Method 2 environmental-variable coverage across the pesticide sampling activities.

For each of the six primary environmental variables, it reports information such as:

- total sampling activities,
- available values,
- missing values, and
- coverage percentage.

The six primary environmental variables are:

1. discharge,
2. water temperature,
3. dissolved oxygen,
4. pH,
5. specific conductance, and
6. turbidity.

This table provides the primary high-level completeness check for Method 2.

---

## `method2_raw_qc/feature_source_summary.csv`

This file summarizes which source or matching strategy supplied each Method 2 environmental value.

For each environmental variable and source category, it reports information such as:

- number of observations, and
- percentage of observations.

Source categories can include strategies such as:

- discrete measurement associated with the same sampling activity,
- nearest continuous observation within the permitted matching window,
- daily values, and
- other permitted fallback sources.

This file is useful for determining whether an environmental variable is primarily supported by direct field measurements or by temporal/fallback matching.

---

## `method2_raw_qc/retrieval_log.csv`

This file records USGS environmental-data retrieval problems encountered during Method 2.

Records can contain information such as:

- monitoring site,
- retrieval request,
- requested start date,
- requested end date, and
- error message.

Its purpose is to distinguish environmental information that is genuinely unavailable from information that may be absent because an external USGS retrieval request failed.

For example, an API timeout should be recorded as a retrieval problem rather than automatically interpreted as evidence that no USGS observation exists.

---

## `method2_raw_qc/time_gap_summary.csv`

This file summarizes the temporal distance between pesticide sampling activities and the environmental observations selected by Method 2.

For each environmental variable, the summary reports statistics such as:

- number of matched observations,
- mean time gap,
- median time gap, and
- maximum time gap.

Time gaps are reported in minutes where applicable.

Its purpose is to verify that environmental observations were selected within the intended temporal matching rules and to identify variables for which the selected environmental observations tend to occur farther from the pesticide sampling time.

---

# 6. Relationship to the Processed Data

The files in `data/interim/` support environmental extraction, provenance tracking, quality control, and comparison between the two independent environmental extraction methods.

They should not be confused with the processed datasets used for the main pesticide analysis.

The consolidated activity-level environmental feature dataset is stored as:

`data/processed/sample_features.parquet`

The final enriched pesticide-result dataset is stored as:

`data/processed/t2_pest_concs_enriched_v2.parquet`

The overall relationship can be summarized as:

```text
USGS pesticide sampling activities
            │
            ├──────────────────────┐
            │                      │
            ▼                      ▼
        Method 1               Method 2
            │                      │
            ▼                      ▼
method1_activity_          method2_activity_
features.parquet           features.parquet
            │                      │
            │                      ├── method2_environmental_matches.parquet
            │                      │          │
            │                      │          └── Detailed provenance
            │                      │
            └──────────┬───────────┘
                       │
                       ▼
              Cross-method comparison
                       │
                       ▼
         environmental_match_exceptions.csv
                       │
                       ▼
            Validated/selected features
                       │
                       ▼
      data/processed/sample_features.parquet
                       │
                       ▼
        Final enriched pesticide dataset
                       │
                       ▼
data/processed/t2_pest_concs_enriched_v2.parquet
```

---

# 7. Environmental Method Comparison

The two environmental extraction methods were compared independently at the sampling-activity level.

The comparison identified **1,114 environmental matching exceptions**:

```text
Discharge exceptions:                   145
Other environmental exceptions:         969
                                      -----
Total exceptions:                     1,114
```

The complete set of differences is retained in:

`environmental_match_exceptions.csv`

This design intentionally preserves the independent Method 1 and Method 2 results rather than overwriting one method with the other before validation.

This allows the environmental augmentation process to be independently audited.

---

# 8. Provenance Correction

During preparation and validation of the Method 1 activity-level environmental dataset, outdated environmental provenance information was identified for the Illinois River site:

`Site_Abb == "Illinois R, IL"`

The issue affected **366 value/provenance cells** in:

`data/processed/sample_features.parquet`

These records were updated using the corrected station alias and environmental extraction results.

The final delivered enriched pesticide dataset:

`data/processed/t2_pest_concs_enriched_v2.parquet`

was not affected by this provenance issue.

Additional information about this correction and other known limitations is documented in:

`UNRESOLVED_ISSUES.md`

---

# 9. Purpose of Retaining the Interim Files

The interim files are intentionally retained even when some of their information is also represented in the processed datasets.

Together, they provide the audit trail needed to answer four important questions.

### 1. What environmental value was assigned to each pesticide sampling activity?

See:

- `method1_activity_features.parquet`
- `method2_activity_features.parquet`

### 2. How was a Method 2 environmental value obtained?

See:

- `method2_environmental_matches.parquet`
- `method2_match_method_summary.csv`
- `method2_provenance_completeness.csv`
- `method2_provenance_validation.csv`

### 3. Where did the two independent environmental extraction methods disagree?

See:

- `environmental_match_exceptions.csv`

### 4. Were there coverage gaps, source differences, API retrieval failures, or temporal-matching issues?

See:

- `method1_raw_qc/`
- `method2_raw_qc/`

Together, these files make the environmental augmentation workflow auditable while keeping intermediate diagnostic information separate from the final processed pesticide-analysis datasets.