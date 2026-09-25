from __future__ import annotations

import os
import time
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from dataretrieval import waterdata, ChunkInterrupted
from dataretrieval.exceptions import RateLimited


# ============================================================
# 1. CONFIGURATION
# ============================================================

T2_FILE = "t2_pest_concs.parquet"
T1_FILE = "t1_site_info.csv"

OUTDIR = Path("USGS_ENV_ENRICHED")
CACHE = OUTDIR / "raw_cache"

OUTDIR.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# Six environmental variables
PCODES = {
    "00060": "Discharge_cfs",
    "00010": "Water_Temperature_C",
    "00300": "Dissolved_Oxygen_mg_L",
    "00400": "pH",
    "00095": "Specific_Conductance_uScm",
    "63680": "Turbidity_FNU",
}

# Some discrete records use 00061 for instantaneous discharge.
DISCRETE_FALLBACK = {
    "00061": "Discharge_cfs"
}

# Keep NTU separate. Do NOT substitute it for FNU.
EXTRA_DISCRETE = {
    "00076": "Turbidity_NTU"
}

DISCRETE_PCODES = (
    list(PCODES.keys())
    + list(DISCRETE_FALLBACK.keys())
    + list(EXTRA_DISCRETE.keys())
)

SIX_FEATURES = [
    "Discharge_cfs",
    "Water_Temperature_C",
    "Dissolved_Oxygen_mg_L",
    "pH",
    "Specific_Conductance_uScm",
    "Turbidity_FNU",
]

# Exact fixed offsets represented by the abbreviations stored in t2.
TZ_OFFSET_HOURS = {
    "EST": -5,
    "EDT": -4,
    "CST": -6,
    "CDT": -5,
    "MST": -7,
    "MDT": -6,
    "PST": -8,
    "PDT": -7,
    "UTC": 0,
    "GMT": 0,
}

CONTINUOUS_WINDOW = "PT30M"
DISCRETE_TOLERANCE = pd.Timedelta("60min")

# Table 2 covers Water Years 2013-2022.
STUDY_START = "2012-10-01"
STUDY_END   = "2022-09-30"

MAX_QUOTA_WAITS = 20
DEFAULT_QUOTA_WAIT = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("USGS_environment")


# ============================================================
# 2. RETRY / API HELPERS
# ============================================================

def quota_wait(exc):
    retry_after = getattr(exc, "retry_after", None)

    try:
        if retry_after:
            return min(max(float(retry_after), 5.0), 3700.0)
    except Exception:
        pass

    return float(DEFAULT_QUOTA_WAIT)


def retry(fn, *args, tries=4, **kwargs):

    call = lambda: fn(*args, **kwargs)

    quota_waits = 0
    attempt = 0

    while True:

        try:
            return call()

        except ChunkInterrupted as exc:

            quota_waits += 1

            if quota_waits > MAX_QUOTA_WAITS:
                raise

            wait = quota_wait(exc)

            log.warning(
                "Chunk interrupted. Waiting %.0f seconds.",
                wait
            )

            time.sleep(wait)

            if getattr(exc, "call", None) is not None:
                call = exc.call.resume

        except RateLimited as exc:

            quota_waits += 1

            if quota_waits > MAX_QUOTA_WAITS:
                raise

            wait = quota_wait(exc)

            log.warning(
                "Rate limited. Waiting %.0f seconds.",
                wait
            )

            time.sleep(wait)

        except Exception as exc:

            attempt += 1

            if attempt >= tries:
                raise

            wait = 5 * (2 ** (attempt - 1))

            log.warning(
                "%s failed: %s. Retry in %d sec.",
                getattr(fn, "__name__", str(fn)),
                exc,
                wait
            )

            time.sleep(wait)


def pick(df, candidates, description):

    for c in candidates:
        if c in df.columns:
            return c

    raise KeyError(
        f"Could not identify {description}. "
        f"Tried {candidates}. "
        f"Returned columns = {list(df.columns)}"
    )


def chunks(seq, n):

    seq = list(seq)

    for i in range(0, len(seq), n):
        yield seq[i:i+n]


# ============================================================
# 3. LOAD ORIGINAL FILES
# ============================================================

print("Reading pesticide dataset...")

t2_original = pd.read_parquet(T2_FILE)

# Preserve original row order explicitly.
t2_original = t2_original.reset_index(drop=True)
t2_original["_original_row"] = np.arange(len(t2_original))

original_columns = [
    c for c in t2_original.columns
    if c != "_original_row"
]

print("t2 rows:", f"{len(t2_original):,}")
print("t2 columns:", len(original_columns))


print("\nReading site metadata...")

t1 = pd.read_csv(
    T1_FILE,
    dtype={"Location_Identifier": str}
)

required_t1 = [
    "Location_Identifier",
    "station_nm",
    "Site_Abb"
]

missing = [c for c in required_t1 if c not in t1.columns]

if missing:
    raise ValueError(
        f"Missing required t1 columns: {missing}"
    )

# Preserve IDs exactly as strings.
t1["Location_Identifier"] = (
    t1["Location_Identifier"]
    .astype(str)
    .str.strip()
)

print("t1 physical-site rows:", len(t1))
print(
    "Unique Location_Identifier:",
    t1["Location_Identifier"].nunique()
)


# ============================================================
# 4. VALIDATE t2 STRUCTURE
# ============================================================

required_t2 = [
    "Pesticide_Site",
    "Site_Abb",
    "Water_Year",
    "Activity_ActivityIdentifier",
    "Activity_StartDate",
    "Activity_StartTime",
    "Activity_StartTimeZone",
]

missing = [
    c for c in required_t2
    if c not in t2_original.columns
]

if missing:
    raise ValueError(
        f"Missing required t2 columns: {missing}"
    )


print("\nDate range:")
print(
    t2_original["Activity_StartDate"].min(),
    "to",
    t2_original["Activity_StartDate"].max()
)

print("\nWater years:")
print(
    t2_original["Water_Year"].min(),
    "to",
    t2_original["Water_Year"].max()
)

print("\nTime-zone codes:")
print(
    t2_original["Activity_StartTimeZone"]
    .value_counts(dropna=False)
)

print(
    "\nMissing sample times:",
    t2_original["Activity_StartTime"].isna().sum()
)


# ============================================================
# 5. CHECK ACTIVITY ID CONSISTENCY
# ============================================================

activity_check = (
    t2_original
    .groupby("Activity_ActivityIdentifier", dropna=False)
    .agg(
        n_site=("Site_Abb", "nunique"),
        n_date=("Activity_StartDate", "nunique"),
        n_time=("Activity_StartTime", "nunique"),
        n_tz=("Activity_StartTimeZone", "nunique")
    )
)

conflicting_activities = activity_check[
    (activity_check["n_site"] > 1) |
    (activity_check["n_date"] > 1) |
    (activity_check["n_time"] > 1) |
    (activity_check["n_tz"] > 1)
]

print(
    "\nUnique pesticide sampling activities:",
    f"{t2_original['Activity_ActivityIdentifier'].nunique():,}"
)

print(
    "Conflicting Activity IDs:",
    len(conflicting_activities)
)

if len(conflicting_activities) > 0:

    conflicting_activities.to_csv(
        OUTDIR / "conflicting_activity_ids.csv"
    )

    raise ValueError(
        "Some Activity IDs correspond to multiple "
        "site/date/time combinations. "
        "See conflicting_activity_ids.csv."
    )


# ============================================================
# 6. BUILD ONE ROW PER PESTICIDE SAMPLING EVENT
# ============================================================

sample_cols = [
    "Pesticide_Site",
    "Site_Abb",
    "Water_Year",
    "Activity_ActivityIdentifier",
    "Activity_StartDate",
    "Activity_StartTime",
    "Activity_StartTimeZone",
]

samples = (
    t2_original[sample_cols]
    .drop_duplicates("Activity_ActivityIdentifier")
    .copy()
)

samples = samples.rename(
    columns={
        "Activity_ActivityIdentifier": "activity_id"
    }
)

samples["Activity_StartDate"] = (
    samples["Activity_StartDate"]
    .astype(str)
    .str.strip()
)

samples["Activity_StartTime"] = (
    samples["Activity_StartTime"]
    .astype("string")
    .str.strip()
)

samples["Activity_StartTimeZone"] = (
    samples["Activity_StartTimeZone"]
    .astype("string")
    .str.strip()
)


# ============================================================
# 7. MAP t2 SITES TO t1 SITE METADATA
# ============================================================

# First derive the location ID encoded in Pesticide_Site.
# This provides a strong direct mapping for most sites.
samples["_site_no_from_t2"] = (
    samples["Pesticide_Site"]
    .astype(str)
    .str.rsplit("_", n=1)
    .str[-1]
    .str.strip()
)

samples["_location_from_t2"] = (
    "USGS-" + samples["_site_no_from_t2"]
)

known_locations = set(
    t1["Location_Identifier"].dropna()
)

samples["Location_Identifier"] = (
    samples["_location_from_t2"]
    .where(
        samples["_location_from_t2"].isin(
            known_locations
        )
    )
)


# For unresolved records, try Site_Abb only when it maps
# unambiguously to ONE physical location.

siteabb_map = (
    t1.groupby("Site_Abb")["Location_Identifier"]
    .agg(lambda x: list(pd.unique(x.dropna())))
    .to_dict()
)


def unique_siteabb_location(site_abb):

    values = siteabb_map.get(site_abb, [])

    if len(values) == 1:
        return values[0]

    return None


missing_loc = samples["Location_Identifier"].isna()

samples.loc[
    missing_loc,
    "Location_Identifier"
] = samples.loc[
    missing_loc,
    "Site_Abb"
].map(unique_siteabb_location)


# Keep track of ambiguous analytical sites.
ambiguous_siteabb = {
    k: v
    for k, v in siteabb_map.items()
    if len(v) > 1
}

print(
    "\nSite_Abb values mapping to >1 physical station:",
    len(ambiguous_siteabb)
)

for k, v in ambiguous_siteabb.items():
    print(k, "->", v)


unresolved = samples[
    samples["Location_Identifier"].isna()
]

print(
    "\nUnresolved sample activities:",
    len(unresolved)
)

if len(unresolved):

    unresolved.to_csv(
        OUTDIR / "unresolved_site_mapping.csv",
        index=False
    )

    print(
        "WARNING: unresolved sites were saved to "
        "unresolved_site_mapping.csv"
    )


# ============================================================
# 8. PHYSICAL SITE ALIASES
# ============================================================

# Some analytical sites can represent more than one physical
# monitoring location.
#
# Construct aliases automatically from t1 only when t2's primary
# location is one of the physical stations represented by the
# same Site_Abb.

LOCATION_ALIASES = {}

for site_abb, locations in ambiguous_siteabb.items():

    primary_values = (
        samples.loc[
            samples["Site_Abb"] == site_abb,
            "Location_Identifier"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    for primary in primary_values:

        aliases = [
            x for x in locations
            if x != primary
        ]

        if aliases:
            LOCATION_ALIASES[primary] = aliases


print("\nPhysical-station aliases:")

if LOCATION_ALIASES:
    for k, v in LOCATION_ALIASES.items():
        print(k, "->", v)
else:
    print("None")


def ids_for(location):

    if pd.isna(location):
        return []

    return [
        location,
        *LOCATION_ALIASES.get(location, [])
    ]


# ============================================================
# 9. BUILD EXACT SAMPLE TIMESTAMP FROM t2
# ============================================================

offset = (
    samples["Activity_StartTimeZone"]
    .map(TZ_OFFSET_HOURS)
)

unknown_tz = (
    samples.loc[
        samples["Activity_StartTimeZone"].notna()
        & offset.isna(),
        "Activity_StartTimeZone"
    ]
    .unique()
)

if len(unknown_tz):

    raise ValueError(
        f"Unmapped t2 time-zone codes: {unknown_tz}"
    )


# IMPORTANT:
# Missing time stays missing.
# We DO NOT invent 12:00 or 00:00.

valid_time = (
    samples["Activity_StartTime"].notna()
    &
    samples["Activity_StartTime"].ne("")
    &
    samples["Activity_StartTime"].ne("<NA>")
)

local_datetime_text = (
    samples["Activity_StartDate"]
    + " "
    + samples["Activity_StartTime"].fillna("")
)

local_dt = pd.to_datetime(
    local_datetime_text,
    format="%Y-%m-%d %H:%M:%S",
    errors="coerce"
)

samples["sample_dt_utc"] = pd.NaT

good = (
    valid_time
    & local_dt.notna()
    & offset.notna()
)

converted = (
    local_dt.loc[good]
    -
    pd.to_timedelta(
        offset.loc[good],
        unit="h"
    )
)

samples.loc[
    good,
    "sample_dt_utc"
] = converted.values

samples["sample_dt_utc"] = pd.to_datetime(
    samples["sample_dt_utc"],
    utc=True
)

# Daily matching must use original t2 date.
samples["sample_date"] = pd.to_datetime(
    samples["Activity_StartDate"],
    errors="coerce"
).dt.normalize()


print(
    "\nActivities with valid exact sampling timestamp:",
    f"{samples['sample_dt_utc'].notna().sum():,}",
    "/",
    f"{len(samples):,}"
)

print(
    "Activities without usable sampling time:",
    f"{samples['sample_dt_utc'].isna().sum():,}"
)


# ============================================================
# 10. INITIALIZE FEATURE TABLE
# ============================================================

feat = pd.DataFrame(
    index=samples.index
)

all_vars = list(
    dict.fromkeys(
        list(PCODES.values())
        + list(EXTRA_DISCRETE.values())
    )
)

for var in all_vars:

    feat[var] = np.nan
    feat[var + "_source"] = None
    feat[var + "_gap_min"] = np.nan
    feat[var + "_matched_time_utc"] = pd.NaT
    feat[var + "_n_values"] = np.nan


for c in [
    "Q_daily_mean_cfs",
    "Q_mean_prev3d_cfs",
    "Q_mean_prev7d_cfs",
    "Q_mean_prev30d_cfs",
    "Q_change_1d_cfs",
    "Q_percentile_site",
]:
    feat[c] = np.nan


# ============================================================
# 11. NORMALIZE DISCRETE USGS RESULTS
# ============================================================

EMPTY_DISCRETE = pd.DataFrame(
    columns=[
        "activity_id",
        "Location_Identifier",
        "dt_utc",
        "pcode",
        "value"
    ]
)


def normalize_discrete(df, primary_location):

    if df is None or df.empty:
        return EMPTY_DISCRETE.copy()

    value_col = pick(
        df,
        [
            "Result_Measure",
            "Result_ResultMeasureValue",
            "Result_MeasureValue"
        ],
        "result value"
    )

    activity_col = pick(
        df,
        ["Activity_ActivityIdentifier"],
        "activity identifier"
    )

    pcode_col = pick(
        df,
        [
            "USGSpcode",
            "Result_USGSPCode"
        ],
        "parameter code"
    )

    # Actual monitoring-location column if available.
    loc_col = None

    for candidate in [
        "MonitoringLocationIdentifier",
        "MonitoringLocation_Identifier",
        "Location_Identifier"
    ]:
        if candidate in df.columns:
            loc_col = candidate
            break


    if "Activity_StartDateTime" in df.columns:

        dt = pd.to_datetime(
            df["Activity_StartDateTime"],
            utc=True,
            errors="coerce"
        )

    else:

        tz = (
            df["Activity_StartTimeZone"]
            .astype("string")
            .str.strip()
            .map(TZ_OFFSET_HOURS)
        )

        local = pd.to_datetime(
            df["Activity_StartDate"].astype(str)
            + " "
            + df["Activity_StartTime"].astype(str),
            errors="coerce"
        )

        dt = (
            local
            -
            pd.to_timedelta(tz, unit="h")
        )

        dt = pd.to_datetime(
            dt,
            utc=True
        )


    if loc_col is not None:

        raw_location = (
            df[loc_col]
            .astype(str)
            .str.strip()
        )

        # Fold alias physical stations onto analytical primary
        # station so matching works at the analytical-site level.
        alias_to_primary = {}

        for primary, aliases in LOCATION_ALIASES.items():

            alias_to_primary[primary] = primary

            for alias in aliases:
                alias_to_primary[alias] = primary

        locations = raw_location.map(
            alias_to_primary
        ).fillna(raw_location)

    else:
        locations = pd.Series(
            primary_location,
            index=df.index
        )


    out = pd.DataFrame({
        "activity_id":
            df[activity_col].astype(str),

        "Location_Identifier":
            locations,

        "dt_utc":
            pd.to_datetime(
                dt,
                utc=True,
                errors="coerce"
            ),

        "pcode":
            df[pcode_col]
            .astype(str)
            .str.strip()
            .str.zfill(5),

        "value":
            pd.to_numeric(
                df[value_col],
                errors="coerce"
            ),
    })


    # Qualified/non-detect discrete environmental result:
    # do not treat as ordinary numeric environmental value.
    if "Result_ResultDetectionCondition" in df.columns:

        condition = (
            df["Result_ResultDetectionCondition"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        out.loc[
            condition != "",
            "value"
        ] = np.nan


    return out.dropna(
        subset=["value", "dt_utc"]
    )


def concat_discrete(frames):

    frames = [
        f for f in frames
        if f is not None and not f.empty
    ]

    if not frames:
        return EMPTY_DISCRETE.copy()

    result = pd.concat(
        frames,
        ignore_index=True
    )

    result["dt_utc"] = pd.to_datetime(
        result["dt_utc"],
        utc=True
    )

    return result


# ============================================================
# 12. DISCRETE DOWNLOAD WINDOWS
# ============================================================

def date_windows(start, end, years=2):

    lo = pd.Timestamp(start)
    last = pd.Timestamp(end)

    output = []

    while lo <= last:

        hi = min(
            lo + pd.DateOffset(years=years)
            - pd.Timedelta(days=1),
            last
        )

        output.append((lo, hi))

        lo = hi + pd.Timedelta(days=1)

    return output


retrieval_log = []


def get_discrete(
    primary_location,
    start,
    end,
    chunk_years=2
):

    frames = []

    for lo, hi in date_windows(
        start,
        end,
        chunk_years
    ):

        safe_id = primary_location.replace(
            "USGS-", ""
        )

        cache_file = (
            CACHE
            /
            f"discrete_{safe_id}_{lo:%Y%m%d}_{hi:%Y%m%d}.parquet"
        )

        if cache_file.exists():

            frames.append(
                pd.read_parquet(cache_file)
            )

            continue


        print(
            "Discrete:",
            primary_location,
            lo.date(),
            "to",
            hi.date()
        )

        try:

            df, _ = retry(
                waterdata.get_samples,
                tries=3,
                monitoring_location_id=
                    ids_for(primary_location),
                usgs_pcode=DISCRETE_PCODES,
                activity_start_date_lower=
                    lo.strftime("%Y-%m-%d"),
                activity_start_date_upper=
                    hi.strftime("%Y-%m-%d"),
                profile="fullphyschem"
            )

            normalized = normalize_discrete(
                df,
                primary_location
            )

            normalized.to_parquet(
                cache_file,
                index=False
            )

            frames.append(normalized)

        except Exception as exc:

            retrieval_log.append({
                "site": primary_location,
                "call": "get_samples",
                "start": str(lo.date()),
                "end": str(hi.date()),
                "error": str(exc)
            })

            log.warning(
                "Discrete failed %s %s..%s: %s",
                primary_location,
                lo.date(),
                hi.date(),
                exc
            )

    return concat_discrete(frames)


# ============================================================
# 13. ATTACH DISCRETE VALUES
# ============================================================

def attach_discrete(samples, discrete, feat):

    priority = {}

    for pc, var in PCODES.items():
        priority.setdefault(
            var, []
        ).append(pc)

    for pc, var in DISCRETE_FALLBACK.items():
        priority.setdefault(
            var, []
        ).append(pc)

    for pc, var in EXTRA_DISCRETE.items():
        priority.setdefault(
            var, []
        ).append(pc)


    for var, pcodes in priority.items():

        for pcode in pcodes:

            d = discrete[
                discrete["pcode"] == pcode
            ].copy()

            if d.empty:
                continue


            # ---------------------------------------------
            # Priority 1: EXACT SAME ACTIVITY
            # ---------------------------------------------

            stats = (
                d.groupby("activity_id")["value"]
                .agg(["mean", "count"])
            )

            m = samples["activity_id"].map(
                stats["mean"]
            )

            n = samples["activity_id"].map(
                stats["count"]
            )

            fill = (
                feat[var].isna()
                & m.notna()
            )

            feat.loc[
                fill,
                var
            ] = m[fill]

            feat.loc[
                fill,
                var + "_source"
            ] = "discrete_same_activity"

            feat.loc[
                fill,
                var + "_gap_min"
            ] = 0.0

            feat.loc[
                fill,
                var + "_n_values"
            ] = n[fill]


            # ---------------------------------------------
            # Priority 2: SAME SITE +/-60 MIN
            # ---------------------------------------------

            need_mask = (
                feat[var].isna()
                &
                samples["sample_dt_utc"].notna()
                &
                samples["Location_Identifier"].notna()
            )

            need = samples.loc[
                need_mask,
                [
                    "Location_Identifier",
                    "sample_dt_utc"
                ]
            ].copy()

            if need.empty:
                continue

            need["_row"] = need.index

            need = need.sort_values(
                "sample_dt_utc"
            )


            right = (
                d.groupby(
                    [
                        "Location_Identifier",
                        "dt_utc"
                    ],
                    as_index=False
                )["value"]
                .agg(["mean", "count"])
                .reset_index()
                .rename(
                    columns={
                        "mean": "_value",
                        "count": "_count"
                    }
                )
            )

            right["_matched_time"] = (
                right["dt_utc"]
            )

            right = right.sort_values(
                "dt_utc"
            )


            matched = pd.merge_asof(
                need,
                right,
                left_on="sample_dt_utc",
                right_on="dt_utc",
                by="Location_Identifier",
                tolerance=DISCRETE_TOLERANCE,
                direction="nearest"
            )

            matched = matched.dropna(
                subset=["_value"]
            )

            if matched.empty:
                continue


            matched["_gap"] = (
                matched["sample_dt_utc"]
                -
                matched["_matched_time"]
            ).abs().dt.total_seconds() / 60


            idx = matched["_row"].values

            feat.loc[
                idx,
                var
            ] = matched["_value"].values

            feat.loc[
                idx,
                var + "_source"
            ] = "discrete_time_match"

            feat.loc[
                idx,
                var + "_gap_min"
            ] = matched["_gap"].values

            feat.loc[
                idx,
                var + "_matched_time_utc"
            ] = matched[
                "_matched_time"
            ].values

            feat.loc[
                idx,
                var + "_n_values"
            ] = matched["_count"].values


# ============================================================
# 14. CONTINUOUS SENSOR MATCH
# ============================================================

def get_continuous_nearest(
    location,
    pcode,
    targets,
    window=CONTINUOUS_WINDOW
):

    safe_id = location.replace(
        "USGS-", ""
    )

    cache_file = (
        CACHE
        /
        f"nearest_{safe_id}_{pcode}.parquet"
    )

    request_file = (
        CACHE
        /
        f"nearest_{safe_id}_{pcode}_requested.parquet"
    )


    if cache_file.exists():

        found = pd.read_parquet(
            cache_file
        )

        for c in [
            "target_time",
            "time"
        ]:
            if c in found:
                found[c] = pd.to_datetime(
                    found[c],
                    utc=True
                )

    else:

        found = pd.DataFrame(
            columns=[
                "target_time",
                "time",
                "value",
                "unit",
                "gap_min"
            ]
        )


    if request_file.exists():

        requested_df = pd.read_parquet(
            request_file
        )

        requested = set(
            pd.to_datetime(
                requested_df["target_time"],
                utc=True
            )
        )

    else:
        requested = set()


    target_values = (
        pd.to_datetime(
            targets.dropna().unique(),
            utc=True
        )
    )

    todo = [
        t
        for t in target_values
        if t not in requested
    ]


    for batch in chunks(todo, 25):

        try:

            df, _ = retry(
                waterdata.get_nearest_continuous,
                targets=list(batch),
                monitoring_location_id=
                    ids_for(location),
                parameter_code=pcode,
                window=window
            )

        except Exception as exc:

            retrieval_log.append({
                "site": location,
                "call":
                    f"get_nearest_continuous_{pcode}",
                "error": str(exc)
            })

            log.warning(
                "Continuous failed %s %s: %s",
                location,
                pcode,
                exc
            )

            # Do NOT mark failed requests as completed.
            break


        if df is not None and not df.empty:

            new = pd.DataFrame({
                "target_time":
                    pd.to_datetime(
                        df["target_time"],
                        utc=True
                    ),

                "time":
                    pd.to_datetime(
                        df["time"],
                        utc=True
                    ),

                "value":
                    pd.to_numeric(
                        df["value"],
                        errors="coerce"
                    ),

                "unit":
                    (
                        df["unit_of_measure"]
                        if "unit_of_measure"
                        in df.columns
                        else None
                    )
            })


            new["gap_min"] = (
                new["time"]
                -
                new["target_time"]
            ).abs().dt.total_seconds() / 60


            new = new.dropna(
                subset=["value"]
            )


            found = pd.concat(
                [found, new],
                ignore_index=True
            )


            found = (
                found
                .sort_values("gap_min")
                .drop_duplicates(
                    "target_time",
                    keep="first"
                )
            )


        requested.update(batch)


        found.to_parquet(
            cache_file,
            index=False
        )

        pd.DataFrame({
            "target_time":
                pd.Series(
                    list(requested),
                    dtype="datetime64[ns, UTC]"
                )
        }).to_parquet(
            request_file,
            index=False
        )


    return found


def attach_continuous(
    samples,
    feat,
    location
):

    site_rows = samples.index[
        samples["Location_Identifier"]
        == location
    ]


    for pcode, var in PCODES.items():

        need = site_rows[
            feat.loc[
                site_rows,
                var
            ].isna().values
        ]

        need = [
            i for i in need
            if pd.notna(
                samples.loc[
                    i,
                    "sample_dt_utc"
                ]
            )
        ]

        if not need:
            continue


        targets = samples.loc[
            need,
            "sample_dt_utc"
        ]


        nearest = get_continuous_nearest(
            location,
            pcode,
            targets
        )

        if nearest.empty:
            continue


        nearest["target_time"] = pd.to_datetime(
            nearest["target_time"],
            utc=True
        )

        nearest = (
            nearest
            .sort_values("gap_min")
            .drop_duplicates(
                "target_time",
                keep="first"
            )
            .set_index("target_time")
        )


        for row in need:

            target = samples.loc[
                row,
                "sample_dt_utc"
            ]

            if target not in nearest.index:
                continue

            rec = nearest.loc[target]

            feat.loc[
                row,
                var
            ] = rec["value"]

            feat.loc[
                row,
                var + "_source"
            ] = "continuous_nearest_30min"

            feat.loc[
                row,
                var + "_gap_min"
            ] = rec["gap_min"]

            feat.loc[
                row,
                var + "_matched_time_utc"
            ] = rec["time"]

            feat.loc[
                row,
                var + "_n_values"
            ] = 1


# ============================================================
# 15. DAILY DISCHARGE
# ============================================================

def get_daily_q(
    location,
    start=STUDY_START,
    end=STUDY_END
):

    safe_id = location.replace(
        "USGS-", ""
    )

    cache_file = (
        CACHE
        /
        f"daily_Q_{safe_id}.parquet"
    )


    if cache_file.exists():

        d = pd.read_parquet(
            cache_file
        )

        d["date"] = pd.to_datetime(
            d["date"]
        )

        return d.set_index(
            "date"
        )["value"]


    # Need 35 preceding days for 30-day history.
    lower = (
        pd.Timestamp(start)
        -
        pd.Timedelta(days=35)
    ).strftime("%Y-%m-%d")


    frames = []


    for station in ids_for(location):

        try:

            df, _ = retry(
                waterdata.get_daily,
                monitoring_location_id=station,
                parameter_code="00060",
                statistic_id="00003",
                time=f"{lower}/{end}"
            )

        except Exception as exc:

            retrieval_log.append({
                "site": station,
                "call": "daily_discharge",
                "error": str(exc)
            })

            continue


        if df is None or df.empty:
            continue


        dates = pd.to_datetime(
            df["time"],
            errors="coerce"
        )

        if getattr(
            dates.dt,
            "tz",
            None
        ) is not None:

            dates = dates.dt.tz_localize(
                None
            )


        temp = pd.DataFrame({
            "date":
                dates.dt.normalize(),

            "value":
                pd.to_numeric(
                    df["value"],
                    errors="coerce"
                ),

            "_station":
                station
        })


        # Primary station wins on overlapping dates.
        temp["_priority"] = (
            0 if station == location else 1
        )

        frames.append(temp)


    if not frames:

        return pd.Series(
            dtype=float
        )


    d = pd.concat(
        frames,
        ignore_index=True
    )

    d = (
        d.dropna(
            subset=["date", "value"]
        )
        .sort_values(
            ["date", "_priority"]
        )
        .drop_duplicates(
            "date",
            keep="first"
        )
        .sort_values("date")
    )


    d[[
        "date",
        "value"
    ]].to_parquet(
        cache_file,
        index=False
    )


    return d.set_index(
        "date"
    )["value"]


def attach_daily_q(
    samples,
    feat,
    location
):

    q = get_daily_q(
        location
    )

    if q.empty:
        return


    full_index = pd.date_range(
        q.index.min(),
        q.index.max(),
        freq="D"
    )

    full = q.reindex(
        full_index
    )


    # Previous days only.
    prior = full.shift(1)


    q_features = pd.DataFrame({
        "Q_daily_mean_cfs":
            full,

        "Q_mean_prev3d_cfs":
            prior.rolling(
                3,
                min_periods=2
            ).mean(),

        "Q_mean_prev7d_cfs":
            prior.rolling(
                7,
                min_periods=5
            ).mean(),

        "Q_mean_prev30d_cfs":
            prior.rolling(
                30,
                min_periods=20
            ).mean(),

        "Q_change_1d_cfs":
            full - full.shift(1)
    })


    site_rows = samples.index[
        samples["Location_Identifier"]
        == location
    ]

    dates = samples.loc[
        site_rows,
        "sample_date"
    ]


    for col in q_features.columns:

        feat.loc[
            site_rows,
            col
        ] = dates.map(
            q_features[col]
        ).values


    study_values = full[
        (full.index >= STUDY_START)
        &
        (full.index <= STUDY_END)
    ].dropna()


    if len(study_values):

        sorted_values = np.sort(
            study_values.values
        )

        q_sample = feat.loc[
            site_rows,
            "Q_daily_mean_cfs"
        ]

        valid = q_sample.notna()

        percentile = np.full(
            len(site_rows),
            np.nan
        )

        percentile[valid.values] = (
            np.searchsorted(
                sorted_values,
                q_sample[valid].values,
                side="right"
            )
            /
            len(sorted_values)
        )

        feat.loc[
            site_rows,
            "Q_percentile_site"
        ] = percentile


# ============================================================
# 16. DOWNLOAD DISCRETE RESULTS
# ============================================================

valid_locations = sorted(
    samples["Location_Identifier"]
    .dropna()
    .unique()
)

print(
    "\nPhysical primary locations to process:",
    len(valid_locations)
)


discrete_frames = []

for i, location in enumerate(
    valid_locations,
    start=1
):

    print(
        f"\nDiscrete site {i}/{len(valid_locations)}:",
        location
    )

    d = get_discrete(
        location,
        STUDY_START,
        STUDY_END,
        chunk_years=2
    )

    if not d.empty:
        discrete_frames.append(d)


discrete = concat_discrete(
    discrete_frames
)

print(
    "\nTotal discrete environmental results:",
    f"{len(discrete):,}"
)


# ============================================================
# 17. PRIORITY 1 + 2
# ============================================================

print(
    "\nAttaching same-activity / nearby discrete measurements..."
)

attach_discrete(
    samples,
    discrete,
    feat
)


# ============================================================
# 18. PRIORITY 3 + DAILY Q
# ============================================================

for i, location in enumerate(
    valid_locations,
    start=1
):

    print(
        f"\nSite {i}/{len(valid_locations)}:",
        location
    )

    print(
        "  Matching continuous sensor observations..."
    )

    attach_continuous(
        samples,
        feat,
        location
    )


    print(
        "  Retrieving daily discharge..."
    )

    attach_daily_q(
        samples,
        feat,
        location
    )


    # Save progress after every site.
    progress = pd.concat(
        [
            samples[
                [
                    "activity_id",
                    "Site_Abb",
                    "Location_Identifier",
                    "Activity_StartDate",
                    "Activity_StartTime",
                    "Activity_StartTimeZone",
                    "sample_dt_utc"
                ]
            ],
            feat
        ],
        axis=1
    )

    progress.to_parquet(
        OUTDIR
        /
        "sample_features_PROGRESS.parquet",
        index=False
    )


# ============================================================
# 19. DISCHARGE FALLBACK
# ============================================================

missing_q = (
    feat["Discharge_cfs"].isna()
    &
    feat["Q_daily_mean_cfs"].notna()
)

feat.loc[
    missing_q,
    "Discharge_cfs"
] = feat.loc[
    missing_q,
    "Q_daily_mean_cfs"
]

feat.loc[
    missing_q,
    "Discharge_cfs_source"
] = "daily_mean_same_sample_date"

feat.loc[
    missing_q,
    "Discharge_cfs_gap_min"
] = np.nan


print(
    "\nDischarge values filled by same-date daily mean:",
    f"{missing_q.sum():,}"
)


# ============================================================
# 20. SAVE EVENT-LEVEL QC DATASET
# ============================================================

sample_keys = samples[
    [
        "activity_id",
        "Site_Abb",
        "Location_Identifier",
        "Water_Year",
        "Activity_StartDate",
        "Activity_StartTime",
        "Activity_StartTimeZone",
        "sample_dt_utc"
    ]
].copy()


sample_features = pd.concat(
    [
        sample_keys.reset_index(drop=True),
        feat.reset_index(drop=True)
    ],
    axis=1
)


sample_features.to_parquet(
    OUTDIR
    /
    "sample_features_with_provenance.parquet",
    index=False
)


# ============================================================
# 21. MERGE SIX FEATURES BACK TO ORIGINAL t2
# ============================================================

six = feat[
    SIX_FEATURES
].copy()

six.insert(
    0,
    "Activity_ActivityIdentifier",
    samples["activity_id"].values
)


# Verify unique merge key.
assert (
    six["Activity_ActivityIdentifier"]
    .is_unique
), "Feature table does not have unique activity IDs."


enriched = t2_original.merge(
    six,
    on="Activity_ActivityIdentifier",
    how="left",
    validate="many_to_one",
    sort=False
)


# Restore exact original order.
enriched = enriched.sort_values(
    "_original_row"
).reset_index(drop=True)


# ============================================================
# 22. CRITICAL VALIDATION
# ============================================================

assert len(enriched) == len(t2_original), (
    "ERROR: row count changed during merge."
)


# Original values must remain identical.
left = (
    enriched[
        ["_original_row"] + original_columns
    ]
    .sort_values("_original_row")
    .reset_index(drop=True)
)

right = (
    t2_original[
        ["_original_row"] + original_columns
    ]
    .sort_values("_original_row")
    .reset_index(drop=True)
)

pd.testing.assert_frame_equal(
    left,
    right,
    check_dtype=True,
    check_like=False
)


print(
    "\nVALIDATION PASSED:"
)

print(
    "Original rows:",
    f"{len(t2_original):,}"
)

print(
    "Enriched rows:",
    f"{len(enriched):,}"
)

print(
    "All original columns and values preserved."
)


# Remove temporary row identifier.
enriched = enriched.drop(
    columns="_original_row"
)


# ============================================================
# 23. SAVE FINAL DATASET
# ============================================================

FINAL_PARQUET = (
    OUTDIR
    /
    "t2_pest_concs_enriched.parquet"
)

enriched.to_parquet(
    FINAL_PARQUET,
    index=False
)

print(
    "\nSaved:",
    FINAL_PARQUET
)


# CSV is optional because ~956k rows will be large.
# Uncomment if needed:
#
# enriched.to_csv(
#     OUTDIR /
#     "t2_pest_concs_enriched.csv",
#     index=False
# )


# ============================================================
# 24. COVERAGE REPORT
# ============================================================

coverage_rows = []

for variable in SIX_FEATURES:

    available = int(
        feat[variable].notna().sum()
    )

    coverage_rows.append({
        "Variable":
            variable,

        "Total_Sampling_Activities":
            len(feat),

        "Available":
            available,

        "Missing":
            len(feat) - available,

        "Coverage_pct":
            round(
                100
                * available
                / len(feat),
                2
            )
    })


coverage = pd.DataFrame(
    coverage_rows
)

coverage.to_csv(
    OUTDIR
    /
    "feature_coverage_summary.csv",
    index=False
)

print("\nFEATURE COVERAGE")
print(
    coverage.to_string(
        index=False
    )
)


# ============================================================
# 25. COVERAGE BY SOURCE
# ============================================================

source_rows = []

for variable in SIX_FEATURES:

    source_col = (
        variable
        +
        "_source"
    )

    temp = (
        feat[source_col]
        .fillna("missing")
        .value_counts()
    )

    for source, count in temp.items():

        source_rows.append({
            "Variable":
                variable,

            "Source":
                source,

            "Count":
                int(count),

            "Percent":
                round(
                    100
                    * count
                    / len(feat),
                    2
                )
        })


source_summary = pd.DataFrame(
    source_rows
)

source_summary.to_csv(
    OUTDIR
    /
    "feature_source_summary.csv",
    index=False
)


# ============================================================
# 26. TIME-GAP QC
# ============================================================

gap_rows = []

for variable in SIX_FEATURES:

    gap_col = (
        variable
        +
        "_gap_min"
    )

    values = feat[
        gap_col
    ].dropna()

    if len(values):

        gap_rows.append({
            "Variable":
                variable,

            "N":
                len(values),

            "Mean_gap_min":
                values.mean(),

            "Median_gap_min":
                values.median(),

            "Max_gap_min":
                values.max()
        })


gap_summary = pd.DataFrame(
    gap_rows
)

gap_summary.to_csv(
    OUTDIR
    /
    "time_gap_summary.csv",
    index=False
)


# ============================================================
# 27. RETRIEVAL ERRORS
# ============================================================

pd.DataFrame(
    retrieval_log
).to_csv(
    OUTDIR
    /
    "retrieval_log.csv",
    index=False
)


# ============================================================
# 28. FINAL SUMMARY
# ============================================================

print("\n======================================")
print("EXTRACTION FINISHED")
print("======================================")

print(
    "Original pesticide rows:",
    f"{len(t2_original):,}"
)

print(
    "Unique sampling activities:",
    f"{len(samples):,}"
)

print(
    "Primary locations processed:",
    len(valid_locations)
)

print(
    "Valid exact sampling timestamps:",
    f"{samples['sample_dt_utc'].notna().sum():,}"
)

print(
    "Missing/invalid sampling timestamps:",
    f"{samples['sample_dt_utc'].isna().sum():,}"
)

print(
    "\nFinal dataset:"
)

print(
    FINAL_PARQUET
)

print(
    "\nQC/provenance:"
)

print(
    OUTDIR /
    "sample_features_with_provenance.parquet"
)

print(
    "\nCoverage:"
)

print(
    OUTDIR /
    "feature_coverage_summary.csv"
)

print(
    "\nSource summary:"
)

print(
    OUTDIR /
    "feature_source_summary.csv"
)

print(
    "\nTime-gap QC:"
)

print(
    OUTDIR /
    "time_gap_summary.csv"
)

print(
    "\nRetrieval errors:"
)

print(
    OUTDIR /
    "retrieval_log.csv"
)
