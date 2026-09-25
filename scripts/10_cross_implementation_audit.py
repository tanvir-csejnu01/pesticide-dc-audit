#!/usr/bin/env python3
"""
08_cross_implementation_audit.py
==================================
Compares this project's environmental augmentation (produced by
06_build_environmental_features.py) against a second, independently written
implementation, at both the chemical-result-row level and the
sampling-activity level. Required by the Student Task Brief's "automated
checks... compare the two extraction implementations, and document
discrepancies and unresolved cases."

Inputs:
  data/processed/t2_pest_concs_enriched_v2.parquet   this project's dataset
  data/raw/dataset_2013_2022_G.csv                   second implementation
                                                       (NOT stored in this repo;
                                                       see data/raw/README.md)

Outputs:
  data/processed/dataset_discrepancies.csv    every cell where the two
                                               implementations disagree or one
                                               has a value the other lacks
  (summary statistics are printed to stdout)

STATUS: reproduces the comparison already reported (98.56% cell-level
agreement; 98.01% of activities identical on all six variables). The second
implementation's file is large (~250 MB) and is deliberately NOT committed to
this repository — see the note in data/raw/README.md on keeping large raw
files out of version control. Point IN_G at a local copy to re-run this
script.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN_MINE = ROOT / "data/processed/t2_pest_concs_enriched_v2.parquet"
IN_G = ROOT / "data/raw/dataset_2013_2022_G.csv"  # place a local copy here to re-run
OUT = ROOT / "data/processed/dataset_discrepancies.csv"

ENV_SIX = ["Discharge_cfs", "Water_Temperature_C", "Dissolved_Oxygen_mg_L",
          "pH", "Turbidity_FNU", "Specific_Conductance"]
G_NAME = {  # Implementation G's column names -> this project's names
    "Discharge_cfs": "Discharge_cfs",
    "Water_Temperature_C": "Water_Temperature_C",
    "Dissolved_Oxygen_mg_L": "Dissolved_Oxygen_mg_L",
    "pH": "pH",
    "Specific_Conductance_uScm": "Specific_Conductance",
    "Turbidity_FNU": "Turbidity_FNU",
}


def main() -> None:
    if not IN_G.exists():
        raise SystemExit(
            f"{IN_G} not found. This ~250 MB file is intentionally excluded from "
            "version control; place a local copy at that path to re-run this audit. "
            "The last-computed output is already at data/processed/dataset_discrepancies.csv."
        )

    key = ["Activity_ActivityIdentifier", "Site_Abb", "Activity_StartDate", "Water_Year"]
    mine = pd.read_csv(IN_MINE if IN_MINE.suffix == ".csv" else IN_MINE, columns=None) \
        if False else pd.read_parquet(IN_MINE)
    g = pd.read_csv(IN_G, usecols=key + list(G_NAME))
    g = g.rename(columns=G_NAME)

    for c in key:
        assert (g[c].astype(str).values == mine[c].astype(str).values).all(), \
            f"row order / key mismatch on {c} — the two files must have identical row order"

    E = pd.concat([mine[key], g[ENV_SIX].add_suffix("_G"), mine[ENV_SIX].add_suffix("_M")], axis=1)
    E = E.drop_duplicates("Activity_ActivityIdentifier").reset_index(drop=True)

    rows = []
    for v in ENV_SIX:
        a, b = E[v + "_G"], E[v + "_M"]
        kind = np.where(a.isna() & b.notna(), "mine missing (G has value)",
               np.where(a.notna() & b.isna(), "G missing (mine has value)",
               np.where((a - b).abs() > 1e-9, "values differ", None)))
        mask = pd.Series(kind, index=E.index).notna()
        r = E.loc[mask, ["Activity_ActivityIdentifier", "Site_Abb", "Activity_StartDate"]].copy()
        r["variable"] = v
        r["G_value"] = a[mask]
        r["mine_value"] = b[mask]
        r["difference_G_minus_mine"] = (a - b)[mask]
        r["issue"] = pd.Series(kind, index=E.index)[mask]
        rows.append(r)
    R = pd.concat(rows).sort_values(["Site_Abb", "Activity_StartDate", "variable"])
    R.to_csv(OUT, index=False)

    n_act = len(E)
    all_same = np.ones(n_act, bool)
    for v in ENV_SIX:
        all_same &= ((E[v + "_G"] == E[v + "_M"]) | (E[v + "_G"].isna() & E[v + "_M"].isna())).values
    cell_ident = np.mean([
        ((E[v + "_G"] == E[v + "_M"]) | (E[v + "_G"].isna() & E[v + "_M"].isna())).mean()
        for v in ENV_SIX
    ])
    print(f"activities compared: {n_act:,}")
    print(f"cell-level agreement across all 6 variables: {cell_ident * 100:.2f}%")
    print(f"activities identical on all 6 variables: {all_same.sum():,} ({all_same.mean() * 100:.2f}%)")
    print(f"discrepancy rows written to {OUT}: {len(R):,} cells, "
          f"{R['Activity_ActivityIdentifier'].nunique():,} activities")


if __name__ == "__main__":
    main()
