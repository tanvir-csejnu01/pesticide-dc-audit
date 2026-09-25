#!/usr/bin/env python3
"""
09_build_activity_master.py

Create one row per sampling activity from the enriched national table.
Environmental observations shared by multiple analytes are therefore
represented once at the activity level -- this is the reference table for
the "chemical-result row vs. sampling activity" distinction.

KEY FIX (2026-09): this script previously grouped by
["Pesticide_Site", "Activity_ActivityIdentifier"]. Pesticide_Site encodes
the analyte as well as the site ("AnalyteName_SiteNumber"), so that key is
actually unique per CHEMICAL-RESULT ROW, not per activity -- the resulting
file had 955,728 rows (one per pesticide result) instead of ~12,896 (one
per activity), a 74x inflation that defeated the file's entire purpose.

Checked directly before fixing (not assumed): grouping the base release by
Activity_ActivityIdentifier and counting distinct Site_Abb per group gives
0 activities mapping to more than one site -- Activity_ActivityIdentifier
IS globally unique in this dataset, on its own, with no compound key
needed. Fixed to group by Activity_ActivityIdentifier alone.

Output:
    data/processed/activity_master.parquet
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INFILE = ROOT / "data/processed/t2_pest_concs_enriched_v2.parquet"
OUTFILE = ROOT / "data/processed/activity_master.parquet"
DC_START = pd.Timestamp("2013-01-01")
DC_END = pd.Timestamp("2021-08-31")

ENV = [
    "Discharge_cfs","Water_Temperature_C","Dissolved_Oxygen_mg_L",
    "pH","Turbidity_FNU","Specific_Conductance"
]

def first_nonmissing(s):
    x=s.dropna()
    return x.iloc[0] if len(x) else None

def main():
    df=pd.read_parquet(INFILE)
    required=["Pesticide_Site","Activity_ActivityIdentifier",
              "Activity_StartDate","Activity_StartTime",
              "Activity_StartTimeZone","Pesticide_Name","Site_Abb"]
    missing=[c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Verify the global-uniqueness assumption every run, rather than trusting
    # the docstring's earlier one-time check.
    multi_site = df.groupby("Activity_ActivityIdentifier")["Site_Abb"].nunique()
    if (multi_site > 1).any():
        raise ValueError(
            f"{int((multi_site > 1).sum())} activity IDs map to more than one "
            "Site_Abb -- Activity_ActivityIdentifier is NOT globally unique in "
            "this run. Do not group by it alone; investigate before proceeding."
        )

    for c in ENV:
        if c not in df.columns:
            df[c]=pd.NA

    agg={
        "Pesticide_Site":"first",  # kept for traceability; NOT the grouping key
        "Site_Abb":"first",
        "Activity_StartDate":"first",
        "Activity_StartTime":"first",
        "Activity_StartTimeZone":"first",
        "Activity_TypeCode":"first",
        "Activity_MediaSubdivision":"first",
        "Pesticide_Name":"nunique",
    }
    for c in ENV:
        agg[c]=first_nonmissing

    a=(df.groupby("Activity_ActivityIdentifier", dropna=False)
         .agg(agg).reset_index()
         .rename(columns={"Pesticide_Name":"n_analytes"}))

    a["sample_date"]=pd.to_datetime(a["Activity_StartDate"],errors="coerce")
    a["dc_window"]=a["sample_date"].between(DC_START,DC_END,inclusive="both")
    a.to_parquet(OUTFILE,index=False)
    assert len(a) == df["Activity_ActivityIdentifier"].nunique(), \
        "row count does not match the true activity count -- fix did not take"
    print(f"Wrote {OUTFILE} with {len(a):,} activity rows "
         f"(from {len(df):,} chemical-result rows).")

if __name__=="__main__":
    main()

