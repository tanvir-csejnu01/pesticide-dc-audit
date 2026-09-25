# Unresolved Issues

## Current Status

The main Phase-1 audit is complete. The national 84-analyte dataset has been
organized, environmentally augmented, compared across two independent
extraction methods, analyzed, and validated.

The items below are either:

1. additional verification that can strengthen the current dataset; or
2. work planned for the next research phase.

They do not indicate that the main Phase-1 audit is incomplete.

---

## 1. Remaining Verification

### Environmental Provenance

Some detailed source information was not recorded during the original
environmental extraction, including source timestamps, original units,
quality flags, and signed time offsets for some matches.

These fields can be completed through additional source extraction if they
are required for the final modeling dataset.

### Remaining Discrepancy Checks

The major differences between the two environmental extraction methods have
already been identified. Method 2 retrieval logs also explain the main
timeout-related discrepancy blocks.

Direct USGS source verification has been completed for the Sope Creek case.
Additional source-level checks can be performed for the remaining discrepancy
blocks.

### Station Crosswalk

The known Illinois River historical station mapping has been resolved.

A systematic station crosswalk can still be performed to confirm that all
published analysis sites are connected to the correct physical USGS stations.

### Environmental Outliers

Unusual environmental values have been identified and flagged but not
automatically changed.

These values should be checked against the original USGS records before
preparing the final modeling dataset.

### Reporting-Level Changes

Changes in pesticide reporting levels have been identified for many analytes.

Additional verification of laboratory-method and reporting-level changes may
be needed when interpreting long-term detection patterns.

---

## 2. Next Research Phase

The following tasks belong to the next stage of the research rather than the
main Phase-1 audit.

### DC/NHM-PRMS Hydrology

Retrieve and connect the required DC/NHM-PRMS hydrologic variables with the
audited pesticide observations.

### National Basin/HUC12 Connection

Extend the upstream basin and HUC12 workflow from the pilot stations to the
national monitoring sites.

### Separate Imidacloprid Cross-Check

Compare the separate imidacloprid release with the national dataset as an
independent cross-check without directly merging the two datasets.

### Final Research Dataset Selection

Use the Phase-1 audit results together with the DC/NHM-PRMS information to
determine whether the final modeling dataset should use:

- all analytes;
- groups of analytes; or
- selected analytes.

---

## 3. Project Status

| Component | Status |
|---|---|
| Full 84-analyte dataset audit | **Complete** |
| Sampling-activity organization | **Complete** |
| Environmental augmentation | **Complete** |
| Environmental coverage analysis | **Complete** |
| Method 1 vs. Method 2 comparison | **Complete** |
| Method 2 reproduction check | **Complete** |
| All-84-analyte comparative analysis | **Complete** |
| Automated integrity validation | **Complete** |
| Selected manual USGS verification | **Complete** |
| Additional source verification | Remaining |
| Detailed provenance completion | Remaining if required |
| DC/NHM-PRMS integration | Next phase |
| National basin/HUC12 extension | Next phase |
| Final research dataset selection | Next phase |

The remaining items mainly involve additional verification and the next
research stage. The main Phase-1 audit and comparative analysis are complete.