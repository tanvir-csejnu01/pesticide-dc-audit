#!/usr/bin/env python3
"""
build_features.py
=================
Add USGS environmental predictors (discharge, water temperature, dissolved
oxygen, pH, specific conductance, turbidity) to the Riverine Pesticides sample
table (t2_pest_concs.parquet) by station and sampling date/time.

Written against dataretrieval 1.3.0 (waterdata module). Run this on a machine with internet access (needs api.waterdata.usgs.gov).

In Colab / Jupyter: paste this file into one cell and run it (nothing executes), then in a
NEW cell call, for example:
    main(["--t2", "/content/t2_pest_concs.parquet", "--outdir", "/content/out", "--sites", "3"])

From a terminal:

    pip install dataretrieval pandas pyarrow
    export API_USGS_PAT="<your key>"     # free: https://api.waterdata.usgs.gov/signup/
    python build_features.py --t2 t2_pest_concs.parquet --outdir out
    python build_features.py --t2 t2_pest_concs.parquet --outdir out --sites 3   # dry run

How each sample gets its values (first match wins, provenance is recorded in
the <variable>_source column):
  1. discrete_same_activity : field result stored under the same
                              Activity_ActivityIdentifier as the pesticide result
  2. discrete_time_match    : discrete result at the same site within +/-60 min
  3. continuous_nearest     : nearest sensor reading (+/-30 min by default)
Discharge additionally gets daily-mean features (same day, prior 3/7/30-day
means, 1-day change, site percentile), which work even where no sensor exists.

Outputs (in --outdir):
  sample_features.parquet               one row per sample (12,896 expected), ALL feature + provenance columns (QC)
  t2_pest_concs_enriched.parquet        Table 2 plus the SIX predictors:
                                        Discharge_cfs, Water_Temperature_C, Dissolved_Oxygen_mg_L,
                                        pH, Turbidity_FNU, Specific_Conductance
                                        (add --full-features for provenance/flow-history columns, --csv for a CSV)
  feature_coverage_summary.csv          % coverage per variable + complete-case counts
  feature_coverage_by_site_year.csv     % coverage per site x water year x variable
  retrieval_log.csv                     any site/parameter calls that failed
  sites_check.csv                       USGS names for the site IDs (verify these!)
  raw_cache/                            per-site pulls, so a re-run resumes
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dataretrieval import ChunkInterrupted, waterdata
from dataretrieval.exceptions import RateLimited

log = logging.getLogger("build_features")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
PCODES = {
    "00060": "Discharge_cfs",
    "00010": "Water_Temperature_C",
    "00300": "Dissolved_Oxygen_mg_L",
    "00400": "pH",
    "00095": "Specific_Conductance",  # uS/cm at 25 C; rename to ..._uS_cm if you prefer
    "63680": "Turbidity_FNU",
}
# Discrete-only helpers
DISCRETE_FALLBACK = {"00061": "Discharge_cfs"}  # instantaneous discharge at sampling time
EXTRA_DISCRETE = {"00076": "Turbidity_NTU"}      # NTU is NOT the same unit as FNU: kept separate
DISCRETE_PCODES = list(PCODES) + list(DISCRETE_FALLBACK) + list(EXTRA_DISCRETE)

# Time-zone abbreviations found in Table 2 -> fixed UTC offset in hours
TZ_OFFSET_HOURS = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5,
                   "MST": -7, "MDT": -6, "PST": -8, "PDT": -7, "UTC": 0}

# The Illinois River site (05586300) merges two physical stations (Valley City
# WY2013-2018, Florence WY2015-2022). Put the OTHER station's ID here AFTER you
# verify it in sites_check.csv, e.g. {"USGS-05586300": ["USGS-<other id>"]}.
# Left empty on purpose: a wrong ID would silently attach another river's data.
LOCATION_ALIASES: dict[str, list[str]] = {}

# The six predictors that are added to the dataset (in this column order)
SIX_FEATURES = ["Discharge_cfs", "Water_Temperature_C", "Dissolved_Oxygen_mg_L",
                "pH", "Turbidity_FNU", "Specific_Conductance"]

STUDY_START, STUDY_END = "2012-10-01", "2022-09-30"
DISCRETE_TOL = pd.Timedelta("60min")
MAX_FAILED_WINDOWS = 3  # per site, per run
UTC_NS = "datetime64[ns, UTC]"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
MAX_QUOTA_WAITS = 20        # per call; ~1 h windows, so this tolerates many hours of waiting
DEFAULT_QUOTA_WAIT = 300    # seconds, used when the server sends no Retry-After


def _quota_wait(exc) -> float:
    ra = getattr(exc, "retry_after", None)
    try:
        return min(max(float(ra), 5.0), 3700.0) if ra else float(DEFAULT_QUOTA_WAIT)
    except (TypeError, ValueError):
        return float(DEFAULT_QUOTA_WAIT)


def retry(fn, *args, tries: int = 4, **kwargs):
    """Call fn, surviving both flaky networks and the 1,000-requests/hour USGS quota.

    * 429 / 5xx in the middle of a chunked call (ChunkInterrupted): wait Retry-After (or 5 min),
      then RESUME so only the still-pending chunks are re-sent.
    * 429 on a single request (RateLimited): wait Retry-After, then re-send.
    * anything else (timeouts, ...): exponential backoff, `tries` attempts in total.
    """
    call = lambda: fn(*args, **kwargs)  # noqa: E731
    quota_waits = attempt = 0
    while True:
        try:
            return call()
        except ChunkInterrupted as exc:
            quota_waits += 1
            if quota_waits > MAX_QUOTA_WAITS:
                raise
            wait = _quota_wait(exc)
            log.warning("%s: %s interrupted (%s); waiting %.0fs then resuming (%d/%d)",
                        getattr(fn, "__name__", fn), type(exc).__name__, exc, wait,
                        quota_waits, MAX_QUOTA_WAITS)
            time.sleep(wait)
            if getattr(exc, "call", None) is not None:
                call = exc.call.resume
        except RateLimited as exc:
            quota_waits += 1
            if quota_waits > MAX_QUOTA_WAITS:
                raise
            wait = _quota_wait(exc)
            log.warning("%s: rate limited (429); waiting %.0fs (%d/%d)",
                        getattr(fn, "__name__", fn), wait, quota_waits, MAX_QUOTA_WAITS)
            time.sleep(wait)
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt >= tries:
                raise
            wait = 5 * 2 ** (attempt - 1)
            log.warning("%s failed (%s); retrying in %ss", getattr(fn, "__name__", fn), exc, wait)
            time.sleep(wait)


def chunks(seq, n):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def pick(df: pd.DataFrame, candidates: list[str], what: str) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"Could not find the {what} column (tried {candidates}). "
                   f"Columns returned: {list(df.columns)}")


def ids_for(loc: str) -> list[str]:
    return [loc] + LOCATION_ALIASES.get(loc, [])


def set_http_timeout(seconds: float) -> None:
    """The package's default read timeout is 60 s, which the Samples API can exceed."""
    try:
        import httpx
        from dataretrieval.transport.http import HTTPX_DEFAULTS
        HTTPX_DEFAULTS["timeout"] = httpx.Timeout(float(seconds), connect=15.0)
        log.info("HTTP read timeout set to %ss", seconds)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not change HTTP timeout (%s); using package default", exc)


def check_api_key() -> None:
    """Log whether a USGS API key is visible. Without one the limit is ~50 requests/hour, not 1,000."""
    import os
    if not os.environ.get("API_USGS_PAT", "").strip() and os.environ.get("USGS_API_KEY", "").strip():
        os.environ["API_USGS_PAT"] = os.environ["USGS_API_KEY"].strip()
        log.info("Copied USGS_API_KEY into API_USGS_PAT (the name the dataretrieval package reads)")
    key = os.environ.get("API_USGS_PAT", "").strip()
    if key:
        log.info("USGS API key found (%d characters): limit is ~1,000 requests/hour", len(key))
    else:
        log.warning("No API_USGS_PAT environment variable found. Unless a dataretrieval config file "
                    "supplies a key, you are limited to ~50 requests/hour. In Colab run "
                    "os.environ['API_USGS_PAT'] = '<your key>' BEFORE main([...]).")


# --------------------------------------------------------------------------
# Step 1: sample table from Table 2
# --------------------------------------------------------------------------
def build_samples(t2: pd.DataFrame) -> pd.DataFrame:
    cols = ["Pesticide_Site", "Site_Abb", "Water_Year", "Activity_ActivityIdentifier",
            "Activity_StartDate", "Activity_StartTime", "Activity_StartTimeZone"]
    s = t2[cols].drop_duplicates("Activity_ActivityIdentifier").copy()
    s = s.rename(columns={"Activity_ActivityIdentifier": "activity_id"})
    s["site_no"] = s["Pesticide_Site"].str.rsplit("_", n=1).str[-1]
    s["Location_Identifier"] = "USGS-" + s["site_no"]
    offset = s["Activity_StartTimeZone"].str.strip().map(TZ_OFFSET_HOURS)
    if offset.isna().any():
        bad = s.loc[offset.isna(), "Activity_StartTimeZone"].unique()
        raise ValueError(f"Unmapped time-zone codes: {bad}")
    local = pd.to_datetime(s["Activity_StartDate"] + " " + s["Activity_StartTime"],
                           format="%Y-%m-%d %H:%M:%S")
    s["sample_dt_utc"] = (local - pd.to_timedelta(offset, unit="h")).dt.tz_localize("UTC")
    s["sample_dt_utc"] = s["sample_dt_utc"].astype(UTC_NS)
    s["sample_date"] = pd.to_datetime(s["Activity_StartDate"])
    return s.drop(columns=["Pesticide_Site"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Step 2: discrete field results (USGS Samples API)
# --------------------------------------------------------------------------
def normalize_discrete(df: pd.DataFrame | None, primary: str) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["activity_id", "Location_Identifier", "dt_utc", "pcode", "value"])
    if df is None or df.empty:
        return empty
    val = pick(df, ["Result_Measure", "Result_ResultMeasureValue", "Result_MeasureValue"], "result value")
    act = pick(df, ["Activity_ActivityIdentifier"], "activity identifier")
    pc = pick(df, ["USGSpcode", "Result_USGSPCode"], "USGS parameter code")
    if "Activity_StartDateTime" in df.columns:
        dt = pd.to_datetime(df["Activity_StartDateTime"], utc=True, errors="coerce")
    else:
        off = df["Activity_StartTimeZone"].map(TZ_OFFSET_HOURS)
        loc_dt = pd.to_datetime(df["Activity_StartDate"] + " " + df["Activity_StartTime"],
                                format="%Y-%m-%d %H:%M:%S", errors="coerce")
        dt = (loc_dt - pd.to_timedelta(off, unit="h")).dt.tz_localize("UTC")
    out = pd.DataFrame({
        "activity_id": df[act].astype(str),
        "Location_Identifier": primary,  # aliases are folded back onto the primary ID
        "dt_utc": dt.astype(UTC_NS),
        "pcode": df[pc].astype(str).str.strip().str.zfill(5),
        "value": pd.to_numeric(df[val], errors="coerce"),
    })
    if "Result_ResultDetectionCondition" in df.columns:  # drop non-detects / qualified-out rows
        cond = df["Result_ResultDetectionCondition"].fillna("").astype(str).str.strip()
        out.loc[cond != "", "value"] = np.nan
    return out.dropna(subset=["value", "dt_utc"])


EMPTY_DISCRETE_COLS = ["activity_id", "Location_Identifier", "dt_utc", "pcode", "value"]


def concat_discrete(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate discrete frames, ignoring empties so dtypes (tz-aware UTC) survive."""
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=EMPTY_DISCRETE_COLS)
    out = pd.concat(frames, ignore_index=True)
    out["dt_utc"] = pd.to_datetime(out["dt_utc"], utc=True).astype(UTC_NS)
    return out


def date_windows(start: str, end: str, years: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    lo, last, out = pd.Timestamp(start), pd.Timestamp(end), []
    while lo <= last:
        hi = min(lo + pd.DateOffset(years=years) - pd.Timedelta(days=1), last)
        out.append((lo, hi))
        lo = hi + pd.Timedelta(days=1)
    return out


def fetch_samples_window(loc: str, lo: pd.Timestamp, hi: pd.Timestamp,
                         log_rows: list) -> tuple[pd.DataFrame, bool]:
    """One Samples request; if it fails, split the window in half and try each half."""
    try:
        df, _ = retry(waterdata.get_samples, tries=2, monitoring_location_id=ids_for(loc),
                      usgs_pcode=DISCRETE_PCODES,
                      activity_start_date_lower=lo.strftime("%Y-%m-%d"),
                      activity_start_date_upper=hi.strftime("%Y-%m-%d"),
                      profile="fullphyschem")
        return normalize_discrete(df, loc), True
    except KeyError:
        raise  # a schema surprise should stop the run, not be swallowed
    except Exception as exc:  # noqa: BLE001
        if (hi - lo).days > 400:   # 2 yr -> 1 yr, then give up on that window
            mid = (lo + (hi - lo) / 2).normalize()
            log.warning("Samples %s %s..%s failed (%s); splitting window", loc, lo.date(), hi.date(), exc)
            a, ok_a = fetch_samples_window(loc, lo, mid, log_rows)
            b, ok_b = fetch_samples_window(loc, mid + pd.Timedelta(days=1), hi, log_rows)
            return concat_discrete([a, b]), ok_a and ok_b
        log_rows.append({"site": loc, "call": f"get_samples {lo.date()}..{hi.date()}", "error": str(exc)})
        log.warning("Samples %s %s..%s gave up: %s", loc, lo.date(), hi.date(), exc)
        return pd.DataFrame(columns=EMPTY_DISCRETE_COLS), False


def get_discrete(loc: str, start: str, end: str, cache: Path, log_rows: list,
                 chunk_years: int = 2) -> pd.DataFrame:
    """Discrete results for one site, pulled in date windows and cached per window.
    A window that failed is NOT cached, so re-running the script retries only that window."""
    frames, failed = [], 0
    for lo, hi in date_windows(start, end, chunk_years):
        f = cache / f"discrete_{loc}_{lo:%Y%m%d}_{hi:%Y%m%d}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f))
            continue
        if failed >= MAX_FAILED_WINDOWS:  # circuit breaker: service is struggling, move on
            log.warning("Skipping %s %s..%s after %d failed windows (re-run to retry)",
                        loc, lo.date(), hi.date(), failed)
            continue
        df, ok = fetch_samples_window(loc, lo, hi, log_rows)
        if ok:
            df.to_parquet(f)
        else:
            failed += 1
        frames.append(df)
    return concat_discrete(frames)


def attach_discrete(samples: pd.DataFrame, disc: pd.DataFrame, feat: pd.DataFrame) -> None:
    """Fill feat[var], feat[var_source], feat[var_gap_min] from discrete results."""
    order = {}  # variable -> pcodes in priority order
    for pc, var in PCODES.items():
        order.setdefault(var, []).append(pc)
    for pc, var in DISCRETE_FALLBACK.items():
        order.setdefault(var, []).append(pc)
    for pc, var in EXTRA_DISCRETE.items():
        order.setdefault(var, []).append(pc)
        feat[var], feat[var + "_source"], feat[var + "_gap_min"] = np.nan, None, np.nan

    for var, pcs in order.items():
        for pc in pcs:
            d = disc[disc["pcode"] == pc]
            if d.empty:
                continue
            # (1) same activity
            by_act = d.groupby("activity_id")["value"].mean()
            m = samples["activity_id"].map(by_act)
            fill = feat[var].isna() & m.notna()
            feat.loc[fill, var] = m[fill]
            feat.loc[fill, var + "_source"] = "discrete_same_activity"
            feat.loc[fill, var + "_gap_min"] = 0.0
            # (2) same site, nearest in time within tolerance
            need = samples.loc[feat[var].isna(), ["Location_Identifier", "sample_dt_utc"]].copy()
            if need.empty:
                continue
            need["_row"] = need.index
            need["Location_Identifier"] = need["Location_Identifier"].astype(object)
            need = need.sort_values("sample_dt_utc")
            right = (d.groupby(["Location_Identifier", "dt_utc"], as_index=False)["value"].mean()
                     .rename(columns={"value": "_v"}).sort_values("dt_utc"))
            right["_t"] = right["dt_utc"]
            right["Location_Identifier"] = right["Location_Identifier"].astype(object)
            mm = pd.merge_asof(need, right, left_on="sample_dt_utc", right_on="dt_utc",
                               by="Location_Identifier", tolerance=DISCRETE_TOL, direction="nearest")
            mm = mm.dropna(subset=["_v"])
            if mm.empty:
                continue
            gap = (mm["sample_dt_utc"] - mm["_t"]).abs().dt.total_seconds() / 60
            feat.loc[mm["_row"].values, var] = mm["_v"].values
            feat.loc[mm["_row"].values, var + "_source"] = "discrete_time_match"
            feat.loc[mm["_row"].values, var + "_gap_min"] = gap.values


# --------------------------------------------------------------------------
# Step 3: continuous sensors (nearest reading to each sample time)
# --------------------------------------------------------------------------
def series_available(loc: str, log_rows: list) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]] | None:
    """Which parameters have a time series at this site, and over what span. None = unknown."""
    try:
        meta, _ = retry(waterdata.get_time_series_metadata, monitoring_location_id=ids_for(loc),
                        parameter_code=list(PCODES))
        if meta is None or meta.empty:
            return {}
        b = pd.to_datetime(meta[pick(meta, ["begin_utc", "begin"], "series begin")], utc=True, errors="coerce")
        e = pd.to_datetime(meta[pick(meta, ["end_utc", "end"], "series end")], utc=True, errors="coerce")
        tmp = pd.DataFrame({"pc": meta["parameter_code"].astype(str).str.zfill(5), "b": b, "e": e})
        return {pc: (g["b"].min(), g["e"].max()) for pc, g in tmp.groupby("pc")}
    except Exception as exc:  # noqa: BLE001
        log_rows.append({"site": loc, "call": "get_time_series_metadata", "error": str(exc)})
        return None


CONT_COLS = ["target_time", "time", "value", "unit", "gap_min"]


def _read_cont_cache(fnd: Path, req: Path):
    found = pd.read_parquet(fnd) if fnd.exists() else pd.DataFrame(columns=CONT_COLS)
    requested = set(pd.read_parquet(req)["target_time"]) if req.exists() else set()
    return found, requested


def get_continuous_nearest(loc: str, pc: str, targets: pd.Series, window: str,
                           cache: Path, log_rows: list) -> pd.DataFrame:
    """Nearest sensor reading for each target time, cached INCREMENTALLY: every finished chunk
    is written to disk immediately, and targets already requested (found or not) are never
    requested again. A failed chunk is not marked as requested, so a re-run retries it."""
    fnd = cache / f"cont_{loc}_{pc}_{window}.parquet"
    req = cache / f"cont_{loc}_{pc}_{window}_requested.parquet"
    found, requested = _read_cont_cache(fnd, req)
    todo = [t for t in targets.tolist() if t not in requested]
    for chunk in chunks(todo, 25):
        try:
            df, _ = retry(waterdata.get_nearest_continuous, targets=chunk,
                          monitoring_location_id=ids_for(loc), parameter_code=pc, window=window)
        except Exception as exc:  # noqa: BLE001
            log_rows.append({"site": loc, "call": f"get_nearest_continuous:{pc}", "error": str(exc)})
            log.warning("Continuous pull failed for %s %s: %s (progress kept; re-run to retry)",
                        loc, pc, exc)
            break
        if df is not None and not df.empty:
            new = pd.DataFrame({
                "target_time": pd.to_datetime(df["target_time"], utc=True).astype(UTC_NS),
                "time": pd.to_datetime(df["time"], utc=True).astype(UTC_NS),
                "value": pd.to_numeric(df["value"], errors="coerce"),
                "unit": df["unit_of_measure"] if "unit_of_measure" in df.columns else None,
            })
            new["gap_min"] = (new["time"] - new["target_time"]).abs().dt.total_seconds() / 60
            new = new.dropna(subset=["value"])
            found = pd.concat([f for f in (found, new) if not f.empty], ignore_index=True) \
                if (not found.empty or not new.empty) else found
            found = found.sort_values("gap_min").drop_duplicates("target_time")
        requested.update(chunk)
        found.to_parquet(fnd)
        pd.DataFrame({"target_time": pd.Series(sorted(requested)).astype(UTC_NS)}).to_parquet(req)
    return found


def attach_continuous(samples: pd.DataFrame, feat: pd.DataFrame, loc: str, window: str,
                      cache: Path, log_rows: list, units_seen: dict) -> None:
    avail = series_available(loc, log_rows)
    site_rows = samples.index[samples["Location_Identifier"] == loc]
    for pc, var in PCODES.items():
        span = None
        if avail is not None:
            if pc not in avail:
                continue  # no time series for this parameter at this site
            span = avail[pc]
        # only samples that discrete results did not already fill
        rows = site_rows[feat.loc[site_rows, var].isna().values]
        t = samples.loc[rows, "sample_dt_utc"]
        if span is not None and pd.notna(span[0]) and pd.notna(span[1]):
            pad = pd.Timedelta(window.replace("PT", "").lower()) if window.startswith("PT") else pd.Timedelta("1h")
            t = t[(t >= span[0] - pad) & (t <= span[1] + pad)]
        if t.empty:
            continue
        nearest = get_continuous_nearest(loc, pc, t, window, cache, log_rows)
        if nearest.empty:
            continue
        for u in nearest["unit"].dropna().unique():
            units_seen.setdefault(pc, set()).add(str(u))
        by_t = nearest.set_index("target_time")
        rows = t.index
        vals = samples.loc[rows, "sample_dt_utc"].map(by_t["value"])
        gaps = samples.loc[rows, "sample_dt_utc"].map(by_t["gap_min"])
        fill = feat.loc[rows, var].isna() & vals.notna()
        idx = fill[fill].index
        feat.loc[idx, var] = vals[idx]
        feat.loc[idx, var + "_source"] = "continuous_nearest"
        feat.loc[idx, var + "_gap_min"] = gaps[idx]


# --------------------------------------------------------------------------
# Step 4: daily-mean discharge and antecedent-flow features
# --------------------------------------------------------------------------
def get_daily_q(loc: str, start: str, end: str, cache: Path, log_rows: list) -> pd.Series:
    f = cache / f"daily_q_{loc}.parquet"
    if f.exists():
        d = pd.read_parquet(f)
        return d.set_index("date")["value"]
    lo = (pd.Timestamp(start) - pd.Timedelta(days=35)).strftime("%Y-%m-%d")
    frames, failed = [], False
    for i in ids_for(loc):  # primary first so it wins on overlapping dates
        try:
            df, _ = retry(waterdata.get_daily, monitoring_location_id=i, parameter_code="00060",
                          statistic_id="00003", time=f"{lo}/{end}")
        except Exception as exc:  # noqa: BLE001
            failed = True
            log_rows.append({"site": i, "call": "get_daily", "error": str(exc)})
            log.warning("Daily discharge failed for %s: %s (not cached; re-run to retry)", i, exc)
            continue
        if df is not None and not df.empty:
            t = pd.to_datetime(df["time"])
            if getattr(t.dt, "tz", None) is not None:
                t = t.dt.tz_localize(None)
            frames.append(pd.DataFrame({"date": t.dt.normalize(),
                                        "value": pd.to_numeric(df["value"], errors="coerce")}))
    if frames:
        d = pd.concat(frames).dropna().drop_duplicates("date", keep="first").sort_values("date")
    else:
        d = pd.DataFrame({"date": pd.to_datetime([]), "value": []})
    if not failed:
        d.to_parquet(f)
    return d.set_index("date")["value"]


def attach_daily_q(samples: pd.DataFrame, feat: pd.DataFrame, loc: str, start: str, end: str,
                   cache: Path, log_rows: list) -> None:
    q = get_daily_q(loc, start, end, cache, log_rows)
    if q.empty:
        return
    full = q.reindex(pd.date_range(q.index.min(), q.index.max(), freq="D"))
    prior = full.shift(1)  # exclude the sample day itself from "antecedent" windows
    feats = pd.DataFrame({
        "Q_daily_mean_cfs": full,
        "Q_mean_prev3d_cfs": prior.rolling(3, min_periods=2).mean(),
        "Q_mean_prev7d_cfs": prior.rolling(7, min_periods=5).mean(),
        "Q_mean_prev30d_cfs": prior.rolling(30, min_periods=20).mean(),
        "Q_change_1d_cfs": full - full.shift(1),
    })
    study = full[(full.index >= start) & (full.index <= end)].dropna()
    rows = samples.index[samples["Location_Identifier"] == loc]
    dates = samples.loc[rows, "sample_date"]
    for col in feats.columns:
        feat.loc[rows, col] = dates.map(feats[col]).values
    if len(study) > 0:
        sv = np.sort(study.values)
        feat.loc[rows, "Q_percentile_site"] = (
            np.searchsorted(sv, feat.loc[rows, "Q_daily_mean_cfs"].astype(float).values, side="right") / len(sv)
        )
        feat.loc[rows[feat.loc[rows, "Q_daily_mean_cfs"].isna()], "Q_percentile_site"] = np.nan


# --------------------------------------------------------------------------
# Step 5: site check + coverage reporting
# --------------------------------------------------------------------------
def check_sites(locs: list[str], outdir: Path) -> None:
    frames = []
    for chunk in chunks(locs, 40):
        try:
            df, _ = retry(waterdata.get_monitoring_locations, monitoring_location_id=chunk, skip_geometry=True)
            frames.append(df)
        except Exception as exc:  # noqa: BLE001
            log.warning("Site check failed: %s", exc)
    if not frames:
        return
    sites = pd.concat(frames, ignore_index=True)
    # the package renames the raw "id" column to "monitoring_location_id"
    id_col = "monitoring_location_id" if "monitoring_location_id" in sites.columns else "id"
    keep = [c for c in [id_col, "monitoring_location_name", "state_name", "drainage_area",
                        "time_zone_abbreviation"] if c in sites.columns]
    sites[keep].to_csv(outdir / "sites_check.csv", index=False)
    found = set(sites[id_col]) if id_col in sites.columns else set()
    missing = [x for x in locs if x not in found]
    log.info("Site check: %d of %d IDs found in USGS monitoring locations", len(found & set(locs)), len(locs))
    if missing:
        log.warning("IDs not found: %s", missing)
    if "USGS-05586300" in locs and not LOCATION_ALIASES:
        log.warning("USGS-05586300 (Illinois River) merges two stations. Check sites_check.csv and set "
                    "LOCATION_ALIASES so the other station's data is included.")


def coverage_reports(feat: pd.DataFrame, samples: pd.DataFrame, outdir: Path) -> None:
    vars_ = list(dict.fromkeys(list(PCODES.values()) + list(EXTRA_DISCRETE.values())))
    vars_ += ["Q_daily_mean_cfs"]
    n = len(feat)
    rows = []
    for v in vars_:
        r = {"variable": v, "n_samples": n, "n_available": int(feat[v].notna().sum()),
             "pct_available": round(100 * feat[v].notna().mean(), 1)}
        if v + "_source" in feat.columns:
            for k, c in feat[v + "_source"].value_counts().items():
                r["src_" + str(k)] = int(c)
        rows.append(r)
    q_any = feat["Discharge_cfs"].notna() | feat["Q_daily_mean_cfs"].notna()
    t2vars = ["Water_Temperature_C", "Dissolved_Oxygen_mg_L", "pH", "Specific_Conductance"]
    tier2 = q_any & feat[t2vars].notna().all(axis=1)
    tier3 = tier2 & feat["Turbidity_FNU"].notna()
    for name, mask in [("COMPLETE: discharge only", q_any),
                       ("COMPLETE: + temp, DO, pH, conductance", tier2),
                       ("COMPLETE: + turbidity (FNU)", tier3)]:
        rows.append({"variable": name, "n_samples": n, "n_available": int(mask.sum()),
                     "pct_available": round(100 * mask.mean(), 1)})
    summary = pd.DataFrame(rows)
    summary.to_csv(outdir / "feature_coverage_summary.csv", index=False)
    print("\n" + summary[["variable", "n_available", "pct_available"]].to_string(index=False))

    long = pd.concat([samples[["Site_Abb", "Water_Year"]].reset_index(drop=True),
                      feat[vars_].notna().reset_index(drop=True)], axis=1)
    by = long.groupby(["Site_Abb", "Water_Year"])[vars_].mean().mul(100).round(1).reset_index()
    by.to_csv(outdir / "feature_coverage_by_site_year.csv", index=False)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t2", required=True, help="path to t2_pest_concs.parquet")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--window", default="PT30M", help="+/- window for nearest sensor reading (ISO 8601)")
    ap.add_argument("--sites", type=int, default=None,
                    help="DRY RUN ONLY: process just the first N sites. Omit for the full 81-site dataset.")
    ap.add_argument("--site-ids", default=None,
                    help="comma-separated USGS site numbers to process, e.g. 14206950,03374100 "
                         "(default: all sites in the table)")
    ap.add_argument("--full-features", action="store_true",
                    help="also add provenance (_source, _gap_min), discharge-history and NTU columns "
                         "to the enriched table (default: only the six predictors)")
    ap.add_argument("--csv", action="store_true", help="also write t2_pest_concs_enriched.csv")
    ap.add_argument("--timeout", type=float, default=120.0, help="HTTP read timeout in seconds")
    ap.add_argument("--discrete-chunk-years", type=int, default=2,
                    help="size of each Samples request window (smaller = fewer timeouts)")
    ap.add_argument("--start", default=STUDY_START)
    ap.add_argument("--end", default=STUDY_END)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    check_api_key()
    set_http_timeout(args.timeout)
    outdir = Path(args.outdir)
    cache = outdir / "raw_cache"
    cache.mkdir(parents=True, exist_ok=True)

    t2 = pd.read_parquet(args.t2)
    n_t2 = len(t2)
    n_orig_cols = t2.shape[1]
    samples = build_samples(t2)
    locs = sorted(samples["Location_Identifier"].unique())
    t2_loc = "USGS-" + t2["Pesticide_Site"].str.rsplit("_", n=1).str[-1]
    if args.site_ids:
        wanted = ["USGS-" + x.strip().replace("USGS-", "").zfill(8)   # restore leading zeros
                  for x in args.site_ids.split(",") if x.strip()]
        unknown = [w for w in wanted if w not in locs]
        if unknown:
            raise ValueError(f"Site IDs not in the table: {unknown}")
        locs = sorted(wanted)
    if args.sites:
        locs = locs[: args.sites]
    if args.site_ids or args.sites:
        samples = samples[samples["Location_Identifier"].isin(locs)].reset_index(drop=True)
        t2 = t2[t2_loc.isin(locs)]
    log.info("%d samples at %d sites (%s)", len(samples), len(locs),
             "DRY RUN" if args.sites else "FULL RUN")
    if not args.sites:
        log.info("Full run makes thousands of API calls; the USGS key limit is ~1,000/hour, so expect "
                 "waits for the rate limit. Leave it running; progress is cached in %s and a re-run resumes.",
                 outdir / "raw_cache")
    check_sites(locs, outdir)

    log_rows: list = []
    units_seen: dict = {}
    feat = pd.DataFrame(index=samples.index)
    for pc, var in PCODES.items():
        feat[var], feat[var + "_source"], feat[var + "_gap_min"] = np.nan, None, np.nan
    for c in ["Q_daily_mean_cfs", "Q_mean_prev3d_cfs", "Q_mean_prev7d_cfs", "Q_mean_prev30d_cfs",
              "Q_change_1d_cfs", "Q_percentile_site"]:
        feat[c] = np.nan

    # 2) discrete field results (same activity, then time match)
    disc = concat_discrete([get_discrete(l, args.start, args.end, cache, log_rows,
                                         args.discrete_chunk_years) for l in locs])
    log.info("Discrete results retrieved: %d rows", len(disc))
    attach_discrete(samples, disc, feat)

    # 3) continuous sensors + 4) daily discharge, site by site
    for i, loc in enumerate(locs, 1):
        log.info("[%d/%d] %s", i, len(locs), loc)
        attach_continuous(samples, feat, loc, args.window, cache, log_rows, units_seen)
        attach_daily_q(samples, feat, loc, args.start, args.end, cache, log_rows)

    # Discharge: where no instantaneous value exists, use the daily mean for the sample date
    miss = feat["Discharge_cfs"].isna() & feat["Q_daily_mean_cfs"].notna()
    feat.loc[miss, "Discharge_cfs"] = feat.loc[miss, "Q_daily_mean_cfs"]
    feat.loc[miss, "Discharge_cfs_source"] = "daily_mean"
    log.info("Discharge filled from the daily mean for %d samples", int(miss.sum()))

    # 5) outputs
    keys = samples[["activity_id", "Location_Identifier", "Site_Abb", "Water_Year", "sample_dt_utc"]]
    sample_features = pd.concat([keys, feat], axis=1)
    sample_features.to_parquet(outdir / "sample_features.parquet", index=False)

    add = (feat if args.full_features else feat[SIX_FEATURES]).copy()
    add.insert(0, "Activity_ActivityIdentifier", samples["activity_id"].values)
    enriched = t2.merge(add, on="Activity_ActivityIdentifier", how="left", validate="many_to_one")
    assert len(enriched) == len(t2), "row count changed during merge"
    enriched.to_parquet(outdir / "t2_pest_concs_enriched.parquet", index=False)
    if args.csv:
        enriched.to_csv(outdir / "t2_pest_concs_enriched.csv", index=False)
    log.info("Enriched table: %d rows x %d columns (%d added)", len(enriched), enriched.shape[1],
             enriched.shape[1] - n_orig_cols)

    coverage_reports(feat, samples, outdir)
    pd.DataFrame(log_rows).to_csv(outdir / "retrieval_log.csv", index=False)
    if units_seen:
        print("\nUnits reported by continuous series:", {k: sorted(v) for k, v in units_seen.items()})
        print("Check these before modeling (e.g. discharge should be ft^3/s, temperature degC).")
    log.info("Done. %d failed calls (see retrieval_log.csv).", len(log_rows))


def _in_notebook() -> bool:
    import sys
    return "ipykernel" in sys.modules or "google.colab" in sys.modules


if __name__ == "__main__" and not _in_notebook():
    main()  # terminal use; in Colab/Jupyter call main([...]) from a separate cell
