# Raw Data

This directory documents the original data sources used in the project.
The original source information is kept separate from the processed and
augmented datasets so that the analysis can be traced back to the source data.

## Data Source 1: USGS Riverine Pesticide Dataset

The primary pesticide data were obtained from a USGS national assessment of
pesticides in U.S. rivers and streams (Breitmeyer et al., 2026):

https://doi.org/10.5066/P1NDXVYD

The data release covers 84 pesticide-related analytes at 81 published analysis
sites across the conterminous United States. The study period covers water years
2013–2022, corresponding to October 1, 2012 through September 30, 2022.

A USGS water year runs from October 1 through September 30. Therefore, water
year 2013 begins on October 1, 2012 and ends on September 30, 2013.

The USGS study was designed to examine pesticide occurrence and detection,
comparison with aquatic-life and human-health benchmarks, and temporal trends
during the study period.

## Tables in the Original USGS Data Release

The USGS data release contains seven main tables:

| Table | Description |
|---|---|
| `t1_site_info` | Monitoring-site information, including station identifiers, site names, geographic information, regions, drainage areas, and coordinates. |
| `t2_pest_concs` | Individual pesticide concentration results, including pesticide name, site, sampling date and time, detection condition, USGS parameter code, and result value in µg/L. |
| `t3_pest_TWDF` | Annual pesticide detection-frequency and concentration summaries. |
| `t4_ALB_acute` | Acute aquatic-life benchmark comparison results. |
| `t5_ALB_chronic` | Chronic aquatic-life benchmark comparison results. |
| `t6_HH_bnchmrk` | Human-health benchmark comparison results. |
| `t7_pest_trends` | Pesticide trend results for the study period. |

For the current national data audit, `t2_pest_concs` is the primary pesticide
observation table. The `t1_site_info` table provides additional information
about the monitoring locations.The remaining tables are available in the source dataset link.

## Primary Concentration Table

The `t2_pest_concs` table contains 955,728 chemical-result records for 84
pesticide-related analytes across 81 published analysis sites.

Each row represents the result for one analyte associated with a sampling
activity. Multiple analytes can therefore share the same sampling activity.

For example:

Site: Kansas River  
Sampling date: June 15, 2018  
Analyte: Atrazine  
Result: 0.42 µg/L

The working copy of the original concentration table is stored as:

`data/processed/t2_pest_concs.parquet`

The original chemical-result information is preserved separately from the
environmentally augmented dataset.

## Fields Used from `t2_pest_concs`

| Field | Description |
|---|---|
| `Pesticide_Site` | Combined pesticide and analysis-site identifier |
| `Pesticide_Name` | Name of the pesticide-related analyte |
| `Site_Abb` | Abbreviated site name |
| `USGSpcode` | USGS parameter code identifying the measured constituent |
| `Water_Year` | USGS water year |
| `Activity_ActivityIdentifier` | Identifier for the sampling activity |
| `Activity_TypeCode` | Type of sampling activity |
| `Activity_MediaSubdivision` | Sample medium subdivision |
| `Activity_StartDate` | Sample collection date |
| `Activity_StartTime` | Sample collection time |
| `Activity_StartTimeZone` | Time zone associated with sample collection |
| `Result_ResultDetectionCondition` | Detection or nondetection information |
| `Result_Value_ug_L` | Reported result value in µg/L |

## Environmental Data Requirement

The original `t2_pest_concs` table does not directly contain the six
environmental variables required for the current analysis:

- discharge
- water temperature
- dissolved oxygen
- pH
- specific conductance
- turbidity

These variables were therefore retrieved separately from USGS water-data
sources and matched to the pesticide sampling activities using site and
sampling-time information.

The resulting datasets are stored separately from the original pesticide
archive:

`data/processed/t2_pest_concs_enriched_v2.parquet`

contains the pesticide results with the six environmental variables added, and

`data/processed/sample_features.parquet`

contains the environmental information organized at the sampling-activity
level.

## Source Metadata

`Riverine_Pesticides.xml` contains the metadata associated with the original
USGS pesticide data release. It provides information about the dataset,
tables, fields, and attributes. It does not contain the pesticide observation
records themselves.