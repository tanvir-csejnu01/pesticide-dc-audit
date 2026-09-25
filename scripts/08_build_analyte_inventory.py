#!/usr/bin/env python3
"""
08_build_analyte_inventory.py
Build the 84-analyte inventory.

Adds the complete-month DC overlap split requested in the task brief:
2013-01-01 through 2021-08-31. Observations outside that window remain in
the full archive.

Output:
  data/processed/analyte_list_84.csv

NOTE (2026-09): this script previously ALSO built data/processed/
activity_master.parquet inline, using groupby(["Pesticide_Site",
"Activity_ActivityIdentifier"]) as the row key. That key is NOT what it
looks like -- Pesticide_Site encodes the analyte as well as the site
("AnalyteName_SiteNumber"), so it is unique per CHEMICAL-RESULT ROW, not
per sampling activity. The result was a 955,728-row "activity_master" file
-- one row per pesticide result, not per activity, exactly the distinction
this file exists to preserve. It also collided with the same file being
built (correctly or not) by scripts/09_build_activity_master.py.
Activity_ActivityIdentifier was checked directly (see
scripts/09_build_activity_master.py's header) and found to be globally
unique on its own -- no compound key is needed. The activity_master build
was removed from this script; scripts/09_build_activity_master.py is now
the single, corrected source for that file.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN_BASE = ROOT / "data/processed/t2_pest_concs.parquet"
IN_ENRICHED = ROOT / "data/processed/t2_pest_concs_enriched_v2.parquet"
OUT_ANALYTE = ROOT / "data/processed/analyte_list_84.csv"

ENV_SIX = ["Discharge_cfs","Water_Temperature_C","Dissolved_Oxygen_mg_L",
           "pH","Turbidity_FNU","Specific_Conductance"]
ENV_CORE5 = [v for v in ENV_SIX if v != "Turbidity_FNU"]
DC_START = pd.Timestamp("2013-01-01")
DC_END = pd.Timestamp("2021-08-31")

def main():
    base = pd.read_parquet(IN_BASE)
    en = pd.read_parquet(IN_ENRICHED)
    assert len(base) == len(en) == 955_728
    for c in ["Pesticide_Site","Pesticide_Name","USGSpcode",
              "Activity_ActivityIdentifier","Activity_StartDate"]:
        assert c in en.columns, f"missing required field: {c}"

    en["y"] = pd.to_numeric(en["Result_Value_ug_L"], errors="coerce")
    cond = en["Result_ResultDetectionCondition"].astype("string").str.strip()
    en["ND"] = cond.eq("Not Detected")
    en["date"] = pd.to_datetime(en["Activity_StartDate"], errors="coerce")
    en["dc_window"] = en["date"].between(DC_START, DC_END, inclusive="both")
    en["core5_ok"] = en[ENV_CORE5].notna().all(axis=1)
    en["all6_ok"] = en[ENV_SIX].notna().all(axis=1)

    def summarize(g):
        nd = g.loc[g["ND"], "y"].dropna()
        det = g.loc[~g["ND"], "y"].dropna()
        return pd.Series({
            "n_chemical_result_rows": len(g),
            "n_sampling_activities": g["Activity_ActivityIdentifier"].nunique(),
            "n_analysis_sites": g["Pesticide_Site"].nunique(),
            "n_site_abbreviations": g["Site_Abb"].nunique(),
            "first_date": g["date"].min(),
            "last_date": g["date"].max(),
            "n_water_years": g["Water_Year"].nunique(),
            "n_nondetect_rows": int(g["ND"].sum()),
            "n_other_detection_condition_rows": int((~g["ND"]).sum()),
            "n_detection_condition_missing": int(cond.loc[g.index].isna().sum()),
            "reporting_level_min_ugL": nd.min() if len(nd) else np.nan,
            "reporting_level_median_ugL": nd.median() if len(nd) else np.nan,
            "reporting_level_max_ugL": nd.max() if len(nd) else np.nan,
            "reporting_level_changed_over_time": bool(nd.nunique() > 1) if len(nd) else False,
            "detected_or_other_value_median_ugL": det.median() if len(det) else np.nan,
            "detected_or_other_value_max_ugL": det.max() if len(det) else np.nan,
            "pct_rows_with_5_core_env_vars": round(100*g["core5_ok"].mean(),1),
            "pct_rows_with_all_6_env_vars": round(100*g["all6_ok"].mean(),1),
            "dc_window_rows": int(g["dc_window"].sum()),
            "dc_window_activities": g.loc[g["dc_window"],"Activity_ActivityIdentifier"].nunique(),
            "outside_dc_window_rows": int((~g["dc_window"]).sum()),
            "outside_dc_window_activities": g.loc[~g["dc_window"],"Activity_ActivityIdentifier"].nunique(),
        })

    per = (en.groupby(["Pesticide_Name","USGSpcode"], dropna=False)
             .apply(summarize, include_groups=False)
             .reset_index()
             .sort_values("Pesticide_Name"))
    assert len(per) == 84
    per.to_csv(OUT_ANALYTE, index=False)

    print(f"wrote {OUT_ANALYTE}: {len(per)} analytes")

if __name__ == "__main__":
    main()
