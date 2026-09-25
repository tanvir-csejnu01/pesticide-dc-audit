# Phase-1 Repository Structure

This repository contains the data, scripts, reports, configuration files, and validation outputs used for the Phase-1 national pesticide data audit and environmental augmentation.

The repository is organized so that the original data, intermediate processing, final datasets, analysis outputs, and documentation remain separate and traceable.

---

## 1. Overall Project Structure

```text
pesticide-dc-audit/
│
├── README.md
├── PROJECT_STRUCTURE.md
├── CHECKSUMS.txt
├── UNRESOLVED_ISSUES.md
├── requirements.txt
│
├── config/
│   ├── README.md
│   ├── audit_config.yaml
│   └── environmental_matching_config.yaml
│
├── reports/
│   ├── National_Data_Audit_EN.md
│   ├── Data_Dictionary_EN.md
│   ├── Pilot_Connection_Report_EN.md
│   ├── Environmental_Augmentation_Methods_EN.md
│   ├── Comparative_Analyte_Analysis_EN.md
│   └── Validation_Summary_EN.md
│
├── scripts/
│   ├── 01_download_sources.py
│   ├── 02_clean_observations.py
│   ├── 03_match_environment.py
│   ├── 04_pilot_basins.py
│   ├── 05_make_figures.py
│   ├── 06_environment_method1_independent_extraction.py
│   ├── 07_build_environmental_matches_with_provenance.py
│   ├── 08_build_analyte_inventory.py
│   ├── 09_build_activity_master.py
│   ├── 10_cross_implementation_audit.py
│   ├── 11_compare_all_analytes.py
│   ├── 12_build_environmental_matches_method2_full_provenance.py
│   ├── 13_build_interim_activity_features.py
│   └── 14_environment_method2_independent_extraction.py
│
├── data/
│   │
│   ├── raw/
│   │   ├── README.md
│   │   └── Riverine_Pesticides.xml
│   │
│   ├── interim/
│   │   ├── README.md
│   │   ├── method1_activity_features.parquet
│   │   ├── method2_activity_features.parquet
│   │   ├── method2_environmental_matches.parquet
│   │   ├── environmental_match_exceptions.csv
│   │   ├── method1_raw_qc/
│   │   └── method2_raw_qc/
│   │
│   └── processed/
│       ├── t2_pest_concs.parquet
│       ├── t2_pest_concs_enriched_v2.parquet
│       ├── sample_features.parquet
│       ├── activity_master.parquet
│       ├── analyte_list_84.csv
│       ├── analyte_comparison_full.csv
│       ├── analyte_env_relationships.csv
│       ├── dataset_discrepancies.csv
│       └── README_dataset_final_csv.md
│
└── outputs/
    │
    ├── tables/
    │   ├── README.md
    │   ├── source_scope_summary.csv
    │   ├── censoring_summary.csv
    │   ├── environmental_coverage_summary.csv
    │   ├── method_comparison_summary.csv
    │   └── dc_window_summary.csv
    │
    └── checks/
        ├── README.md
        ├── automated_checks.csv
        └── manual_spot_checks.csv
```

---

## 2. Configuration

The `config/` directory stores the main settings used by the audit and environmental matching workflows.

```text
config/
├── README.md
├── audit_config.yaml
└── environmental_matching_config.yaml
```

### `audit_config.yaml`

Stores project-level audit settings such as:

- expected dataset counts;
- DC analysis window; and
- statistical-analysis settings.

### `environmental_matching_config.yaml`

Stores the environmental matching rules, including:

- environmental parameter codes;
- matching windows;
- matching hierarchy; and
- related extraction settings.

---

## 3. Reports

The `reports/` directory contains the main documentation for Phase 1.

| Report | Purpose |
|---|---|
| `National_Data_Audit_EN.md` | Documents the full 84-analyte dataset audit, coverage, environmental matching, and validation results. |
| `Data_Dictionary_EN.md` | Defines the important fields used in the raw, activity-level, environmental, and processed datasets. |
| `Pilot_Connection_Report_EN.md` | Summarizes the earlier two-analyte pilot and its connection to the current national analysis. |
| `Environmental_Augmentation_Methods_EN.md` | Documents Method 1 and Method 2 environmental extraction and matching procedures. |
| `Comparative_Analyte_Analysis_EN.md` | Summarizes the common comparison applied to all 84 analytes. |
| `Validation_Summary_EN.md` | Summarizes completed, partial, and pending validation work. |

---

## 4. Scripts

The `scripts/` directory contains the data preparation, environmental augmentation, audit, and comparative-analysis workflows.

### Pilot Workflow

```text
01_download_sources.py
02_clean_observations.py
03_match_environment.py
04_pilot_basins.py
05_make_figures.py
```

These scripts belong to the earlier pilot workflow.

They cover source preparation, observation cleaning, environmental matching, basin connections, and pilot figures.

### Method 1 Environmental Augmentation

```text
06_environment_method1_independent_extraction.py
07_build_environmental_matches_with_provenance.py
```

`06_environment_method1_independent_extraction.py` performs the independent Method 1 environmental extraction.

`07_build_environmental_matches_with_provenance.py` organizes the environmental matches and available provenance information for auditing.

### National Dataset Audit

```text
08_build_analyte_inventory.py
09_build_activity_master.py
10_cross_implementation_audit.py
11_compare_all_analytes.py
```

These scripts perform the main national audit:

- `08_build_analyte_inventory.py` — builds the 84-analyte inventory.
- `09_build_activity_master.py` — creates one record per unique sampling activity.
- `10_cross_implementation_audit.py` — compares Method 1 and Method 2.
- `11_compare_all_analytes.py` — applies the common comparative analysis to all 84 analytes.

### Method 2 and Interim Comparison

```text
12_build_environmental_matches_method2_full_provenance.py
13_build_interim_activity_features.py
14_environment_method2_independent_extraction.py
```

- `14_environment_method2_independent_extraction.py` contains the independent Method 2 environmental extraction workflow.
- `12_build_environmental_matches_method2_full_provenance.py` provides the Method 2 full-provenance workflow.
- `13_build_interim_activity_features.py` prepares comparable activity-level Method 1 and Method 2 tables and generates the environmental exception log.

---

## 5. Data

The `data/` directory is divided into three levels:

```text
raw
  ↓
interim
  ↓
processed
```

### 5.1 Raw Data

```text
data/raw/
├── README.md
└── Riverine_Pesticides.xml
```

The raw directory stores source data and source metadata.

Large raw files that are not committed to the repository are documented in:

```text
data/raw/README.md
```

This includes the Method 2 source/output file:

```text
dataset_2013_2022_G.csv
```

when maintained outside version control.

---

### 5.2 Interim Data

```text
data/interim/
├── README.md
├── method1_activity_features.parquet
├── method2_activity_features.parquet
├── method2_environmental_matches.parquet
├── environmental_match_exceptions.csv
├── method1_raw_qc/
└── method2_raw_qc/
```

The interim directory stores intermediate environmental datasets used before the final dataset is produced.

| File | Purpose |
|---|---|
| `method1_activity_features.parquet` | Activity-level environmental features produced by Method 1. |
| `method2_activity_features.parquet` | Activity-level environmental features produced by Method 2. |
| `method2_environmental_matches.parquet` | Long-format Method 2 environmental matching and available provenance information. |
| `environmental_match_exceptions.csv` | Activity-variable cases where Method 1 and Method 2 differ. |
| `method1_raw_qc/` | QC and extraction records from Method 1. |
| `method2_raw_qc/` | QC, extraction, and retrieval records from Method 2. |

These files preserve the two methods independently so their agreement and differences remain auditable.

---

### 5.3 Processed Data

```text
data/processed/
├── t2_pest_concs.parquet
├── t2_pest_concs_enriched_v2.parquet
├── sample_features.parquet
├── activity_master.parquet
├── analyte_list_84.csv
├── analyte_comparison_full.csv
├── analyte_env_relationships.csv
├── dataset_discrepancies.csv
└── README_dataset_final_csv.md
```

| File | Purpose |
|---|---|
| `t2_pest_concs.parquet` | Original pesticide concentration table used as the base dataset. |
| `t2_pest_concs_enriched_v2.parquet` | Final pesticide dataset augmented with six environmental variables. |
| `sample_features.parquet` | Combined activity-level environmental feature table. |
| `activity_master.parquet` | Master table with one row per unique sampling activity. |
| `analyte_list_84.csv` | Inventory of all 84 analytes. |
| `analyte_comparison_full.csv` | Comparative summary for all 84 analytes. |
| `analyte_env_relationships.csv` | Environmental relationship results for all analytes. |
| `dataset_discrepancies.csv` | Detailed Method 1 vs. Method 2 discrepancy records used in the audit. |
| `README_dataset_final_csv.md` | Explains the redundant CSV export and how to regenerate it if required. |

The main Phase-1 research dataset is:

```text
data/processed/t2_pest_concs_enriched_v2.parquet
```

---

## 6. Outputs

The `outputs/` directory stores summary tables and validation results generated from the audit.

### 6.1 Tables

```text
outputs/tables/
├── README.md
├── source_scope_summary.csv
├── censoring_summary.csv
├── environmental_coverage_summary.csv
├── method_comparison_summary.csv
└── dc_window_summary.csv
```

| File | Purpose |
|---|---|
| `source_scope_summary.csv` | Summary of dataset size, analytes, sites, activities, and study period. |
| `censoring_summary.csv` | Detection, nondetection, and reporting-level summary. |
| `environmental_coverage_summary.csv` | Coverage of the six environmental variables. |
| `method_comparison_summary.csv` | Summary of agreement and discrepancies between the two environmental methods. |
| `dc_window_summary.csv` | Summary of observations within the required DC analysis period. |

### 6.2 Validation Checks

```text
outputs/checks/
├── README.md
├── automated_checks.csv
└── manual_spot_checks.csv
```

| File | Purpose |
|---|---|
| `automated_checks.csv` | Automated integrity and consistency checks for the complete dataset. |
| `manual_spot_checks.csv` | Selected environmental records manually checked against original USGS source data. |

---

## 7. Overall Workflow

The repository follows this general workflow:

```text
Original USGS pesticide data
            │
            ▼
    Sampling activities
            │
            ├─────────────────────┐
            ▼                     ▼
 Environmental Method 1    Environmental Method 2
      Scripts 06–07             Script 14
            │                     │
            └──────────┬──────────┘
                       ▼
             Activity-level comparison
                    Script 13
                       │
                       ▼
              National data audit
                 Scripts 08–10
                       │
                       ▼
            All-84-analyte analysis
                    Script 11
                       │
                       ▼
        Final enriched research dataset
                       │
                       ▼
      Tables + validation + reports
```

The two environmental methods are kept separate until comparison so that differences can be identified and audited.

---

## 8. Main Phase-1 Outputs

The Phase-1 repository provides four main results:

1. **Audited pesticide dataset**  
   All 84 analytes and the original chemical-result records are retained.

2. **Activity-level environmental dataset**  
   Six environmental variables are connected to the pesticide sampling activities where data are available.

3. **Cross-method validation**  
   Two independent environmental extraction methods are compared to identify agreement and discrepancies.

4. **All-analyte comparison**  
   All 84 analytes are evaluated using the same data-coverage, detection, concentration, and environmental criteria.

Together, these outputs provide the data foundation for selecting the final research dataset and modeling scope in the next stage.