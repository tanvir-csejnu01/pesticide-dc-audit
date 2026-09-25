#!/usr/bin/env python3
"""
11_compare_all_analytes.py
Apply one descriptive comparison workflow to all 84 analytes.

Adds:
- full-release and DC-window coverage fields;
- Benjamini-Hochberg FDR correction for environmental association tests.

No analyte is ranked, selected, or excluded.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT=Path(__file__).resolve().parents[1]
IN_ENRICHED=ROOT/"data/processed/t2_pest_concs_enriched_v2.parquet"
OUT_WIDE=ROOT/"data/processed/analyte_comparison_full.csv"
OUT_REL=ROOT/"data/processed/analyte_env_relationships.csv"

ENV_SIX=["Discharge_cfs","Water_Temperature_C","Dissolved_Oxygen_mg_L",
         "pH","Turbidity_FNU","Specific_Conductance"]
N_SITES_TOTAL=81
DC_START=pd.Timestamp("2013-01-01")
DC_END=pd.Timestamp("2021-08-31")
SEASON={12:"DJF",1:"DJF",2:"DJF",3:"MAM",4:"MAM",5:"MAM",
        6:"JJA",7:"JJA",8:"JJA",9:"SON",10:"SON",11:"SON"}
MIN_N_FOR_CORR=20

def bh_adjust(p):
    """Benjamini-Hochberg adjusted p-values; NaNs remain NaN."""
    s=pd.Series(p, dtype=float)
    out=pd.Series(np.nan,index=s.index,dtype=float)
    valid=s.dropna()
    if valid.empty: return out
    order=valid.sort_values().index
    vals=valid.loc[order].to_numpy()
    m=len(vals)
    adj=vals*m/np.arange(1,m+1)
    adj=np.minimum.accumulate(adj[::-1])[::-1]
    adj=np.clip(adj,0,1)
    out.loc[order]=adj
    return out

def per_analyte(g):
    nd=g.loc[g["ND"],"y"].dropna()
    det=g.loc[~g["ND"] & g["y"].notna() & (g["y"]>0)]
    out={
        "n_chemical_result_rows":len(g),
        "n_sampling_activities":g["Activity_ActivityIdentifier"].nunique(),
        "n_analysis_sites":g["Pesticide_Site"].nunique(),
        "pct_of_81_analysis_sites":round(100*g["Pesticide_Site"].nunique()/N_SITES_TOTAL,1),
        "n_water_years_present":g["Water_Year"].nunique(),
        "first_date":g["date"].min(),
        "last_date":g["date"].max(),
        "n_nondetect_rows":int(g["ND"].sum()),
        "n_other_condition_rows":int((~g["ND"]).sum()),
        "n_detection_condition_missing":int(g["condition_missing"].sum()),
        "reporting_level_min_ugL":nd.min() if len(nd) else np.nan,
        "reporting_level_median_ugL":nd.median() if len(nd) else np.nan,
        "reporting_level_max_ugL":nd.max() if len(nd) else np.nan,
        "conc_median_ugL":det["y"].median() if len(det) else np.nan,
        "conc_q25_ugL":det["y"].quantile(.25) if len(det) else np.nan,
        "conc_q75_ugL":det["y"].quantile(.75) if len(det) else np.nan,
        "conc_max_ugL":det["y"].max() if len(det) else np.nan,
        "n_sites_with_non_nondetect_value":det["Pesticide_Site"].nunique() if len(det) else 0,
        "dc_window_rows":int(g["dc_window"].sum()),
        "dc_window_activities":g.loc[g["dc_window"],"Activity_ActivityIdentifier"].nunique(),
        "outside_dc_window_rows":int((~g["dc_window"]).sum()),
        "outside_dc_window_activities":g.loc[~g["dc_window"],"Activity_ActivityIdentifier"].nunique(),
    }
    if g["season"].notna().any():
        rates=g.groupby("season")["ND"].apply(lambda s:(~s).mean())
        out["peak_season_by_non_nondetect_fraction"]=rates.idxmax() if len(rates) else np.nan
    else:
        out["peak_season_by_non_nondetect_fraction"]=np.nan
    for v in ENV_SIX:
        out[f"pct_rows_matched_{v}"]=round(100*g[v].notna().mean(),1)
        # activity-level coverage for this analyte
        a=g.groupby("Activity_ActivityIdentifier")[v].apply(lambda s:s.notna().any())
        out[f"pct_activities_matched_{v}"]=round(100*a.mean(),1) if len(a) else np.nan
    return pd.Series(out)

def relationships(g,name):
    rows=[]
    for v in ENV_SIX:
        sub=g[[v,"ND"]].dropna()
        if len(sub)>=MIN_N_FOR_CORR and sub["ND"].nunique()==2:
            rho,p=stats.spearmanr(sub[v],(~sub["ND"]).astype(int))
        else: rho,p=np.nan,np.nan
        rows.append({"Pesticide_Name":name,"variable":v,
                     "relationship":"non_nondetect_status_vs_env",
                     "n":len(sub),"spearman_rho":rho,"p_value":p})
        subd=g.loc[(~g["ND"]) & g["y"].notna() & (g["y"]>0),[v,"y"]].dropna()
        if len(subd)>=MIN_N_FOR_CORR:
            rho,p=stats.spearmanr(subd[v],np.log10(subd["y"]))
        else: rho,p=np.nan,np.nan
        rows.append({"Pesticide_Name":name,"variable":v,
                     "relationship":"log10_value_vs_env_among_non_nondetects",
                     "n":len(subd),"spearman_rho":rho,"p_value":p})
    return rows

def main():
    en=pd.read_parquet(IN_ENRICHED)
    en["y"]=pd.to_numeric(en["Result_Value_ug_L"],errors="coerce")
    cond=en["Result_ResultDetectionCondition"].astype("string").str.strip()
    en["ND"]=cond.eq("Not Detected")
    en["condition_missing"]=cond.isna() | cond.eq("")
    en["date"]=pd.to_datetime(en["Activity_StartDate"],errors="coerce")
    en["dc_window"]=en["date"].between(DC_START,DC_END,inclusive="both")
    en["season"]=en["date"].dt.month.map(SEASON)

    wide=(en.groupby(["Pesticide_Name","USGSpcode"],dropna=False)
           .apply(per_analyte,include_groups=False).reset_index()
           .sort_values("Pesticide_Name"))
    assert len(wide)==84
    wide.to_csv(OUT_WIDE,index=False)

    rows=[]
    for name,g in en.groupby("Pesticide_Name"):
        rows.extend(relationships(g,name))
    rel=pd.DataFrame(rows)
    # Correct across the complete family of tests reported in this table.
    rel["p_value_fdr_bh"]=bh_adjust(rel["p_value"])
    rel["significant_fdr_0_05"]=rel["p_value_fdr_bh"].lt(.05)
    rel.to_csv(OUT_REL,index=False)

    print(f"wrote {OUT_WIDE}: {len(wide)} analytes")
    print(f"wrote {OUT_REL}: {len(rel)} relationship rows")
    print("FDR-significant tests (q<0.05):",
          int(rel["significant_fdr_0_05"].fillna(False).sum()))

if __name__=="__main__":
    main()
