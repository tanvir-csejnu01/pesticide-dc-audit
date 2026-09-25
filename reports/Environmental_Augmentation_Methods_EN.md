# Environmental Augmentation Methods

## 1. Purpose

This report documents the two independent methods used to augment pesticide sampling activities with six environmental variables.

The two implementations are retained separately so that their results can be compared and discrepancies can be audited.

---

## 2. Observation Level

The pesticide dataset is stored at the chemical-result level, but environmental matching is performed at the **sampling-activity level**.

One sampling activity represents a water sample collected at a particular site, date, and time. Multiple pesticide analytes can be measured from the same sample.

Therefore:

```text
One sampling activity
        │
        ├── multiple pesticide concentrations
        │
        └── one matched set of environmental conditions
```

Environmental features are matched once per sampling activity and then joined back to the corresponding chemical-result records.

---

## 3. Environmental Variables

Six environmental variables are included:

| Variable | Unit |
|---|---|
| Discharge | ft³/s (cfs) |
| Water temperature | °C |
| Dissolved oxygen | mg/L |
| pH | standard units |
| Specific conductance | µS/cm |
| Turbidity | FNU |

FNU and NTU turbidity measurements are retained separately and are not automatically substituted for one another.

---

# 4. Method 1

## 4.1 Implementation

Method 1 is implemented in:

```text
scripts/06_environment_method1_independent_extraction.py
```

It retrieves environmental observations from USGS and matches them to the pesticide sampling activities.

The main USGS sources are:

- Samples API for discrete/field measurements;
- continuous-value data for sensor observations; and
- daily statistics for daily mean discharge.

---

## 4.2 Matching Hierarchy

Environmental values are selected in the following order.

### 1. `discrete_same_activity`

A discrete environmental measurement recorded under the same `Activity_ActivityIdentifier` as the pesticide sample.

```text
Time gap = 0 minutes
```

### 2. `discrete_time_match`

If a same-activity measurement is unavailable, the nearest discrete observation at the same station within:

```text
±60 minutes
```

is selected.

### 3. `continuous_nearest`

If no suitable discrete observation is available, the nearest continuous-sensor observation within:

```text
±30 minutes
```

is selected.

### 4. `daily_mean`

For discharge only, a same-date USGS daily mean can be used when an instantaneous/matched discharge value is unavailable.

### 5. No match

If none of the permitted matching rules succeeds, the environmental value remains missing.

No interpolation or carry-forward is applied.

---

## 4.3 USGS Parameter Codes

| Variable | Primary Parameter Code |
|---|---|
| Discharge | `00060` |
| Water temperature | `00010` |
| Dissolved oxygen | `00300` |
| pH | `00400` |
| Specific conductance | `00095` |
| Turbidity (FNU) | `63680` |

Additional permitted codes and detailed matching configuration are defined in:

```text
config/environmental_matching_config.yaml
```

---

# 5. Method 2

## 5.1 Implementation

Method 2 is implemented independently in:

```text
scripts/14_environment_method2_independent_extraction.py
```

Its actual extraction output was compared directly with the previously generated Method 2 dataset:

```text
data/raw/dataset_2013_2022_G.csv
```

The comparison confirmed agreement across the **12,896 sampling activities and six environmental variables** for that implementation output.

---

## 5.2 Matching Logic

Method 2 uses the same overall environmental matching hierarchy:

```text
discrete_same_activity
        ↓
discrete_time_match (±60 min)
        ↓
continuous_nearest (±30 min)
        ↓
daily_mean discharge fallback
        ↓
no match
```

The matching hierarchy is therefore consistent between the two implementations.

The two methods remain useful as independent implementations because their data retrieval, station handling, QC, and processing logic are implemented separately.

---

## 5.3 Implementation Differences

Although the matching hierarchy is the same, Method 2 includes several additional implementation features.

### Automatic station-alias detection

Method 2 derives station aliases from:

```text
t1_site_info.csv
```

This allows it to identify cases where one published analysis site is associated with more than one physical USGS station.

The Illinois River case is an example.

Method 1 handles such aliases through manually specified station mappings.

### Activity-consistency validation

Method 2 checks that each sampling activity maps consistently to its expected:

- site;
- date;
- time; and
- time zone.

### Multiple-value tracking

When multiple discrete records contribute to the same activity/parameter result, Method 2 records the number of contributing values.

### Site-level progress saving

Method 2 saves progress after individual sites, allowing long extraction runs to be resumed more easily.

---

# 6. Method 2 Retrieval Failures

The Method 2 retrieval log identified seven site/period blocks where discrete USGS retrieval timed out.

The affected blocks were:

| Site | Period |
|---|---|
| Sope Creek, GA | 2012–2014 |
| Red River, ND | 2012–2014 |
| Maple Creek, NE | 2012–2014 |
| Truckee River, NV | 2014–2016 |
| Shingle Creek, MN | 2018–2020 |
| Mississippi River, MN | 2018–2020 |
| Sacramento River, CA | 2020–2022 |

The logged failures reported USGS service read timeouts.

These retrieval failures explain important differences observed between the two independently generated environmental datasets and should be treated as retrieval issues rather than automatically interpreted as differences in matching methodology.

The retrieval record is retained in:

```text
data/interim/method2_raw_qc/retrieval_log.csv
```

---

# 7. Method 2 Provenance

The Method 2 activity-level results are retained in:

```text
data/interim/method2_activity_features.parquet
```

Detailed long-format matching information is retained in:

```text
data/interim/method2_environmental_matches.parquet
```

The long-format table represents:

```text
12,896 sampling activities
        ×
6 environmental variables
        =
77,376 activity-variable records
```

Available provenance includes fields related to:

- source station;
- source parameter code;
- matched/original value;
- matching method;
- allowed matching window;
- aggregation interval; and
- missing reason.

Current provenance completeness includes approximately:

```text
source_station_id          100%
matching_method             85.4%
original_value              85.4%
```

Some provenance fields were not recorded by the original Method 2 extraction and therefore cannot be reconstructed reliably from the existing output.

These include:

```text
observation_datetime_local
observation_timezone
original_unit
quality_flag
retrieval_date
source_query
```

Their absence is retained explicitly as a provenance limitation.

---

# 8. Cross-Method Comparison

Method 1 and Method 2 are compared at the:

```text
sampling activity × environmental variable
```

level.

Each comparison can be classified as:

| Comparison Class | Meaning |
|---|---|
| Both missing | Neither method obtained a value |
| Method 1 only | Method 1 obtained a value; Method 2 did not |
| Method 2 only | Method 2 obtained a value; Method 1 did not |
| Agreement | Both methods obtained equivalent values within the comparison tolerance |
| Discrepant | Both methods obtained values but they differ beyond the comparison tolerance |

The complete exception record is stored in:

```text
data/interim/environmental_match_exceptions.csv
```

The current comparison contains:

```text
Discharge exceptions:                   145
Other environmental exceptions:         969
                                      -----
Total exceptions:                     1,114
```

The 969 non-discharge discrepancies are also summarized in:

```text
data/processed/dataset_discrepancies.csv
```

Agreement between the two methods provides a reproducibility check, but agreement alone does not verify every aspect of provenance.

---

# 9. Environmental Coverage

Method 1 provides high activity-level coverage for five environmental variables.

Approximate coverage is:

```text
Five non-turbidity variables: 98.3–99.1%
Turbidity:                    26.3%
```

Turbidity is substantially less complete because suitable turbidity observations are unavailable for many site/time combinations.

Detailed coverage results are retained in:

```text
outputs/tables/environmental_coverage_summary.csv
```

---

# 10. Provenance Requirements

For a fully traceable environmental match, the preferred provenance fields are:

| Provenance Field | Purpose |
|---|---|
| Source station | Identifies the physical monitoring station |
| Parameter code | Identifies the environmental parameter retrieved |
| Observation timestamp | Identifies when the source observation was recorded |
| Observation time zone | Defines the source timestamp reference |
| Original value/unit | Preserves the source representation |
| Standardized value/unit | Records the analysis-ready representation |
| Matching method | Identifies how the observation was selected |
| Time offset | Difference between source observation and sample time |
| Allowed matching window | Documents the temporal rule |
| Aggregation interval | Distinguishes instantaneous and daily values |
| Quality flag | Preserves source quality information |
| Missing reason | Explains unsuccessful matching |
| Retrieval date | Records when the source was queried |
| Source/query information | Supports reproducibility |

Not all of these fields are recoverable from the historical extraction outputs.

---

# 11. Manual Verification

Two targeted checks have been completed against raw USGS records:

1. Sope Creek discharge; and
2. Sope Creek water temperature, dissolved oxygen, and pH.

The verification records are retained in:

```text
outputs/checks/manual_spot_checks.csv
```

Additional details are documented in:

```text
reports/National_Data_Audit_EN.md
```

The remaining retrieval/discrepancy cases should be interpreted using the comparison and retrieval logs until additional manual verification is completed.

---

# 12. Current Status

| Component | Status |
|---|---|
| Method 1 environmental values | Available |
| Method 1 activity-level source/gap information | Available in `sample_features.parquet` |
| Method 1 full provenance | Incomplete |
| Method 2 environmental values | Available |
| Method 2 independent extraction | Completed |
| Method 2 activity-level features | Available |
| Method 2 detailed provenance | Partially available |
| Method 2 retrieval failures | Documented |
| Cross-method comparison | Completed |
| Complete provenance for every matched value | Not yet available |
| Manual source verification | Partially completed |

The main remaining limitation is **provenance completeness**, particularly source timestamps, original units, quality flags, retrieval dates, and query information that were not retained by the original extraction runs.