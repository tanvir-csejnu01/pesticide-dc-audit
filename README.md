# Pesticide Data Companion — National 84-Analyte Audit and Environmental Augmentation

## 1. Project Overview

This repository contains the Phase-1 audit and environmental augmentation of the national USGS riverine pesticide dataset.

The main purpose of this phase is to understand the complete dataset before selecting data for predictive modeling.

Instead of selecting a few pesticides in advance, all **84 analytes** were evaluated using the same workflow.

The project focuses on:

- organizing the national pesticide dataset;
- identifying unique sampling activities;
- adding environmental conditions to pesticide observations;
- validating the environmental matching using two independent methods;
- comparing all 84 analytes; and
- preparing the evidence needed for later research dataset selection.

No final modeling analyte or modeling strategy has been selected in Phase 1.

---

## 2. Data Scope

The working national dataset contains:

| Item | Value |
|---|---:|
| Chemical-result records | 955,728 |
| Pesticide analytes | 84 |
| Published analysis sites | 81 |
| Physical monitoring stations | 82 |
| Unique sampling activities | 12,896 |
| Water years | 2013–2022 |

A chemical-result record is not the same as an independent water sample.

One sampling activity can contain results for many pesticide analytes. These analytes share the environmental conditions measured for that sampling event.

Therefore, environmental matching is performed at the **sampling-activity level**.

---

## 3. What Was Done

### Step 1 — Organize the Pesticide Dataset

The complete pesticide archive was checked and organized without removing analytes or chemical-result records.

The 955,728 chemical-result records were linked to **12,896 unique sampling activities**.

### Step 2 — Add Environmental Variables

Six environmental variables were matched to the sampling activities:

- discharge;
- water temperature;
- dissolved oxygen;
- pH;
- specific conductance; and
- turbidity.

Five variables have approximately **98–99% activity-level coverage**.

Turbidity has lower coverage (**26.3%**) because suitable turbidity observations are unavailable for many site/time combinations.

### Step 3 — Compare Two Environmental Methods

Two independent environmental extraction methods were retained and compared.

Their results show **98.75% cell-level agreement**.

Differences between the methods were recorded for further investigation rather than being silently removed or overwritten.

The major non-discharge discrepancy blocks were linked to documented USGS retrieval timeouts in the Method 2 extraction.

### Step 4 — Compare All 84 Analytes

The same analysis was applied to every analyte.

The comparison includes:

- number of records and sampling activities;
- site and time coverage;
- detection and nondetection patterns;
- reporting-level changes;
- environmental-data availability;
- concentration distributions;
- spatial-temporal patterns; and
- relationships with environmental conditions.

This provides a common basis for comparing the suitability of different analytes for later research and modeling.

### Step 5 — Validate the Dataset

Automated checks were performed on the complete dataset.

Selected environmental discrepancies were also checked against original USGS source records.

Unresolved cases are retained and documented rather than automatically corrected.

---

## 4. Main Phase-1 Findings

The audit provides several important findings for the next stage of the research.

### Dataset Structure

The national dataset is large, but the 955,728 chemical-result records come from only **12,896 independent sampling activities**.

This distinction is important because environmental conditions belong to sampling activities rather than individual chemical-result rows.

### Environmental Data

Five environmental variables have high coverage and can support further analysis.

Turbidity is much less complete and will require special consideration in later modeling.

### Analyte Differences

The 84 analytes do not have identical data characteristics.

They differ in:

- number of observations;
- site and temporal coverage;
- detection frequency;
- reporting limits;
- concentration distributions; and
- relationships with environmental conditions.

Therefore, the final research dataset should be selected using these measured characteristics rather than choosing analytes only from the earlier pilot study.

---

## 5. Main Research Gain

Before this audit, the project had a large national pesticide dataset but limited evidence for deciding which parts of it were suitable for modeling.

After Phase 1, we now know:

```text
What pesticide data are available
        ↓
How the sampling activities are organized
        ↓
Which environmental variables can be connected
        ↓
How complete the environmental data are
        ↓
How consistent the environmental extraction is
        ↓
How the 84 analytes differ
        ↓
What limitations must be considered before modeling
```

This provides the evidence needed for the next research-dataset selection step.

The later modeling strategy can therefore be evaluated as:

- one model using many/all analytes;
- separate models for analyte groups; or
- models for selected analytes with suitable data.

---

## 6. Repository Structure

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
│
├── reports/
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
│   ├── raw/
│   ├── interim/
│   └── processed/
│
└── outputs/
    ├── tables/
    └── checks/
```

A detailed description of each directory and script is provided in:

```text
PROJECT_STRUCTURE.md
```

---

## 7. Main Data Products

The most important processed datasets are:

| File | Purpose |
|---|---|
| `t2_pest_concs.parquet` | Base national pesticide concentration dataset |
| `activity_master.parquet` | One row per unique sampling activity |
| `sample_features.parquet` | Activity-level environmental feature table |
| `t2_pest_concs_enriched_v2.parquet` | Final pesticide dataset with environmental variables |
| `analyte_list_84.csv` | Inventory of all 84 analytes |
| `analyte_comparison_full.csv` | Comparative summary of all 84 analytes |
| `analyte_env_relationships.csv` | Analyte-environment relationship results |
| `dataset_discrepancies.csv` | Non-discharge differences identified between the two environmental methods |

The main Phase-1 research dataset is:

```text
data/processed/t2_pest_concs_enriched_v2.parquet
```

Method-specific environmental results and provenance are retained separately in:

```text
data/interim/
```

---

## 8. Main Reports

Detailed documentation is divided among the following reports:

| Report | Purpose |
|---|---|
| `National_Data_Audit_EN.md` | Full national dataset audit and validation |
| `Data_Dictionary_EN.md` | Definitions of the main datasets and variables |
| `Pilot_Connection_Report_EN.md` | Connection between the earlier pilot and national analysis |
| `Environmental_Augmentation_Methods_EN.md` | Environmental extraction and matching methods |
| `Comparative_Analyte_Analysis_EN.md` | Comparison of all 84 analytes |
| `Validation_Summary_EN.md` | Completed and pending validation work |

This README provides only the overall project summary. Technical details are kept in the individual reports to avoid duplication.

---

## 9. Data Companion Window

The full pesticide archive covers water years **2013–2022**.

For later comparison with Data Companion (DC) information, the current complete-month overlap period is:

```text
January 1, 2013 – August 31, 2021
```

Records outside this period remain in the national dataset.

The DC window is used as a separate analysis period rather than removing observations from the full archive.

---

## 10. Reproducibility and Validation

The repository keeps the major processing stages separate:

```text
Raw data
    ↓
Interim processing
    ↓
Processed datasets
    ↓
Analysis outputs
    ↓
Validation and reports
```

Important methodological settings are stored in:

```text
config/
```

Validation results are stored in:

```text
outputs/checks/
```

Known limitations and unresolved cases are tracked in:

```text
UNRESOLVED_ISSUES.md
```

This structure allows the original data, environmental augmentation, comparison results, and validation evidence to remain traceable.

---

## 11. Current Status

| Component | Status |
|---|---|
| National 84-analyte dataset audit | Complete |
| Sampling-activity organization | Complete |
| Six-variable environmental augmentation | Complete |
| Method 1 vs. Method 2 comparison | Complete |
| All-84-analyte comparative analysis | Complete |
| Automated validation | Complete |
| Manual source verification | Partially complete |
| Environmental provenance | Partially complete |
| DC/NHM-PRMS hydrologic integration | Pending |
| National basin/HUC12 extension | Pending |
| Final research-dataset selection | Pending |
| Predictive modeling | Not started in Phase 1 |

---

## 12. Next Step

The next stage is to connect the audited pesticide observations with the required **DC/NHM-PRMS hydrologic information** and evaluate the appropriate research dataset for modeling.

The Phase-1 results will then be used to decide whether the available evidence supports:

```text
All analytes
      OR
Defined analyte groups
      OR
Selected analytes
```

The final choice should be based on data availability, detection characteristics, environmental coverage, temporal and spatial coverage, and the requirements of the planned predictive model.