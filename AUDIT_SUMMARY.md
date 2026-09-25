# Phase-1 Audit Summary

**Project:** National 84-Analyte Audit and Environmental Augmentation  
**Dataset:** USGS Riverine Pesticide Dataset, Water Years 2013–2022  
**Status:** Phase-1 audit completed for all 84 analytes.

## 1. What We Did

The main goal of Phase 1 was to understand and prepare the complete USGS pesticide dataset before selecting data for modeling.

We started with the full national dataset instead of selecting a few pesticides in advance. The dataset contains:

- 955,728 chemical-result records;
- 84 pesticide analytes;
- 81 published analysis sites; and
- 12,896 unique sampling activities.

We first organized the pesticide records by sampling activity. This was important because one water sample can be analyzed for many different chemicals, while the environmental conditions belong to the sampling event.

We then matched six environmental variables to each sampling activity:

- discharge;
- water temperature;
- dissolved oxygen;
- pH;
- specific conductance; and
- turbidity.

Two independent environmental extraction methods were compared to check the reliability of the augmentation. Differences between the methods were identified, investigated, and documented.

Finally, all 84 analytes were compared using the same criteria, including data availability, site and time coverage, detection rate, reporting limits, concentration distribution, environmental-data availability, and relationships with environmental conditions.

---

## 2. What We Found

The audit showed that the national dataset provides a strong data base for further research.

Five environmental variables have approximately **98–99% activity-level coverage**. Turbidity has much lower coverage (**26.3%**) and therefore requires special consideration in later modeling.

The two environmental extraction methods showed **98.75% overall cell-level agreement**. Most of the major differences were linked to documented data-retrieval problems, and the remaining cases are retained for further verification.

The 84 analytes also do not have identical data characteristics. They differ in:

- number of observations;
- site and time coverage;
- detection frequency;
- reporting limits;
- concentration distributions; and
- relationships with environmental conditions.

The environmental relationship analysis also showed that many analytes have statistically supported associations with one or more environmental variables.

Therefore, the environmental variables provide useful information for the next stage of concentration analysis and modeling.

---

## 3. What We Gained from the Audit

The most important outcome of Phase 1 is that we now understand the **structure, quality, coverage, and limitations of the complete dataset** before building a model.

Before the audit, we mainly knew that a large pesticide dataset was available.

After the audit, we know:

```text
What data are available
        ↓
How the sampling activities are organized
        ↓
Which environmental variables can be matched
        ↓
How complete those variables are
        ↓
How reliable the environmental matching is
        ↓
How the 84 analytes differ
        ↓
What limitations must be considered before modeling
```

This gives us a much stronger basis for research dataset selection.

---

## 4. How This Helps Dataset Selection

The audit does **not** tell us to select a particular pesticide yet.

Instead, it gives us the evidence needed to make that decision systematically.

For each analyte, we can now consider:

```text
Enough observations?
        +
Enough sites and years?
        +
Sufficient detections?
        +
Stable/understood reporting limits?
        +
Environmental predictors available?
        +
Meaningful environmental relationships?
```

Based on these characteristics, the next phase can determine whether it is more appropriate to use:

- all analytes in a unified framework;
- groups of analytes with similar data characteristics; or
- selected analytes with sufficient data for detailed modeling.

Therefore, analyte selection will be based on **data evidence rather than preselecting chemicals based only on interest or the earlier pilot study**.

---

## 5. Current Research Dataset

The main output of Phase 1 is the audited and environmentally enriched national pesticide dataset:

```text
data/processed/t2_pest_concs_enriched_v2.parquet
```

Supporting activity-level environmental data and analyte-level comparison tables are also retained for validation and later dataset selection.

The current dataset keeps all 84 analytes and all original pesticide-result records. No final modeling subset has yet been created.

---

## 6. Next Step

The next step is to combine the Phase-1 audit results with the required **DC/NHM-PRMS hydrologic information**.

This will allow us to evaluate not only the environmental conditions at the monitoring station, but also the upstream hydrologic conditions associated with the pesticide observations.

After this integration, we can define the final research dataset and decide whether the modeling framework should use all analytes, groups of analytes, or selected analytes.

---

## Overall Outcome

Phase 1 changed the project from a small pilot-based analysis to a **data-driven national-scale research dataset assessment**.

We now have:

1. a structured national pesticide dataset;
2. environmental information linked to sampling activities;
3. independent validation of the environmental augmentation;
4. a common comparison of all 84 analytes; and
5. evidence that can be used to select the final research dataset in the next phase.

The main gain is that **we do not need to choose the research analytes blindly**. We can now make the modeling-scope and dataset-selection decision based on measured data coverage, detection characteristics, environmental availability, and analyte behavior.