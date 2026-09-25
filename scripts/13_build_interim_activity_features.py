#!/usr/bin/env python3
"""
11_build_interim_activity_features.py
=======================================
Builds data/interim/'s three files, splitting the two extraction methods'
activity-level results apart from the final, merged dataset:

  method1_activity_features.parquet   this project's own extraction (script 06),
                                       12,896 rows, with per-variable match
                                       method and time-gap provenance
  method2_activity_features.parquet   the second implementation's extraction,
                                       collapsed to one row per activity
  environmental_match_exceptions.csv  every (activity, variable) cell where
                                       the two methods disagree or one lacks
                                       a value the other has

Method 1's values here are its OWN independent extraction -- including its
own discharge -- not the discharge substitution applied in
data/processed/t2_pest_concs_enriched_v2.parquet. That substitution (145
activities, documented in reports/National_Data_Audit_EN.md, Section 5) is
deliberately NOT applied here, since the point of this folder is to preserve
what each method independently produced, before that resolution. As a
result, environmental_match_exceptions.csv shows 145 discharge exceptions
(matching that same 145-activity count exactly, a useful cross-check) plus
969 non-discharge exceptions (matching data/processed/dataset_discrepancies.csv
exactly, another cross-check both this script and the earlier one agree).

Inputs (both must already exist; run 06 first if sample_features.parquet is missing):
  data/processed/t2_pest_concs.parquet         for the Site_Abb/Water_Year/date key
  data/processed/sample_features.parquet       Method 1's own extraction
  data/raw/dataset_2013_2022_G.csv             Method 2's extraction (NOT committed;
                                                see data/raw/README.md -- place a local
                                                copy there to run this script)

Provenance note: an earlier run of this script (2026-09) found that
sample_features.parquet was stale for the Illinois River site (it predated
a station-alias fix applied in script 06) and used that discovery to patch
it in place. See UNRESOLVED_ISSUES.md, Resolved section. This script now
assumes sample_features.parquet is current; it does not re-detect staleness.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ENV_SIX = ["Discharge_cfs", "Water_Temperature_C", "Dissolved_Oxygen_mg_L",
          "pH", "Turbidity_FNU", "Specific_Conductance"]
KEY = ["Activity_ActivityIdentifier", "Site_Abb", "Water_Year", "Activity_StartDate"]


def build_method1(t2: pd.DataFrame) -> pd.DataFrame:
    keys = t2[KEY].drop_duplicates("Activity_ActivityIdentifier")
    sf = pd.read_parquet(ROOT / "data/processed/sample_features.parquet")
    sf = sf.rename(columns={"activity_id": "Activity_ActivityIdentifier"})
    cols = ["Activity_ActivityIdentifier"] + [c for v in ENV_SIX for c in (v, f"{v}_source", f"{v}_gap_min")]
    m1 = keys.merge(sf[cols], on="Activity_ActivityIdentifier", how="left")
    out_cols = KEY[:]
    for v in ENV_SIX:
        out_cols += [v, v + "_source", v + "_gap_min"]
    return m1[out_cols].sort_values("Activity_ActivityIdentifier").reset_index(drop=True)


def build_method2(g_path: Path) -> pd.DataFrame:
    g_cols = KEY + ["Discharge_cfs", "Water_Temperature_C", "Dissolved_Oxygen_mg_L",
                    "pH", "Specific_Conductance_uScm", "Turbidity_FNU"]
    g = pd.read_csv(g_path, usecols=g_cols, dtype={"Activity_ActivityIdentifier": str})
    g = g.rename(columns={"Specific_Conductance_uScm": "Specific_Conductance"})
    chk = g.groupby("Activity_ActivityIdentifier")[ENV_SIX].nunique(dropna=False)
    assert (chk <= 1).all().all(), "Method 2 source has a non-constant env value within one activity"
    m2 = g.drop_duplicates("Activity_ActivityIdentifier")[KEY + ENV_SIX]
    return m2.sort_values("Activity_ActivityIdentifier").reset_index(drop=True)


def build_exceptions(m1: pd.DataFrame, m2: pd.DataFrame) -> pd.DataFrame:
    E = m1[KEY + ENV_SIX].merge(m2[["Activity_ActivityIdentifier"] + ENV_SIX],
                                on="Activity_ActivityIdentifier", suffixes=("_method1", "_method2"))
    rows = []
    for v in ENV_SIX:
        a, b = E[v + "_method1"], E[v + "_method2"]
        kind = np.where(a.isna() & b.notna(), "method1_missing_method2_has_value",
               np.where(a.notna() & b.isna(), "method2_missing_method1_has_value",
               np.where((a - b).abs() > 1e-9, "values_differ", None)))
        mask = pd.Series(kind, index=E.index).notna()
        r = E.loc[mask, KEY].copy()
        r["variable"] = v
        r["method1_value"] = a[mask]
        r["method2_value"] = b[mask]
        r["difference_method1_minus_method2"] = (a - b)[mask]
        r["exception_type"] = pd.Series(kind, index=E.index)[mask]
        rows.append(r)
    return pd.concat(rows).sort_values(["Site_Abb", "Activity_StartDate", "variable"]).reset_index(drop=True)


def main() -> None:
    g_path = ROOT / "data/raw/dataset_2013_2022_G.csv"
    if not g_path.exists():
        raise SystemExit(
            f"{g_path} not found. This file is intentionally excluded from version "
            "control (see data/raw/README.md) -- place a local copy there to run this "
            "script. The last-computed outputs are already in data/interim/."
        )

    outdir = ROOT / "data/interim"
    outdir.mkdir(parents=True, exist_ok=True)

    t2 = pd.read_parquet(ROOT / "data/processed/t2_pest_concs.parquet")
    m1 = build_method1(t2)
    assert len(m1) == 12896 and m1.Activity_ActivityIdentifier.is_unique
    m1.to_parquet(outdir / "method1_activity_features.parquet", index=False)

    m2 = build_method2(g_path)
    assert len(m2) == 12896 and m2.Activity_ActivityIdentifier.is_unique
    m2.to_parquet(outdir / "method2_activity_features.parquet", index=False)

    exc = build_exceptions(m1, m2)
    exc.to_csv(outdir / "environmental_match_exceptions.csv", index=False)

    n_act = exc.Activity_ActivityIdentifier.nunique()
    non_disch = (exc.variable != "Discharge_cfs").sum()
    print(f"method1_activity_features.parquet: {m1.shape}")
    print(f"method2_activity_features.parquet: {m2.shape}")
    print(f"environmental_match_exceptions.csv: {exc.shape}")
    print(exc.groupby("variable").size().to_string())
    print(f"\nactivities with >=1 exception: {n_act} (cross-check: should be 257)")
    print(f"non-discharge exceptions: {non_disch} (cross-check: should be 969, "
         "matching data/processed/dataset_discrepancies.csv)")
    print(f"discharge exceptions: {(exc.variable == 'Discharge_cfs').sum()} "
         "(cross-check: should be 145, matching the discharge substitution count "
         "in reports/National_Data_Audit_EN.md Section 5)")


if __name__ == "__main__":
    main()
