# Processed Data

The `data/processed/` directory contains the cleaned, standardized, enriched, and analysis-ready datasets produced by the pesticide data-audit workflow.

Unlike `data/interim/`, which retains intermediate environmental extraction, provenance, and cross-method validation files, the files in this directory represent the processed datasets used for the main audit analyses.

The processed data support several parts of the project:

- pesticide concentration analysis,
- sampling-activity analysis,
- environmental feature integration,
- Method 1 versus Method 2 discrepancy assessment,
- analyte-level coverage analysis,
- environmental relationship analysis, and
- final enriched pesticide data preparation.

---

## Directory Structure

```text
data/processed/
│
├── t2_pest_concs.parquet
├── activity_master.parquet
├── sample_features.parquet
├── t2_pest_concs_enriched_v2.parquet
│
├── analyte_list_84.csv
├── analyte_comparison_full.csv
├── analyte_env_relationships.csv
├── dataset_discrepancies.csv
│
└── README.md
```

A large CSV export named `dataset_2013_2022_final.csv` may also exist locally, but it is not retained in version control because it duplicates the final enriched Parquet dataset and is substantially larger.

---

# 1. Core Pesticide Concentration Dataset

## `t2_pest_concs.parquet`

This file contains the processed pesticide concentration records derived from the original USGS pesticide concentration table.

It represents the pesticide-result level of the project and preserves the concentration observations needed for the subsequent audit and environmental augmentation.

A single sampling activity can contain results for multiple analytes. Therefore, this file should not be interpreted as having one row per sampling activity.

Its main purposes are to provide:

- pesticide concentration results,
- analyte identifiers,
- sampling-activity identifiers,
- monitoring-site information,
- sampling dates and times,
- detection/nondetection information,
- concentration-related metadata, and
- the base pesticide records required for subsequent environmental enrichment.

This file is the processed pesticide concentration foundation from which the enriched pesticide dataset is constructed.

---

# 2. Sampling-Activity Master Table

## `activity_master.parquet`

This file contains the master list of distinct pesticide sampling activities used in the environmental matching workflow.

The pesticide concentration dataset contains multiple chemical-result records from the same field sampling event. Environmental variables, however, should generally be matched to the **sampling activity**, rather than independently retrieved for every pesticide-result row.

Therefore, the pesticide-result data are first reduced to distinct sampling activities.

The activity master contains **12,896 distinct sampling activities** used in the current environmental matching workflow.

Conceptually:

```text
Pesticide-result records
        │
        │ identify distinct sampling events
        ▼
activity_master.parquet
        │
        │ one activity can correspond to
        │ multiple pesticide-result records
        ▼
Environmental matching
```

Its main purposes are to:

- define the unique sampling events,
- prevent repeated environmental retrieval for multiple analytes collected during the same activity,
- provide the sampling timestamp used for environmental matching,
- provide site information needed for USGS retrieval, and
- serve as the common activity-level reference for Method 1 and Method 2.

This file is therefore the bridge between the pesticide-result data and the activity-level environmental matching workflow. However, if you open the file in pandas datafarme then you will find these features:
Index(['Activity_ActivityIdentifier', 'Pesticide_Site', 'Site_Abb',
       'Activity_StartDate', 'Activity_StartTime', 'Activity_StartTimeZone',
       'Activity_TypeCode', 'Activity_MediaSubdivision', 'n_analytes',
       'Discharge_cfs', 'Water_Temperature_C', 'Dissolved_Oxygen_mg_L', 'pH',
       'Turbidity_FNU', 'Specific_Conductance', 'sample_date', 'dc_window'],
      dtype='object')

---

# 3. Consolidated Environmental Feature Dataset

## `sample_features.parquet`

This file contains the consolidated activity-level environmental features associated with the pesticide sampling activities.

The environmental variables include the six primary variables used in the project:

1. discharge,
2. water temperature,
3. dissolved oxygen,
4. pH,
5. specific conductance, and
6. turbidity.

The environmental extraction workflow was evaluated using two independent methods. Their intermediate results are retained in:

```text
data/interim/method1_activity_features.parquet
data/interim/method2_activity_features.parquet
```

The detailed Method 2 provenance records are retained in:

```text
data/interim/method2_environmental_matches.parquet
```

`sample_features.parquet` represents the consolidated activity-level environmental feature dataset used in the processed workflow.

Conceptually:

```text
activity_master.parquet
        │
        ├───────────────┐
        ▼               ▼
    Method 1        Method 2
        │               │
        └───────┬───────┘
                │
        validation/selection
                │
                ▼
    sample_features.parquet
```

The purpose of this file is to provide one activity-level environmental feature set that can subsequently be joined back to the pesticide-result records.

Detailed matching provenance and independent method outputs remain in `data/interim/` so that this processed table does not need to contain every intermediate diagnostic record. 


## Data Dictionary for `sample_features.parquet`



The suffixes used in the environmental columns have the following general meanings:

- `_source`: identifies the source or matching method used to obtain the environmental value.
- `_gap_min`: temporal difference, in minutes, between the pesticide sampling time and the environmental observation used for the match.
- `_cfs`: cubic feet per second.
- `_mg_L`: milligrams per liter.
- `_FNU`: Formazin Nephelometric Units.
- `_NTU`: Nephelometric Turbidity Units.

### Column Dictionary

| Column | Meaning | Unit / Format |
|---|---|---|
| `activity_id` | Unique identifier for the pesticide sampling activity. Multiple pesticide-result records can belong to the same activity. | Identifier |
| `Location_Identifier` | USGS monitoring-location identifier associated with the pesticide sampling activity. | USGS site/station identifier |
| `Site_Abb` | Short name or abbreviation used for the monitoring site. | Text |
| `Water_Year` | Water year associated with the sampling activity. A U.S. water year runs from October 1 of the previous calendar year through September 30 of the named year. | Year |
| `sample_dt_utc` | Date and time of the pesticide sampling activity converted to Coordinated Universal Time (UTC). This timestamp is used as the temporal reference for environmental matching. | UTC datetime |

---

### Primary Environmental Variables

| Column | Meaning | Unit |
|---|---|---|
| `Discharge_cfs` | Stream discharge assigned to the pesticide sampling activity after environmental matching and validation. | ft³/s (cfs) |
| `Water_Temperature_C` | Water temperature assigned to the sampling activity. | °C |
| `Dissolved_Oxygen_mg_L` | Dissolved oxygen concentration assigned to the sampling activity. | mg/L |
| `pH` | pH assigned to the sampling activity. | Standard pH units |
| `Specific_Conductance` | Specific conductance assigned to the sampling activity. | USGS-reported/standardized conductance unit |
| `Turbidity_FNU` | Turbidity assigned to the sampling activity when represented in Formazin Nephelometric Units. | FNU |

These six variables form the primary environmental feature set used in the pesticide-environment audit.

---

### Environmental Source Columns

Each primary environmental variable has an associated `_source` column.

| Column | Meaning |
|---|---|
| `Discharge_cfs_source` | Source or matching method from which `Discharge_cfs` was obtained. |
| `Water_Temperature_C_source` | Source or matching method used for `Water_Temperature_C`. |
| `Dissolved_Oxygen_mg_L_source` | Source or matching method used for `Dissolved_Oxygen_mg_L`. |
| `pH_source` | Source or matching method used for `pH`. |
| `Specific_Conductance_source` | Source or matching method used for `Specific_Conductance`. |
| `Turbidity_FNU_source` | Source or matching method used for `Turbidity_FNU`. |

Depending on the environmental variable and data availability, a source can represent a strategy such as:

- a discrete environmental measurement associated with the same sampling activity,
- a temporally matched continuous observation,
- a daily value, or
- another permitted fallback source.

These fields are retained so that the final environmental value is not separated from information about how it was obtained.

For more detailed Method 2 provenance, including source station and other matching metadata, see:

`data/interim/method2_environmental_matches.parquet`

---

### Environmental Time-Gap Columns

Each primary environmental variable also has an associated `_gap_min` field.

| Column | Meaning | Unit |
|---|---|---|
| `Discharge_cfs_gap_min` | Time difference between the pesticide sampling timestamp and the discharge observation used for the environmental match. | minutes |
| `Water_Temperature_C_gap_min` | Time difference between pesticide sampling and the matched water-temperature observation. | minutes |
| `Dissolved_Oxygen_mg_L_gap_min` | Time difference between pesticide sampling and the matched dissolved-oxygen observation. | minutes |
| `pH_gap_min` | Time difference between pesticide sampling and the matched pH observation. | minutes |
| `Specific_Conductance_gap_min` | Time difference between pesticide sampling and the matched specific-conductance observation. | minutes |
| `Turbidity_FNU_gap_min` | Time difference between pesticide sampling and the matched FNU turbidity observation. | minutes |

A smaller time gap indicates that the selected environmental observation occurred closer to the pesticide sampling time.

For example:

```text
sample_dt_utc = 2020-05-10 10:00 UTC
matched DO observation = 2020-05-10 10:15 UTC

Dissolved_Oxygen_mg_L_gap_min = 15
```

A zero or near-zero gap can occur when the environmental observation was collected at or very close to the pesticide sampling time.

The `_gap_min` fields should be interpreted together with the corresponding `_source` fields because different source types can have different temporal resolutions.

---

## Discharge-Derived Hydrologic Features

In addition to the primary `Discharge_cfs` value associated with the sampling activity, the table contains several discharge-derived variables that describe antecedent and relative hydrologic conditions.

| Column | Meaning | Unit |
|---|---|---|
| `Q_daily_mean_cfs` | Daily mean stream discharge associated with the sampling date. | ft³/s |
| `Q_mean_prev3d_cfs` | Mean stream discharge over the preceding 3-day period. | ft³/s |
| `Q_mean_prev7d_cfs` | Mean stream discharge over the preceding 7-day period. | ft³/s |
| `Q_mean_prev30d_cfs` | Mean stream discharge over the preceding 30-day period. | ft³/s |
| `Q_change_1d_cfs` | Short-term change in discharge relative to the preceding daily condition, used to characterize rising or falling flow conditions. | ft³/s |
| `Q_percentile_site` | Relative position of the sampling-time discharge within the discharge distribution for that monitoring site. | Percentile / relative rank |

These variables provide hydrologic context beyond the instantaneous or matched `Discharge_cfs` value.

For example:

```text
Discharge_cfs
    → discharge associated with the sampling event

Q_daily_mean_cfs
    → average discharge for that day

Q_mean_prev3d_cfs
    → recent 3-day flow condition

Q_mean_prev7d_cfs
    → recent weekly flow condition

Q_mean_prev30d_cfs
    → longer antecedent flow condition

Q_change_1d_cfs
    → whether flow recently increased or decreased

Q_percentile_site
    → whether the flow was relatively low, normal, or high
       compared with conditions at the same site
```

These derived variables are useful for evaluating whether pesticide concentrations are associated with short-term flow changes, antecedent hydrologic conditions, or unusually high/low discharge.

---

## Additional Turbidity Representation

The dataset also retains turbidity represented in NTU where available.

| Column | Meaning | Unit |
|---|---|---|
| `Turbidity_NTU` | Turbidity measurement represented in Nephelometric Turbidity Units. | NTU |
| `Turbidity_NTU_source` | Source or matching method used to obtain the NTU turbidity value. | Text |
| `Turbidity_NTU_gap_min` | Temporal difference between pesticide sampling and the matched NTU turbidity observation. | minutes |

`Turbidity_NTU` and `Turbidity_FNU` should **not automatically be treated as interchangeable measurements** simply because both represent turbidity.

The unit and measurement method should be retained when interpreting or combining turbidity observations.

The primary environmental feature used in the current six-variable environmental feature set is:

`Turbidity_FNU`

while `Turbidity_NTU` is retained as additional information where available.

---

## Column Organization

The 34 columns in `sample_features.parquet` can be grouped as follows:

| Group | Columns | Purpose |
|---|---:|---|
| Sampling/activity identifiers | 5 | Identify the sampling activity, site, water year, and sampling time |
| Six primary environmental values | 6 | Environmental conditions associated with pesticide sampling |
| Primary environmental source fields | 6 | Record how each environmental value was obtained |
| Primary environmental time-gap fields | 6 | Record temporal distance between sampling and environmental observation |
| Derived discharge features | 6 | Characterize daily, antecedent, changing, and relative flow conditions |
| Additional NTU turbidity fields | 3 | Preserve additional turbidity information |

The environmental value, source, and temporal gap should generally be interpreted together.

For example:

```text
Water_Temperature_C
Water_Temperature_C_source
Water_Temperature_C_gap_min
```

together answer:

```text
What was the assigned water temperature?
            +
Where/how was it obtained?
            +
How far was that observation from the pesticide sampling time?
```

---

## Relationship to Detailed Provenance

`sample_features.parquet` should be considered the **consolidated activity-level feature table**, not the complete raw provenance table.

It retains the environmental values and important compact matching information needed for downstream analysis.

The more detailed Method 2 provenance is retained separately in:

`data/interim/method2_environmental_matches.parquet`

Therefore:

```text
method2_environmental_matches.parquet
        │
        │ detailed environmental
        │ matching/provenance evidence
        ▼
method2_activity_features.parquet
        │
        │ independent Method 2
        │ activity-level features
        ▼
Cross-method validation
        │
        │ Method 1 + Method 2
        ▼
sample_features.parquet
        │
        │ consolidated activity-level
        │ environmental features
        ▼
t2_pest_concs_enriched_v2.parquet
        │
        │ environmental features joined
        │ to pesticide-result records
        ▼
Final enriched pesticide dataset
```

Thus, `sample_features.parquet` represents the following statement:

> **For each sampling activity at a specific site, date, and time, multiple pesticide chemicals were analyzed from the same water sample; therefore, the environmental conditions measured or matched to that sampling event remained the same across those chemical records, while the pesticide concentrations differed by chemical.**

Detailed provenance questions should be answered using the corresponding interim provenance files.

---

# 4. Final Enriched Pesticide Dataset

## `t2_pest_concs_enriched_v2.parquet`

This is the principal **enriched pesticide-result dataset** produced by the current audit workflow.

It combines the processed pesticide concentration records with the environmental information associated with their sampling activities.

Conceptually:

```text
t2_pest_concs.parquet
        +
sample_features.parquet
        │
        ▼
t2_pest_concs_enriched_v2.parquet
```

The resulting dataset preserves the pesticide-result level while adding the environmental variables required for subsequent analyses.

The six primary environmental variables are:

- discharge,
- water temperature,
- dissolved oxygen,
- pH,
- specific conductance, and
- turbidity.

This file is used as the main enriched dataset for:

- analyte-level analysis,
- environmental relationship analysis,
- concentration-distribution analysis,
- spatial and temporal analysis,
- environmental-data coverage assessment, and
- subsequent pesticide concentration modeling.

Because multiple analytes can belong to the same sampling activity, environmental values associated with one activity can appear on multiple pesticide-result rows.

This is expected and does not indicate duplicate environmental retrieval.

The environmental values are matched at the activity level and then joined back to the corresponding pesticide-result records.

---

# 5. Analyte Inventory

## `analyte_list_84.csv`

This file contains the inventory of the **84 pesticide analytes** included in the audit.

The purpose of this file is to establish the complete analyte scope before performing analyte-specific analyses.

The project follows an **all-analyte audit strategy**. Therefore, analytes are not preselected based only on detection frequency, sample size, or apparent environmental relationships.

Instead, all 84 analytes are included in the audit, and any later exclusion must be supported by explicit evidence.

This file serves as the reference analyte list for subsequent comparison and analysis.

---

# 6. Full Analyte Comparison

## `analyte_comparison_full.csv`

This file contains the analyte-level comparison results generated for the complete set of pesticide analytes.

The table summarizes information needed to compare analytes across the major audit dimensions.

Depending on the available data for each analyte, the comparison includes information related to:

- number of concentration records,
- number of distinct sampling activities,
- monitoring-site coverage,
- temporal coverage,
- detections and nondetections,
- concentration characteristics,
- environmental-data availability, and
- other analyte-level audit metrics.

Its purpose is to provide a common summary table for comparing the 84 analytes without preselecting only frequently detected chemicals.

This table supports the project's requirement to audit **all analytes using the same general workflow**.

---

# 7. Analyte–Environment Relationships

## `analyte_env_relationships.csv`

This file contains the statistical analysis of relationships between pesticide concentrations and environmental variables.

The analysis evaluates analyte-specific relationships with environmental conditions such as:

- discharge,
- water temperature,
- dissolved oxygen,
- pH,
- specific conductance, and
- turbidity.

The table retains the statistical results needed to determine which analyte–environment relationships are supported by the available observations.

Because many analyte–environment combinations are tested, the workflow also considers multiple-testing correction rather than interpreting raw p-values alone.

In the current processed analysis, **726 analyte–environment relationships remain statistically significant at FDR-adjusted `q < 0.05`**.

This file is intended for audit and exploratory relationship assessment.

A statistically significant relationship should not automatically be interpreted as a causal environmental effect. The results identify statistical associations in the observed dataset and should be interpreted together with sample size, site coverage, temporal coverage, detection frequency, and environmental-data completeness.

---

# 8. Dataset Discrepancy Table

## `dataset_discrepancies.csv`

This file contains environmental discrepancies identified during comparison and validation of the augmented environmental data.

It records cases where the compared environmental values do not agree according to the audit criteria.

The table contains **969 non-discharge environmental discrepancies**.

These correspond to the non-discharge component of the complete cross-method exception table stored in:

```text
data/interim/environmental_match_exceptions.csv
```

The complete interim exception table contains:

```text
Discharge exceptions:                   145
Other environmental exceptions:         969
                                      -----
Total exceptions:                     1,114
```

The distinction is important:

- `data/interim/environmental_match_exceptions.csv` preserves the **complete Method 1 versus Method 2 exception record**, including discharge.
- `data/processed/dataset_discrepancies.csv` contains the **969 non-discharge discrepancies** retained for processed-dataset auditing.

This file therefore provides a processed audit record of environmental inconsistencies that required investigation.

---

# 9. Relationship Between the Main Processed Files

The major processed datasets represent different levels of the workflow and should not be treated as duplicates.

```text
Original USGS pesticide data
            │
            ▼
  t2_pest_concs.parquet
  [pesticide-result level]
            │
            │ identify distinct
            │ sampling activities
            ▼
   activity_master.parquet
     [activity level]
            │
            │ environmental
            │ extraction/matching
            ▼
    data/interim/
 Method 1 + Method 2
            │
            │ validation and
            │ feature consolidation
            ▼
  sample_features.parquet
     [activity level]
            │
            │ join environmental
            │ features back to
            │ pesticide results
            ▼
t2_pest_concs_enriched_v2.parquet
 [enriched pesticide-result level]
            │
            ├───────────────────────┐
            │                       │
            ▼                       ▼
analyte_comparison_full.csv   analyte_env_relationships.csv
            │
            │
            ▼
   All-analyte audit results
```

The important distinction is:

| File | Data Level | Main Purpose |
|---|---|---|
| `t2_pest_concs.parquet` | Pesticide-result level | Processed pesticide concentration records |
| `activity_master.parquet` | Sampling-activity level | Unique sampling events used for environmental matching |
| `sample_features.parquet` | Sampling-activity level | Consolidated environmental variables |
| `t2_pest_concs_enriched_v2.parquet` | Pesticide-result level | Final pesticide records enriched with environmental variables |
| `analyte_list_84.csv` | Analyte level | Defines the complete 84-analyte scope |
| `analyte_comparison_full.csv` | Analyte-summary level | Compares analytes across audit dimensions |
| `analyte_env_relationships.csv` | Analyte–environment level | Statistical relationships between concentration and environmental variables |
| `dataset_discrepancies.csv` | Exception level | Non-discharge environmental discrepancies identified during validation |

---

# 10. Relationship to `data/interim/`

The `processed/` and `interim/` directories serve different purposes.

## `data/interim/`

Contains evidence supporting **how the environmental data were obtained and validated**, including:

- independent Method 1 results,
- independent Method 2 results,
- detailed Method 2 provenance,
- cross-method exceptions,
- retrieval logs,
- feature coverage,
- source summaries,
- time-gap summaries, and
- provenance QC.

## `data/processed/`

Contains the datasets needed for the **main pesticide audit and subsequent analyses**, including:

- processed pesticide records,
- activity master,
- consolidated environmental features,
- final enriched pesticide records,
- analyte inventory,
- analyte comparison results,
- environmental relationship results, and
- processed discrepancy records.

Therefore:

```text
data/interim/
     │
     │ evidence, validation,
     │ provenance and QC
     ▼
data/processed/
     │
     │ analysis-ready datasets
     ▼
Audit analyses and reports
```

The interim files should be retained because they provide the audit trail supporting the processed datasets.

---

# 11. Recommended Canonical Files

For reproducibility, the following files should be treated as the canonical processed datasets for their respective purposes:

| Purpose | Canonical File |
|---|---|
| Processed pesticide concentrations | `t2_pest_concs.parquet` |
| Unique sampling activities | `activity_master.parquet` |
| Consolidated activity-level environmental features | `sample_features.parquet` |
| Final enriched pesticide dataset | `t2_pest_concs_enriched_v2.parquet` |
| Complete analyte inventory | `analyte_list_84.csv` |
| All-analyte comparison | `analyte_comparison_full.csv` |
| Analyte–environment statistical analysis | `analyte_env_relationships.csv` |
| Processed environmental discrepancy audit | `dataset_discrepancies.csv` |

Large CSV exports of Parquet datasets should generally be treated as convenience exports rather than separate canonical datasets.

---

# 12. Summary

The `data/processed/` directory represents the main transition from environmental data extraction and validation to the pesticide data-audit analysis.

In simplified form:

```text
Pesticide concentration records
        +
Distinct sampling activities
        +
Validated environmental features
        │
        ▼
Final enriched pesticide dataset
        │
        ├── Analyte inventory
        ├── Analyte comparison
        ├── Environmental relationships
        └── Discrepancy assessment
```

Together with the provenance and QC information retained in `data/interim/`, these files provide the processed data foundation for the complete pesticide concentration and environmental data audit.