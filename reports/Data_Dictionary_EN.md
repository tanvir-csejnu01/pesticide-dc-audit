# Data Dictionary

## 1. Dataset Structure

The processed pesticide dataset contains **955,728 chemical-result records**, representing **84 analytes**, **81 published analysis sites**, and water years **2013–2022**.

The main processed files are:

```text
data/processed/
├── t2_pest_concs.parquet
├── activity_master.parquet
├── sample_features.parquet
├── t2_pest_concs_enriched_v2.parquet
├── analyte_list_84.csv
├── analyte_comparison_full.csv
├── analyte_env_relationships.csv
└── dataset_discrepancies.csv
```

### Observation Levels

The datasets operate at different observation levels:

| Dataset | Observation Unit |
|---|---|
| `t2_pest_concs.parquet` | One chemical result |
| `activity_master.parquet` | One unique sampling activity |
| `sample_features.parquet` | One environmental feature set per sampling activity |
| `t2_pest_concs_enriched_v2.parquet` | One chemical result with activity-level environmental features |
| `analyte_list_84.csv` | One analyte |
| `analyte_comparison_full.csv` | One analyte summary |
| `analyte_env_relationships.csv` | One analyte–environment relationship |
| `dataset_discrepancies.csv` | One identified environmental discrepancy |

A sampling activity (`Activity_ActivityIdentifier`) represents one water sample collected at a particular site, date, and time.

Multiple chemicals can be analyzed from the same water sample. Therefore, chemical concentrations differ by analyte, while the environmental conditions associated with that sampling activity are shared across its chemical-result records.

---

# 2. `t2_pest_concs.parquet`

This is the processed base pesticide concentration table.

One row represents:

```text
one sampling activity × one analyte result
```

## Column Dictionary

| Field | Type / Unit | Definition |
|---|---|---|
| `Pesticide_Site` | text | Combined analyte/site identifier used in the base release |
| `Pesticide_Name` | text | Pesticide analyte name |
| `Site_Abb` | text | Published analysis-site abbreviation |
| `USGSpcode` | text | 5-digit USGS parameter code for the analyte |
| `Water_Year` | year | USGS water year; October 1 through September 30 |
| `Activity_StartDate` | YYYY-MM-DD | Local date of sample collection |
| `Activity_StartTime` | HH:MM:SS | Local time of sample collection |
| `Activity_StartTimeZone` | text | Time-zone abbreviation recorded for the activity |
| `Activity_MediaSubdivision` | text | Sample medium; surface water in this release |
| `Activity_TypeCode` | text | Sampling-activity type, including information relevant to field replicates |
| `LabInfo_Name` | text | Laboratory that analyzed the sample |
| `Activity_ActivityIdentifier` | text | Unique sampling-activity identifier and environmental join key |
| `Result_ResultDetectionCondition` | text | Detection condition; `"Not Detected"` identifies nondetections |
| `Result_Value_ug_L` | µg/L | Detected concentration; for nondetections, contains the reported laboratory reporting-level value |

No zero or half-reporting-limit substitution is applied to the original pesticide-result field.

---

# 3. `activity_master.parquet`

This table contains the **12,896 unique pesticide sampling activities** used for environmental matching.

Its purpose is to reduce repeated chemical-result rows to unique field sampling events before environmental data are retrieved or matched.

Typical identifying fields include:

| Field | Definition |
|---|---|
| `activity_id` | Unique sampling-activity identifier |
| `Location_Identifier` | USGS monitoring-location identifier |
| `Site_Abb` | Published site abbreviation |
| `Water_Year` | Water year of the activity |
| `sample_dt_utc` | Sampling date/time converted to UTC |

Conceptually:

```text
Many chemical-result rows
        ↓
One unique sampling activity
        ↓
Environmental matching
```

---

# 4. `sample_features.parquet`

This is the consolidated **activity-level environmental feature table**.

One row represents one sampling activity.

## 4.1 Activity Identification

| Field | Definition |
|---|---|
| `activity_id` | Unique sampling-activity identifier |
| `Location_Identifier` | USGS monitoring-location identifier |
| `Site_Abb` | Published analysis-site abbreviation |
| `Water_Year` | Water year |
| `sample_dt_utc` | Sampling timestamp in UTC |

---

## 4.2 Primary Environmental Variables

| Field | Unit | Definition |
|---|---|---|
| `Discharge_cfs` | ft³/s | Discharge assigned to the sampling activity |
| `Water_Temperature_C` | °C | Water temperature assigned to the activity |
| `Dissolved_Oxygen_mg_L` | mg/L | Dissolved oxygen assigned to the activity |
| `pH` | standard units | pH assigned to the activity |
| `Specific_Conductance` | µS/cm | Specific conductance assigned to the activity |
| `Turbidity_FNU` | FNU | Turbidity represented in Formazin Nephelometric Units |

Each environmental value is associated with a sampling event rather than an individual pesticide analyte.

Therefore, different chemicals measured from the same sampling activity receive the same environmental feature values when the activity-level features are joined back to the pesticide-result table.

---

## 4.3 Source and Time-Gap Fields

Each primary environmental variable has corresponding source and time-gap fields.

| Field Pattern | Definition |
|---|---|
| `<variable>_source` | Source or matching method used to obtain the environmental value |
| `<variable>_gap_min` | Time difference, in minutes, between the sampling activity and matched environmental observation |

Examples include:

```text
Discharge_cfs_source
Discharge_cfs_gap_min

Water_Temperature_C_source
Water_Temperature_C_gap_min

Dissolved_Oxygen_mg_L_source
Dissolved_Oxygen_mg_L_gap_min

pH_source
pH_gap_min

Specific_Conductance_source
Specific_Conductance_gap_min

Turbidity_FNU_source
Turbidity_FNU_gap_min
```

Possible matching sources include:

| Source | Meaning |
|---|---|
| `discrete_same_activity` | Environmental measurement associated with the same sampling activity |
| `discrete_time_match` | Nearby discrete environmental observation |
| `continuous_nearest` | Nearest permitted continuous-sensor observation |
| `daily_mean_same_sample_date` | Same-date daily mean used as a discharge fallback |

Detailed matching and provenance information is retained separately in `data/interim/`.

---

## 4.4 Derived Discharge Features

| Field | Unit | Definition |
|---|---|---|
| `Q_daily_mean_cfs` | ft³/s | Daily mean discharge for the sampling date |
| `Q_mean_prev3d_cfs` | ft³/s | Mean discharge over the preceding 3-day period |
| `Q_mean_prev7d_cfs` | ft³/s | Mean discharge over the preceding 7-day period |
| `Q_mean_prev30d_cfs` | ft³/s | Mean discharge over the preceding 30-day period |
| `Q_change_1d_cfs` | ft³/s | Short-term one-day change in discharge |
| `Q_percentile_site` | relative rank | Position of the sampling-date discharge within the site's discharge distribution |

These variables describe recent and antecedent hydrologic conditions around the pesticide sampling event.

---

## 4.5 Additional Turbidity Fields

| Field | Unit | Definition |
|---|---|---|
| `Turbidity_NTU` | NTU | Turbidity represented in Nephelometric Turbidity Units |
| `Turbidity_NTU_source` | text | Source/matching method for the NTU value |
| `Turbidity_NTU_gap_min` | minutes | Time gap between sampling and matched NTU observation |

`Turbidity_NTU` and `Turbidity_FNU` are retained separately and should not automatically be treated as interchangeable measurements.

---

# 5. `t2_pest_concs_enriched_v2.parquet`

This is the final enriched pesticide-result dataset.

It combines:

```text
t2_pest_concs.parquet
        +
activity-level environmental features
        ↓
t2_pest_concs_enriched_v2.parquet
```

The six primary appended environmental variables are:

| Field | Unit |
|---|---|
| `Discharge_cfs` | ft³/s |
| `Water_Temperature_C` | °C |
| `Dissolved_Oxygen_mg_L` | mg/L |
| `pH` | standard units |
| `Specific_Conductance` | µS/cm |
| `Turbidity_FNU` | FNU |

Because multiple analytes can be measured from one sampling activity, the same environmental values can appear on multiple chemical-result rows.

For example:

```text
Same activity/date/time

Atrazine      → concentration A ─┐
Simazine      → concentration B  ├─ same environmental conditions
Imidacloprid  → concentration C  ┘
```

This repetition is expected and does not represent duplicate environmental retrieval.

---

# 6. `analyte_list_84.csv`

This table contains one row for each of the 84 analytes.

| Field | Definition |
|---|---|
| `Pesticide_Name` | Analyte name |
| `USGSpcode` | USGS analyte parameter code |
| `n_chemical_result_rows` | Number of chemical-result records |
| `n_sampling_activities` | Number of distinct sampling activities |
| `n_sites_with_measurement` | Number of sites where the analyte was measured |
| `n_detected_rows` | Number of detected observations |
| `detection_pct` | Percentage of observations detected |
| `first_date` | First observation date |
| `last_date` | Last observation date |
| `reporting_level_min_ugL` | Minimum nondetection reporting level |
| `reporting_level_max_ugL` | Maximum nondetection reporting level |
| `reporting_level_changed_over_time` | Indicator that reporting level varies over time |
| `detected_conc_median_ugL` | Median concentration among detections |
| `detected_conc_max_ugL` | Maximum detected concentration |
| `pct_rows_with_5_core_env_vars` | Percentage with the five higher-coverage environmental variables |
| `pct_rows_with_all_6_env_vars` | Percentage with all six environmental variables |

---

# 7. `analyte_comparison_full.csv`

This table contains one comparative summary row for each analyte.

It supports the all-84-analyte audit and includes metrics related to:

- record and activity counts;
- site and temporal coverage;
- detections and nondetections;
- reporting levels;
- environmental matching;
- detected-concentration distributions; and
- spatial-temporal patterns.

Detailed interpretation is provided in:

```text
reports/comparative_analyze_analysis_eng.md
```

---

# 8. `analyte_env_relationships.csv`

This table contains analyte-specific statistical relationships with the six environmental variables.

Two relationship types are evaluated:

```text
environmental variable ↔ detection status

environmental variable ↔ log10 concentration among detections
```

Typical fields describe:

| Information | Meaning |
|---|---|
| Analyte | Chemical being evaluated |
| Environmental variable | Discharge, temperature, DO, pH, conductance, or turbidity |
| Relationship type | Detection or detected-concentration relationship |
| `n` | Number of observations used |
| Spearman coefficient | Direction and magnitude of monotonic association |
| p-value | Unadjusted statistical significance |
| q-value | FDR-adjusted statistical significance |

The current analysis uses:

```text
q < 0.05
```

as the multiple-testing-adjusted significance criterion.

---

# 9. `dataset_discrepancies.csv`

This table contains the **969 non-discharge environmental discrepancies** identified during cross-method validation.

The complete exception record, including discharge exceptions, is retained in:

```text
data/interim/environmental_match_exceptions.csv
```

Therefore:

```text
data/processed/dataset_discrepancies.csv
        = processed non-discharge discrepancy record

data/interim/environmental_match_exceptions.csv
        = complete Method 1 vs. Method 2 exception record
```

---

# 10. Detailed Environmental Provenance

Detailed environmental provenance is stored in the interim directory rather than the processed directory.

The main Method 2 provenance table is:

```text
data/interim/method2_environmental_matches.parquet
```

It contains one row per:

```text
sampling activity × environmental variable
```

for a total expected structure of:

```text
12,896 activities × 6 variables
= 77,376 activity-variable records
```

The provenance table is used to document information such as:

| Field | Purpose |
|---|---|
| `source_station_id` | USGS station associated with the environmental value |
| `source_parameter_code` | USGS environmental parameter code |
| `original_value` | Environmental value retained from the source |
| `matching_method` | Method used to associate the environmental observation with the sampling activity |
| `time_offset_minutes` | Temporal offset where available |
| `allowed_window_minutes` | Permitted matching window |
| `aggregation_interval` | Instantaneous or daily aggregation information |
| `missing_reason` | Reason a value could not be matched, where available |

Some provenance fields were not retained by the original environmental extraction and therefore remain unavailable. These limitations are documented in the interim QC files and `UNRESOLVED_ISSUES.md`.

---

# 11. Station Identity Note

The analysis contains:

```text
81 published analysis sites
```

while environmental retrieval can involve:

```text
82 physical monitoring stations
```

The difference is associated with the published `Illinois R, IL` site, whose historical environmental retrieval involves two physical USGS stations:

```text
USGS-05586100 — Illinois River at Valley City, IL
USGS-05586300 — Illinois River at Florence, IL
```

This station-history issue is retained in the environmental audit documentation and should not be interpreted as an additional published pesticide analysis site.

---

# 12. Important Data-Use Notes

- `Activity_ActivityIdentifier` / `activity_id` is the key link between pesticide sampling activities and environmental features.
- Multiple chemical results can belong to the same sampling activity.
- Environmental variables are matched at the sampling-activity level, not independently for every analyte row.
- Original pesticide-result columns are retained without environmental-data imputation.
- Missing environmental values are not filled by interpolation or carry-forward.
- Nondetected pesticide results are not automatically replaced with zero or half the reporting limit.
- FNU and NTU turbidity values are retained as separate measurements.
- Detailed environmental provenance and QC information is stored in `data/interim/`.