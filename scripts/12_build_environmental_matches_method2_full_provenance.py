#!/usr/bin/env python3
"""
12_build_environmental_matches_method2_full_provenance.py
=========================================================

Purpose
-------
Build an activity-level environmental dataset and a complete long-format
provenance table for the six environmental variables used in the pesticide
data audit.

IMPORTANT
---------
This script does NOT introduce a new scientific matching strategy.

It preserves the Method-2 hierarchy:

    1. Discrete observation from the same sampling activity
    2. Nearest discrete observation within +/- 60 minutes
    3. Nearest continuous observation within +/- 30 minutes
    4. Daily mean discharge for the same local sampling date
       (discharge only)
    5. Missing, with an explicit reason

For every sampling activity x environmental-variable combination, the
provenance table records the matched value and, where available:

    source_station_id
    source_parameter_code
    observation_date
    observation_datetime_utc
    observation_utc_offset
    observation_timezone
    original_value
    original_unit
    standardized_value
    standardized_unit
    matching_method
    time_offset_minutes
    absolute_time_gap_minutes
    allowed_window_minutes
    aggregation_interval
    quality_flag
    retrieval_status
    missing_reason
    retrieval_date
    source_query

Outputs
-------
data/interim/method2_activity_features_full_provenance.parquet

    One row per pesticide sampling activity with the six environmental
    variables. NOTE: named "_full_provenance" to avoid colliding with
    data/interim/method2_activity_features.parquet, which
    scripts/13_build_interim_activity_features.py already builds with a
    simpler, provenance-free schema -- see the fix note at the output-
    writing section below.

data/interim/method2_environmental_matches_full_provenance.parquet

    Long provenance table with one row per
    sampling activity x environmental variable.

data/interim/method2_match_coverage_summary.csv

data/interim/method2_missing_reason_summary.csv

data/interim/method2_provenance_completeness.csv

Scientific caution
------------------
A retrieval failure is NOT interpreted as evidence that no USGS observation
exists.

Likewise, fields that are not returned by the source API are left null rather
than reconstructed by assumption.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from dataretrieval import ChunkInterrupted, waterdata
from dataretrieval.exceptions import RateLimited


# ============================================================
# 1. LOGGING
# ============================================================

log = logging.getLogger("method2_provenance")


# ============================================================
# 2. METHOD-2 CONFIGURATION
# ============================================================

PCODES = {
    "00060": "Discharge_cfs",
    "00010": "Water_Temperature_C",
    "00300": "Dissolved_Oxygen_mg_L",
    "00400": "pH",
    "00095": "Specific_Conductance_uScm",
    "63680": "Turbidity_FNU",
}

# Method-2 discrete fallback for discharge
DISCRETE_FALLBACK = {
    "00061": "Discharge_cfs"
}

DISCRETE_PCODES = list(PCODES.keys()) + list(DISCRETE_FALLBACK.keys())


STANDARD_UNIT = {
    "Discharge_cfs": "ft^3/s",
    "Water_Temperature_C": "degC",
    "Dissolved_Oxygen_mg_L": "mg/L",
    "pH": "pH units",
    "Specific_Conductance_uScm": "uS/cm",
    "Turbidity_FNU": "FNU",
}


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


# ------------------------------------------------------------
# IMPORTANT:
# The previous Method-2 run identified the Illinois River
# physical-station alias.
#
# If you have the original automatic alias-building code based
# on t1_site_info, use that instead. This mapping preserves the
# already identified relationship when t1 is not supplied.
# ------------------------------------------------------------

DEFAULT_LOCATION_ALIASES = {
    "USGS-05586300": ["USGS-05586100"]
}


DISCRETE_TOL_MIN = 60
CONTINUOUS_TOL_MIN = 30

STUDY_START = "2012-10-01"
STUDY_END = "2022-09-30"

MAX_QUOTA_WAITS = 20
DEFAULT_QUOTA_WAIT = 300

UTC_NS = "datetime64[ns, UTC]"


# ============================================================
# 3. POSSIBLE API COLUMN NAMES
# ============================================================

PROBE_STATION_COLS = [
    "Location_Identifier",
    "monitoring_location_id",
    "Activity_LocationIdentifier",
]

PROBE_UNIT_COLS = [
    "Result_MeasureUnitCode",
    "ResultMeasureUnit",
    "Result_Unit",
    "unit_of_measure",
]

PROBE_QUALITY_COLS = [
    "Result_StatusIdentifier",
    "ResultStatusIdentifier",
    "approval_status",
    "qualifier",
]


# ============================================================
# 4. GENERAL HELPERS
# ============================================================

def first_present(
    df: pd.DataFrame,
    candidates: list[str]
) -> str | None:

    for col in candidates:
        if col in df.columns:
            return col

    return None


def chunks(seq, n):

    seq = list(seq)

    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def retry(fn, *args, tries: int = 4, **kwargs):
    """
    Retry helper preserving the original Method-2 behavior.
    """

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

            raw_wait = float(
                getattr(exc, "retry_after", 0) or 0
            )

            wait = (
                min(max(raw_wait, 5.0), 3700.0)
                if raw_wait > 0
                else DEFAULT_QUOTA_WAIT
            )

            log.warning(
                "%s interrupted; waiting %.0fs "
                "then resuming (%d/%d)",
                getattr(fn, "__name__", str(fn)),
                wait,
                quota_waits,
                MAX_QUOTA_WAITS,
            )

            time.sleep(wait)

            if getattr(exc, "call", None) is not None:
                call = exc.call.resume

        except RateLimited as exc:

            quota_waits += 1

            if quota_waits > MAX_QUOTA_WAITS:
                raise

            raw_wait = float(
                getattr(exc, "retry_after", 0) or 0
            )

            wait = (
                min(max(raw_wait, 5.0), 3700.0)
                if raw_wait > 0
                else DEFAULT_QUOTA_WAIT
            )

            log.warning(
                "Rate limited; waiting %.0fs (%d/%d)",
                wait,
                quota_waits,
                MAX_QUOTA_WAITS,
            )

            time.sleep(wait)

        except Exception as exc:

            attempt += 1

            if attempt >= tries:
                raise

            wait = 5 * (2 ** (attempt - 1))

            log.warning(
                "%s failed (%s); retrying in %ss",
                getattr(fn, "__name__", str(fn)),
                exc,
                wait,
            )

            time.sleep(wait)


# ============================================================
# 5. LOCATION ALIASES
# ============================================================

LOCATION_ALIASES = DEFAULT_LOCATION_ALIASES.copy()


def ids_for(loc: str) -> list[str]:
    """
    Primary physical station followed by known aliases.
    """

    return [loc] + LOCATION_ALIASES.get(loc, [])


# ============================================================
# 6. BUILD ACTIVITY MASTER
# ============================================================

def build_samples(t2: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse pesticide-result rows to one row per sampling
    activity.

    Environmental conditions belong to the sampling activity,
    not separately to every pesticide-result row.
    """

    required = [
        "Pesticide_Site",
        "Site_Abb",
        "Activity_ActivityIdentifier",
        "Activity_StartDate",
        "Activity_StartTime",
        "Activity_StartTimeZone",
    ]

    missing = [
        c for c in required
        if c not in t2.columns
    ]

    if missing:
        raise KeyError(
            f"Missing required t2 columns: {missing}"
        )

    # --------------------------------------------------------
    # Verify Activity ID consistency before collapsing.
    # --------------------------------------------------------

    check = (
        t2.groupby("Activity_ActivityIdentifier")
        .agg(
            n_site=("Pesticide_Site", "nunique"),
            n_siteabb=("Site_Abb", "nunique"),
            n_date=("Activity_StartDate", "nunique"),
            n_time=("Activity_StartTime", "nunique"),
            n_tz=("Activity_StartTimeZone", "nunique"),
        )
    )

    conflicts = check[
        (check["n_site"] > 1)
        | (check["n_siteabb"] > 1)
        | (check["n_date"] > 1)
        | (check["n_time"] > 1)
        | (check["n_tz"] > 1)
    ]

    if not conflicts.empty:

        raise ValueError(
            f"{len(conflicts):,} Activity IDs have "
            "conflicting site/date/time information."
        )

    s = (
        t2[required]
        .drop_duplicates(
            "Activity_ActivityIdentifier"
        )
        .copy()
    )

    s = s.rename(
        columns={
            "Activity_ActivityIdentifier": "activity_id"
        }
    )

    # --------------------------------------------------------
    # Physical USGS station from Pesticide_Site
    # --------------------------------------------------------

    s["site_no"] = (
        s["Pesticide_Site"]
        .astype(str)
        .str.rsplit("_", n=1)
        .str[-1]
    )

    s["Location_Identifier"] = (
        "USGS-" + s["site_no"]
    )

    # --------------------------------------------------------
    # Original local sampling datetime
    # --------------------------------------------------------

    s["sample_datetime_local"] = pd.to_datetime(
        s["Activity_StartDate"].astype(str)
        + " "
        + s["Activity_StartTime"].astype(str),
        errors="coerce",
    )

    # --------------------------------------------------------
    # Convert to UTC using the recorded sample timezone.
    # --------------------------------------------------------

    offset = (
        s["Activity_StartTimeZone"]
        .astype(str)
        .str.strip()
        .map(TZ_OFFSET_HOURS)
    )

    bad_timezone = (
        s["Activity_StartTimeZone"].notna()
        & offset.isna()
    )

    if bad_timezone.any():

        unknown = sorted(
            s.loc[
                bad_timezone,
                "Activity_StartTimeZone"
            ]
            .dropna()
            .astype(str)
            .unique()
        )

        raise ValueError(
            f"Unknown sample timezone(s): {unknown}"
        )

    s["sample_dt_utc"] = (
        s["sample_datetime_local"]
        - pd.to_timedelta(offset, unit="h")
    )

    s["sample_dt_utc"] = (
        s["sample_dt_utc"]
        .dt.tz_localize("UTC")
        .astype(UTC_NS)
    )

    return s.reset_index(drop=True)


# ============================================================
# 7. DATE WINDOWS
# ============================================================

def date_windows(
    start: str,
    end: str,
    years: int = 2
):

    lo = pd.Timestamp(start)
    last = pd.Timestamp(end)

    output = []

    while lo <= last:

        hi = min(
            lo
            + pd.DateOffset(years=years)
            - pd.Timedelta(days=1),
            last,
        )

        output.append((lo, hi))

        lo = hi + pd.Timedelta(days=1)

    return output


# ============================================================
# 8. NORMALIZE DISCRETE DATA
# ============================================================

def normalize_discrete(
    df: pd.DataFrame | None,
    primary: str,
    diag: dict,
) -> pd.DataFrame:

    cols = [
        "activity_id",
        "station_id",
        "dt_utc",
        "utc_offset",
        "pcode",
        "original_value",
        "original_unit",
        "quality_flag",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=cols)

    val_col = first_present(
        df,
        [
            "Result_Measure",
            "Result_ResultMeasureValue",
            "Result_MeasureValue",
        ],
    )

    act_col = first_present(
        df,
        ["Activity_ActivityIdentifier"],
    )

    pc_col = first_present(
        df,
        [
            "USGSpcode",
            "Result_USGSPCode",
        ],
    )

    if (
        val_col is None
        or act_col is None
        or pc_col is None
    ):

        raise KeyError(
            "Samples API result is missing an "
            "expected column.\n"
            f"Available columns: {list(df.columns)}"
        )

    station_col = first_present(
        df,
        PROBE_STATION_COLS,
    )

    unit_col = first_present(
        df,
        PROBE_UNIT_COLS,
    )

    quality_col = first_present(
        df,
        PROBE_QUALITY_COLS,
    )

    diag["discrete_station_col"] = station_col
    diag["discrete_unit_col"] = unit_col
    diag["discrete_quality_col"] = quality_col

    # --------------------------------------------------------
    # Source observation time
    # --------------------------------------------------------

    if "Activity_StartDateTime" in df.columns:

        raw_dt = (
            df["Activity_StartDateTime"]
            .astype(str)
        )

        dt = pd.to_datetime(
            raw_dt,
            utc=True,
            errors="coerce",
        )

        utc_offset = raw_dt.str.extract(
            r"([+-]\d{2}:?\d{2}|Z)$"
        )[0]

    else:

        source_tz = (
            df["Activity_StartTimeZone"]
            .astype(str)
            .str.strip()
        )

        off = source_tz.map(
            TZ_OFFSET_HOURS
        )

        local_dt = pd.to_datetime(
            df["Activity_StartDate"].astype(str)
            + " "
            + df["Activity_StartTime"].astype(str),
            errors="coerce",
        )

        dt = (
            local_dt
            - pd.to_timedelta(off, unit="h")
        )

        dt = dt.dt.tz_localize("UTC")

        utc_offset = off.apply(
            lambda h:
                (
                    f"{'+' if h >= 0 else '-'}"
                    f"{abs(int(h)):02d}:00"
                )
                if pd.notna(h)
                else None
        )

    # --------------------------------------------------------
    # Build normalized table
    # --------------------------------------------------------

    out = pd.DataFrame({
        "activity_id":
            df[act_col].astype(str),

        "station_id":
            (
                df[station_col].astype(str)
                if station_col
                else primary
            ),

        "dt_utc":
            dt.astype(UTC_NS),

        "utc_offset":
            utc_offset.values
            if hasattr(utc_offset, "values")
            else utc_offset,

        "pcode":
            (
                df[pc_col]
                .astype(str)
                .str.strip()
                .str.zfill(5)
            ),

        "original_value":
            pd.to_numeric(
                df[val_col],
                errors="coerce",
            ),

        "original_unit":
            (
                df[unit_col]
                if unit_col
                else None
            ),

        "quality_flag":
            (
                df[quality_col]
                if quality_col
                else None
            ),
    })

    # --------------------------------------------------------
    # Environmental nondetect/qualified result handling
    # Preserve existing Method-2 behavior:
    # nonblank detection condition is not used as a numeric
    # environmental match.
    # --------------------------------------------------------

    if "Result_ResultDetectionCondition" in df.columns:

        condition = (
            df["Result_ResultDetectionCondition"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        out.loc[
            condition != "",
            "original_value"
        ] = np.nan

    return (
        out
        .dropna(
            subset=[
                "original_value",
                "dt_utc",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# 9. DISCRETE RETRIEVAL
# ============================================================

def get_discrete(
    loc: str,
    start: str,
    end: str,
    cache: Path,
    diag: dict,
):

    frames = []

    statuses = []

    query_records = []

    for lo, hi in date_windows(start, end):

        cache_file = (
            cache
            / f"discrete_{loc}_"
              f"{lo:%Y%m%d}_{hi:%Y%m%d}.parquet"
        )

        query_text = (
            f"Samples API | station={ids_for(loc)} | "
            f"pcodes={DISCRETE_PCODES} | "
            f"start={lo:%Y-%m-%d} | "
            f"end={hi:%Y-%m-%d}"
        )

        query_records.append(query_text)

        if cache_file.exists():

            frames.append(
                pd.read_parquet(cache_file)
            )

            statuses.append("cached_success")

            continue

        try:

            raw, _ = retry(
                waterdata.get_samples,
                tries=2,
                monitoring_location_id=ids_for(loc),
                usgs_pcode=DISCRETE_PCODES,
                activity_start_date_lower=lo.strftime(
                    "%Y-%m-%d"
                ),
                activity_start_date_upper=hi.strftime(
                    "%Y-%m-%d"
                ),
                profile="fullphyschem",
            )

            normalized = normalize_discrete(
                raw,
                loc,
                diag,
            )

            normalized.to_parquet(
                cache_file,
                index=False,
            )

            frames.append(normalized)

            if raw is None or raw.empty:
                statuses.append("empty_response")
            else:
                statuses.append("success")

        except Exception as exc:

            log.warning(
                "Samples retrieval failed: "
                "%s %s..%s: %s",
                loc,
                lo.date(),
                hi.date(),
                exc,
            )

            statuses.append("retrieval_failed")

    valid = [
        f
        for f in frames
        if f is not None and not f.empty
    ]

    if valid:

        data = pd.concat(
            valid,
            ignore_index=True,
        )

    else:

        data = pd.DataFrame(
            columns=[
                "activity_id",
                "station_id",
                "dt_utc",
                "utc_offset",
                "pcode",
                "original_value",
                "original_unit",
                "quality_flag",
            ]
        )

    # If ANY period failed, do not pretend the retrieval
    # was fully complete.
    if "retrieval_failed" in statuses:
        overall_status = "partial_retrieval_failure"

    elif all(
        x == "empty_response"
        for x in statuses
    ):
        overall_status = "empty_response"

    else:
        overall_status = "success"

    return (
        data,
        overall_status,
        " || ".join(query_records),
    )


# ============================================================
# 10. CONTINUOUS SERIES METADATA
# ============================================================

def series_available(loc: str):

    query_text = (
        f"Time-series metadata | "
        f"station={ids_for(loc)} | "
        f"pcodes={list(PCODES.keys())}"
    )

    try:

        meta, _ = retry(
            waterdata.get_time_series_metadata,
            monitoring_location_id=ids_for(loc),
            parameter_code=list(PCODES.keys()),
        )

        if meta is None or meta.empty:

            return (
                set(),
                "success_empty",
                query_text,
            )

        available = set(
            meta["parameter_code"]
            .astype(str)
            .str.strip()
            .str.zfill(5)
        )

        return (
            available,
            "success",
            query_text,
        )

    except Exception as exc:

        log.warning(
            "Series metadata retrieval failed "
            "for %s: %s",
            loc,
            exc,
        )

        return (
            set(),
            "retrieval_failed",
            query_text,
        )


# ============================================================
# 11. CONTINUOUS NEAREST RETRIEVAL
# ============================================================

def get_continuous_nearest(
    loc: str,
    pc: str,
    targets: pd.Series,
    cache: Path,
    diag: dict,
):

    cache_file = (
        cache
        / f"continuous_{loc}_{pc}.parquet"
    )

    query_text = (
        f"Nearest continuous API | "
        f"station={ids_for(loc)} | "
        f"pcode={pc} | "
        f"window=PT{CONTINUOUS_TOL_MIN}M"
    )

    if cache_file.exists():

        return (
            pd.read_parquet(cache_file),
            "cached_success",
            query_text,
        )

    frames = []

    retrieval_failed = False

    for target_chunk in chunks(
        targets.tolist(),
        25,
    ):

        try:

            raw, _ = retry(
                waterdata.get_nearest_continuous,
                targets=target_chunk,
                monitoring_location_id=ids_for(loc),
                parameter_code=pc,
                window=f"PT{CONTINUOUS_TOL_MIN}M",
            )

            if raw is not None and not raw.empty:
                frames.append(raw)

        except Exception as exc:

            retrieval_failed = True

            log.warning(
                "Continuous retrieval failed "
                "%s %s: %s",
                loc,
                pc,
                exc,
            )

    if not frames:

        status = (
            "retrieval_failed"
            if retrieval_failed
            else "empty_response"
        )

        return (
            pd.DataFrame(),
            status,
            query_text,
        )

    raw = pd.concat(
        frames,
        ignore_index=True,
    )

    station_col = first_present(
        raw,
        PROBE_STATION_COLS,
    )

    quality_col = first_present(
        raw,
        PROBE_QUALITY_COLS,
    )

    diag["continuous_station_col"] = (
        station_col
    )

    diag["continuous_quality_col"] = (
        quality_col
    )

    # --------------------------------------------------------
    # Preserve source timestamp and offset if exposed.
    # --------------------------------------------------------

    raw_obs_time = raw["time"].astype(str)

    obs_time = pd.to_datetime(
        raw_obs_time,
        utc=True,
        errors="coerce",
    )

    utc_offset = raw_obs_time.str.extract(
        r"([+-]\d{2}:?\d{2}|Z)$"
    )[0]

    out = pd.DataFrame({

        "target_time":
            pd.to_datetime(
                raw["target_time"],
                utc=True,
                errors="coerce",
            ).astype(UTC_NS),

        "obs_time":
            obs_time.astype(UTC_NS),

        "utc_offset":
            utc_offset,

        "original_value":
            pd.to_numeric(
                raw["value"],
                errors="coerce",
            ),

        "original_unit":
            (
                raw["unit_of_measure"]
                if "unit_of_measure" in raw.columns
                else None
            ),

        "station_id":
            (
                raw[station_col].astype(str)
                if station_col
                else loc
            ),

        "quality_flag":
            (
                raw[quality_col]
                if quality_col
                else None
            ),
    })

    out = out.dropna(
        subset=[
            "original_value",
            "obs_time",
        ]
    )

    out.to_parquet(
        cache_file,
        index=False,
    )

    status = (
        "partial_retrieval_failure"
        if retrieval_failed
        else "success"
    )

    return (
        out,
        status,
        query_text,
    )


# ============================================================
# 12. DAILY DISCHARGE
# ============================================================

def get_daily_q(
    loc: str,
    start: str,
    end: str,
    cache: Path,
    diag: dict,
):

    cache_file = (
        cache
        / f"daily_discharge_{loc}.parquet"
    )

    query_text = (
        f"Daily values API | "
        f"station={ids_for(loc)} | "
        f"pcode=00060 | statistic=00003"
    )

    if cache_file.exists():

        return (
            pd.read_parquet(cache_file),
            "cached_success",
            query_text,
        )

    lo = (
        pd.Timestamp(start)
        - pd.Timedelta(days=35)
    ).strftime("%Y-%m-%d")

    frames = []

    failures = 0

    for station_id in ids_for(loc):

        try:

            raw, _ = retry(
                waterdata.get_daily,
                monitoring_location_id=station_id,
                parameter_code="00060",
                statistic_id="00003",
                time=f"{lo}/{end}",
            )

        except Exception as exc:

            failures += 1

            log.warning(
                "Daily discharge retrieval failed "
                "%s: %s",
                station_id,
                exc,
            )

            continue

        if raw is None or raw.empty:
            continue

        quality_col = first_present(
            raw,
            PROBE_QUALITY_COLS,
        )

        diag["daily_quality_col"] = (
            quality_col
        )

        t = pd.to_datetime(
            raw["time"],
            errors="coerce",
        )

        # Daily value represents a date/aggregation period.
        # Do not invent midnight as a source observation time.
        if getattr(t.dt, "tz", None) is not None:
            t = t.dt.tz_localize(None)

        temp = pd.DataFrame({

            "observation_date":
                t.dt.normalize(),

            "original_value":
                pd.to_numeric(
                    raw["value"],
                    errors="coerce",
                ),

            "original_unit":
                (
                    raw["unit_of_measure"]
                    if "unit_of_measure" in raw.columns
                    else None
                ),

            "station_id":
                station_id,

            "quality_flag":
                (
                    raw[quality_col]
                    if quality_col
                    else None
                ),

            # Primary station has priority over alias.
            "_priority":
                0 if station_id == loc else 1,
        })

        frames.append(temp)

    if not frames:

        status = (
            "retrieval_failed"
            if failures > 0
            else "empty_response"
        )

        return (
            pd.DataFrame(),
            status,
            query_text,
        )

    daily = pd.concat(
        frames,
        ignore_index=True,
    )

    daily = (
        daily
        .dropna(
            subset=[
                "original_value",
                "observation_date",
            ]
        )
        .sort_values(
            [
                "observation_date",
                "_priority",
            ]
        )
        .drop_duplicates(
            "observation_date",
            keep="first",
        )
        .drop(columns="_priority")
        .reset_index(drop=True)
    )

    daily.to_parquet(
        cache_file,
        index=False,
    )

    status = (
        "partial_retrieval_failure"
        if failures > 0
        else "success"
    )

    return (
        daily,
        status,
        query_text,
    )


# ============================================================
# 13. CREATE ONE PROVENANCE RECORD
# ============================================================

def make_record(
    sample,
    variable,
    original_value=np.nan,
    original_unit=None,
    source_station_id=None,
    source_parameter_code=None,
    observation_date=None,
    observation_datetime_utc=pd.NaT,
    observation_utc_offset=None,
    observation_timezone=None,
    matching_method="none",
    time_offset_minutes=np.nan,
    allowed_window_minutes=np.nan,
    aggregation_interval=None,
    quality_flag=None,
    retrieval_status=None,
    missing_reason=None,
    retrieval_date=None,
    source_query=None,
):

    standard_value = (
        original_value
        if pd.notna(original_value)
        else np.nan
    )

    absolute_gap = (
        abs(float(time_offset_minutes))
        if pd.notna(time_offset_minutes)
        else np.nan
    )

    return {

        # ----------------------------------------------------
        # Sampling activity
        # ----------------------------------------------------

        "Pesticide_Site":
            sample["Pesticide_Site"],

        "Site_Abb":
            sample["Site_Abb"],

        "Activity_ActivityIdentifier":
            sample["activity_id"],

        "Activity_StartDate":
            sample["Activity_StartDate"],

        "Activity_StartTime":
            sample["Activity_StartTime"],

        "Activity_StartTimeZone":
            sample["Activity_StartTimeZone"],

        "sample_datetime_local":
            sample["sample_datetime_local"],

        "sample_datetime_utc":
            sample["sample_dt_utc"],

        "analysis_location_id":
            sample["Location_Identifier"],

        # ----------------------------------------------------
        # Environmental variable
        # ----------------------------------------------------

        "variable":
            variable,

        # ----------------------------------------------------
        # Source
        # ----------------------------------------------------

        "source_station_id":
            source_station_id,

        "source_parameter_code":
            source_parameter_code,

        "observation_date":
            observation_date,

        "observation_datetime_utc":
            observation_datetime_utc,

        "observation_utc_offset":
            observation_utc_offset,

        "observation_timezone":
            observation_timezone,

        # ----------------------------------------------------
        # Values and units
        # ----------------------------------------------------

        "original_value":
            original_value,

        "original_unit":
            original_unit,

        "standardized_value":
            standard_value,

        "standardized_unit":
            STANDARD_UNIT[variable],

        # ----------------------------------------------------
        # Matching
        # ----------------------------------------------------

        "matching_method":
            matching_method,

        "time_offset_minutes":
            time_offset_minutes,

        "absolute_time_gap_minutes":
            absolute_gap,

        "allowed_window_minutes":
            allowed_window_minutes,

        "aggregation_interval":
            aggregation_interval,

        # ----------------------------------------------------
        # QC / provenance
        # ----------------------------------------------------

        "quality_flag":
            quality_flag,

        "retrieval_status":
            retrieval_status,

        "missing_reason":
            missing_reason,

        "retrieval_date":
            retrieval_date,

        "source_query":
            source_query,
    }


# ============================================================
# 14. MATCH ONE SITE
# ============================================================

def build_matches_for_site(
    loc: str,
    samples: pd.DataFrame,
    cache: Path,
    diag: dict,
    retrieval_date: str,
):

    site_samples = (
        samples[
            samples["Location_Identifier"] == loc
        ]
        .copy()
    )

    # --------------------------------------------------------
    # Retrieve/cache discrete source information
    # --------------------------------------------------------

    (
        discrete,
        discrete_status,
        discrete_query,
    ) = get_discrete(
        loc,
        STUDY_START,
        STUDY_END,
        cache,
        diag,
    )

    # --------------------------------------------------------
    # Retrieve series availability
    # --------------------------------------------------------

    (
        available_series,
        metadata_status,
        metadata_query,
    ) = series_available(loc)

    rows = []

    variable_to_primary_pcode = {
        variable: pcode
        for pcode, variable in PCODES.items()
    }

    for variable, primary_pcode in (
        variable_to_primary_pcode.items()
    ):

        candidate_pcodes = [
            primary_pcode
        ]

        candidate_pcodes += [
            pcode
            for pcode, fallback_variable
            in DISCRETE_FALLBACK.items()
            if fallback_variable == variable
        ]

        matched_ids = set()

        # ====================================================
        # TIER 1 — SAME-ACTIVITY DISCRETE
        # ====================================================

        for candidate_pcode in candidate_pcodes:

            if discrete.empty:
                continue

            d = discrete[
                discrete["pcode"]
                == candidate_pcode
            ]

            if d.empty:
                continue

            for _, sample in site_samples.iterrows():

                activity_id = sample["activity_id"]

                if activity_id in matched_ids:
                    continue

                hit = d[
                    d["activity_id"]
                    == str(activity_id)
                ]

                if hit.empty:
                    continue

                # If multiple valid environmental results exist
                # under the same activity/pcode, retain first
                # according to existing Method-2 behavior.
                r = hit.iloc[0]

                signed_offset = (
                    r["dt_utc"]
                    - sample["sample_dt_utc"]
                ).total_seconds() / 60.0

                rows.append(
                    make_record(
                        sample=sample,
                        variable=variable,

                        original_value=
                            r["original_value"],

                        original_unit=
                            r["original_unit"],

                        source_station_id=
                            r["station_id"],

                        source_parameter_code=
                            candidate_pcode,

                        observation_date=
                            r["dt_utc"].date(),

                        observation_datetime_utc=
                            r["dt_utc"],

                        observation_utc_offset=
                            r["utc_offset"],

                        observation_timezone=None,

                        matching_method=
                            "discrete_same_activity",

                        time_offset_minutes=
                            round(
                                float(signed_offset),
                                3,
                            ),

                        allowed_window_minutes=0.0,

                        aggregation_interval=
                            "instantaneous",

                        quality_flag=
                            r["quality_flag"],

                        retrieval_status=
                            discrete_status,

                        missing_reason=None,

                        retrieval_date=
                            retrieval_date,

                        source_query=
                            discrete_query,
                    )
                )

                matched_ids.add(activity_id)

        # ====================================================
        # TIER 2 — NEAREST DISCRETE +/- 60 MINUTES
        # ====================================================

        for candidate_pcode in candidate_pcodes:

            if discrete.empty:
                continue

            d = (
                discrete[
                    discrete["pcode"]
                    == candidate_pcode
                ]
                .sort_values("dt_utc")
            )

            if d.empty:
                continue

            need = site_samples[
                ~site_samples["activity_id"]
                .isin(matched_ids)
            ]

            for _, sample in need.iterrows():

                delta = (
                    d["dt_utc"]
                    - sample["sample_dt_utc"]
                )

                within = (
                    delta.abs()
                    <= pd.Timedelta(
                        minutes=DISCRETE_TOL_MIN
                    )
                )

                candidates = d[within]

                if candidates.empty:
                    continue

                signed_gap = (
                    candidates["dt_utc"]
                    - sample["sample_dt_utc"]
                ).dt.total_seconds() / 60.0

                best_index = (
                    signed_gap.abs().idxmin()
                )

                r = candidates.loc[best_index]

                signed_offset = (
                    r["dt_utc"]
                    - sample["sample_dt_utc"]
                ).total_seconds() / 60.0

                rows.append(
                    make_record(
                        sample=sample,
                        variable=variable,

                        original_value=
                            r["original_value"],

                        original_unit=
                            r["original_unit"],

                        source_station_id=
                            r["station_id"],

                        source_parameter_code=
                            candidate_pcode,

                        observation_date=
                            r["dt_utc"].date(),

                        observation_datetime_utc=
                            r["dt_utc"],

                        observation_utc_offset=
                            r["utc_offset"],

                        observation_timezone=None,

                        matching_method=
                            "discrete_time_match",

                        time_offset_minutes=
                            round(
                                float(signed_offset),
                                3,
                            ),

                        allowed_window_minutes=
                            DISCRETE_TOL_MIN,

                        aggregation_interval=
                            "instantaneous",

                        quality_flag=
                            r["quality_flag"],

                        retrieval_status=
                            discrete_status,

                        missing_reason=None,

                        retrieval_date=
                            retrieval_date,

                        source_query=
                            discrete_query,
                    )
                )

                matched_ids.add(
                    sample["activity_id"]
                )

        # ====================================================
        # TIER 3 — NEAREST CONTINUOUS +/- 30 MINUTES
        # ====================================================

        need = site_samples[
            ~site_samples["activity_id"]
            .isin(matched_ids)
        ]

        continuous_status = None
        continuous_query = None

        if (
            not need.empty
            and primary_pcode in available_series
        ):

            (
                nearest,
                continuous_status,
                continuous_query,
            ) = get_continuous_nearest(
                loc,
                primary_pcode,
                need["sample_dt_utc"],
                cache,
                diag,
            )

            if not nearest.empty:

                nearest_indexed = (
                    nearest
                    .set_index("target_time")
                )

                for _, sample in need.iterrows():

                    sample_time = (
                        sample["sample_dt_utc"]
                    )

                    if (
                        sample_time
                        not in nearest_indexed.index
                    ):
                        continue

                    r = nearest_indexed.loc[
                        sample_time
                    ]

                    if isinstance(
                        r,
                        pd.DataFrame
                    ):
                        r = r.iloc[0]

                    signed_offset = (
                        r["obs_time"]
                        - sample_time
                    ).total_seconds() / 60.0

                    rows.append(
                        make_record(
                            sample=sample,
                            variable=variable,

                            original_value=
                                r["original_value"],

                            original_unit=
                                r["original_unit"],

                            source_station_id=
                                r["station_id"],

                            source_parameter_code=
                                primary_pcode,

                            observation_date=
                                r["obs_time"].date(),

                            observation_datetime_utc=
                                r["obs_time"],

                            observation_utc_offset=
                                r["utc_offset"],

                            observation_timezone=None,

                            matching_method=
                                "continuous_nearest",

                            time_offset_minutes=
                                round(
                                    float(
                                        signed_offset
                                    ),
                                    3,
                                ),

                            allowed_window_minutes=
                                CONTINUOUS_TOL_MIN,

                            aggregation_interval=
                                "instantaneous",

                            quality_flag=
                                r["quality_flag"],

                            retrieval_status=
                                continuous_status,

                            missing_reason=None,

                            retrieval_date=
                                retrieval_date,

                            source_query=
                                continuous_query,
                        )
                    )

                    matched_ids.add(
                        sample["activity_id"]
                    )

        # ====================================================
        # TIER 4 — DAILY MEAN DISCHARGE
        # ====================================================

        daily_status = None
        daily_query = None

        need = site_samples[
            ~site_samples["activity_id"]
            .isin(matched_ids)
        ]

        if (
            variable == "Discharge_cfs"
            and not need.empty
        ):

            (
                daily_q,
                daily_status,
                daily_query,
            ) = get_daily_q(
                loc,
                STUDY_START,
                STUDY_END,
                cache,
                diag,
            )

            if not daily_q.empty:

                daily_indexed = (
                    daily_q
                    .set_index(
                        "observation_date"
                    )
                )

                for _, sample in need.iterrows():

                    # IMPORTANT:
                    # Match using the ORIGINAL LOCAL
                    # pesticide sampling date.
                    sample_day = pd.Timestamp(
                        sample[
                            "Activity_StartDate"
                        ]
                    ).normalize()

                    if (
                        sample_day
                        not in daily_indexed.index
                    ):
                        continue

                    r = daily_indexed.loc[
                        sample_day
                    ]

                    if isinstance(
                        r,
                        pd.DataFrame
                    ):
                        r = r.iloc[0]

                    rows.append(
                        make_record(
                            sample=sample,
                            variable=variable,

                            original_value=
                                r["original_value"],

                            original_unit=
                                r["original_unit"],

                            source_station_id=
                                r["station_id"],

                            source_parameter_code=
                                "00060",

                            observation_date=
                                sample_day.date(),

                            # Daily mean is an aggregation,
                            # not an instantaneous midnight
                            # observation.
                            observation_datetime_utc=
                                pd.NaT,

                            observation_utc_offset=
                                None,

                            observation_timezone=
                                sample[
                                    "Activity_StartTimeZone"
                                ],

                            matching_method=
                                "daily_mean",

                            time_offset_minutes=
                                np.nan,

                            allowed_window_minutes=
                                np.nan,

                            aggregation_interval=
                                "P1D",

                            quality_flag=
                                r["quality_flag"],

                            retrieval_status=
                                daily_status,

                            missing_reason=None,

                            retrieval_date=
                                retrieval_date,

                            source_query=
                                daily_query,
                        )
                    )

                    matched_ids.add(
                        sample["activity_id"]
                    )

        # ====================================================
        # TIER 5 — MISSING WITH EXPLICIT REASON
        # ====================================================

        need = site_samples[
            ~site_samples["activity_id"]
            .isin(matched_ids)
        ]

        for _, sample in need.iterrows():

            # -----------------------------------------------
            # First priority:
            # Do NOT interpret retrieval failure as
            # scientific absence.
            # -----------------------------------------------

            statuses = [
                discrete_status,
                metadata_status,
                continuous_status,
                daily_status,
            ]

            retrieval_problem = any(
                status in {
                    "retrieval_failed",
                    "partial_retrieval_failure",
                }
                for status in statuses
                if status is not None
            )

            if retrieval_problem:

                reason = (
                    "source_retrieval_incomplete"
                )

                final_retrieval_status = (
                    "retrieval_incomplete"
                )

            else:

                # -------------------------------------------
                # No retrieval problem known.
                # Now classify scientific/data availability.
                # -------------------------------------------

                discrete_for_variable = (
                    not discrete.empty
                    and discrete[
                        "pcode"
                    ].isin(
                        candidate_pcodes
                    ).any()
                )

                if (
                    primary_pcode
                    not in available_series
                    and not discrete_for_variable
                ):

                    reason = (
                        "no_source_series_or_"
                        "discrete_record_at_station"
                    )

                elif (
                    primary_pcode
                    not in available_series
                ):

                    reason = (
                        "no_continuous_series_"
                        "at_station_and_no_"
                        "acceptable_discrete_match"
                    )

                else:

                    reason = (
                        "source_available_but_no_"
                        "acceptable_reading_within_"
                        "matching_rule"
                    )

                final_retrieval_status = (
                    "retrieval_complete"
                )

            combined_query = " || ".join(
                q
                for q in [
                    discrete_query,
                    metadata_query,
                    continuous_query,
                    daily_query,
                ]
                if q
            )

            rows.append(
                make_record(
                    sample=sample,
                    variable=variable,

                    original_value=np.nan,
                    original_unit=None,

                    source_station_id=None,

                    # Preserve the parameter being sought
                    # even when no match is found.
                    source_parameter_code=
                        primary_pcode,

                    observation_date=None,

                    observation_datetime_utc=
                        pd.NaT,

                    observation_utc_offset=None,
                    observation_timezone=None,

                    matching_method="none",

                    time_offset_minutes=np.nan,

                    allowed_window_minutes=np.nan,

                    aggregation_interval=None,

                    quality_flag=None,

                    retrieval_status=
                        final_retrieval_status,

                    missing_reason=reason,

                    retrieval_date=
                        retrieval_date,

                    source_query=
                        combined_query,
                )
            )

    return rows


# ============================================================
# 15. BUILD WIDE ACTIVITY-LEVEL TABLE
# ============================================================

def build_activity_features(
    samples: pd.DataFrame,
    matches: pd.DataFrame,
):

    wide = (
        matches
        .pivot(
            index=
                "Activity_ActivityIdentifier",
            columns="variable",
            values="standardized_value",
        )
        .reset_index()
    )

    activity = (
        samples.rename(
            columns={
                "activity_id":
                    "Activity_ActivityIdentifier"
            }
        )
        [
            [
                "Pesticide_Site",
                "Site_Abb",
                "Activity_ActivityIdentifier",
                "Activity_StartDate",
                "Activity_StartTime",
                "Activity_StartTimeZone",
                "sample_datetime_local",
                "sample_dt_utc",
                "Location_Identifier",
            ]
        ]
        .merge(
            wide,
            on="Activity_ActivityIdentifier",
            how="left",
            validate="one_to_one",
        )
    )

    # Ensure all six variables exist.
    for variable in STANDARD_UNIT:

        if variable not in activity.columns:
            activity[variable] = np.nan

    return activity


# ============================================================
# 16. QC REPORTS
# ============================================================

def build_qc_reports(
    matches: pd.DataFrame,
    n_activities: int,
):

    coverage = (
        matches
        .groupby(
            [
                "variable",
                "matching_method",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="n")
    )

    matched = (
        matches[
            matches["standardized_value"]
            .notna()
        ]
        .groupby("variable")
        .size()
        .rename("matched")
    )

    missing = (
        matches[
            matches["standardized_value"]
            .isna()
        ]
        .groupby("variable")
        .size()
        .rename("missing")
    )

    summary = (
        pd.concat(
            [matched, missing],
            axis=1,
        )
        .fillna(0)
        .reset_index()
    )

    summary["total_activities"] = (
        n_activities
    )

    summary["coverage_pct"] = (
        100
        * summary["matched"]
        / n_activities
    ).round(2)

    missing_reason = (
        matches[
            matches["standardized_value"]
            .isna()
        ]
        .groupby(
            [
                "variable",
                "retrieval_status",
                "missing_reason",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="n")
    )

    provenance_fields = [
        "source_station_id",
        "source_parameter_code",
        "observation_datetime_utc",
        "observation_utc_offset",
        "original_value",
        "original_unit",
        "standardized_value",
        "standardized_unit",
        "matching_method",
        "time_offset_minutes",
        "allowed_window_minutes",
        "aggregation_interval",
        "quality_flag",
        "retrieval_status",
        "missing_reason",
        "retrieval_date",
        "source_query",
    ]

    completeness = []

    for field in provenance_fields:

        completeness.append({
            "field":
                field,

            "available":
                int(
                    matches[field]
                    .notna()
                    .sum()
                ),

            "missing":
                int(
                    matches[field]
                    .isna()
                    .sum()
                ),

            "available_pct":
                round(
                    100
                    * matches[field]
                    .notna()
                    .mean(),
                    2,
                ),
        })

    completeness = pd.DataFrame(
        completeness
    )

    return (
        coverage,
        summary,
        missing_reason,
        completeness,
    )


# ============================================================
# 17. VALIDATION
# ============================================================

def validate_outputs(
    samples: pd.DataFrame,
    matches: pd.DataFrame,
    activity_features: pd.DataFrame,
):

    n_activities = (
        samples["activity_id"].nunique()
    )

    expected = (
        n_activities
        * len(STANDARD_UNIT)
    )

    print("\n==============================")
    print("VALIDATION")
    print("==============================")

    print(
        f"Unique activities: "
        f"{n_activities:,}"
    )

    print(
        f"Environmental variables: "
        f"{len(STANDARD_UNIT)}"
    )

    print(
        f"Expected provenance rows: "
        f"{expected:,}"
    )

    print(
        f"Actual provenance rows: "
        f"{len(matches):,}"
    )

    if len(matches) != expected:

        raise ValueError(
            "Environmental provenance row count "
            "does not equal activities x variables."
        )

    duplicate = matches.duplicated(
        subset=[
            "Activity_ActivityIdentifier",
            "variable",
        ],
        keep=False,
    )

    if duplicate.any():

        raise ValueError(
            f"{duplicate.sum():,} duplicate "
            "activity-variable records found."
        )

    if len(activity_features) != n_activities:

        raise ValueError(
            "Activity-level feature table does "
            "not contain exactly one row per "
            "sampling activity."
        )

    # Every nonmissing value must have a match method.
    bad = (
        matches["standardized_value"].notna()
        & (
            matches["matching_method"].isna()
            | (
                matches["matching_method"]
                == "none"
            )
        )
    )

    if bad.any():

        raise ValueError(
            f"{bad.sum():,} matched values have "
            "no valid matching method."
        )

    # Every missing value must have a reason.
    bad_missing = (
        matches["standardized_value"].isna()
        & matches["missing_reason"].isna()
    )

    if bad_missing.any():

        raise ValueError(
            f"{bad_missing.sum():,} missing "
            "environmental values have no "
            "missing reason."
        )

    print(
        "Duplicate activity-variable rows: 0"
    )

    print(
        "Missing values without reason: 0"
    )

    print(
        "Matched values without method: 0"
    )

    print("Validation passed.")


# ============================================================
# 18. MAIN
# ============================================================

def main(
    argv: list[str] | None = None
):

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=
            argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--t2",
        required=True,
        help=(
            "Path to original "
            "t2_pest_concs.parquet"
        ),
    )

    parser.add_argument(
        "--outdir",
        default="data/interim",
        help="Output directory",
    )

    parser.add_argument(
        "--sites",
        type=int,
        default=None,
        help=(
            "Optional test run using first "
            "N physical stations."
        ),
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(message)s"
        ),
    )

    outdir = Path(args.outdir)

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache = (
        outdir
        / "raw_cache_provenance"
    )

    cache.mkdir(
        parents=True,
        exist_ok=True,
    )

    retrieval_date = (
        datetime.now(timezone.utc)
        .isoformat()
    )

    # --------------------------------------------------------
    # Load pesticide table
    # --------------------------------------------------------

    t2 = pd.read_parquet(args.t2)

    print(
        f"Original pesticide rows: "
        f"{len(t2):,}"
    )

    print(
        "Unique analytes:",
        t2["Pesticide_Name"].nunique()
        if "Pesticide_Name" in t2.columns
        else "not available",
    )

    # --------------------------------------------------------
    # Build activity master
    # --------------------------------------------------------

    samples = build_samples(t2)

    print(
        f"Unique sampling activities: "
        f"{len(samples):,}"
    )

    locations = sorted(
        samples[
            "Location_Identifier"
        ].dropna().unique()
    )

    if args.sites:

        locations = locations[
            :args.sites
        ]

        samples = (
            samples[
                samples[
                    "Location_Identifier"
                ].isin(locations)
            ]
            .reset_index(drop=True)
        )

    print(
        f"Physical primary locations "
        f"processed: {len(locations):,}"
    )

    # --------------------------------------------------------
    # Build provenance
    # --------------------------------------------------------

    diagnostics = {}

    all_rows = []

    for i, loc in enumerate(
        locations,
        start=1,
    ):

        log.info(
            "[%d/%d] %s",
            i,
            len(locations),
            loc,
        )

        site_rows = (
            build_matches_for_site(
                loc=loc,
                samples=samples,
                cache=cache,
                diag=diagnostics,
                retrieval_date=retrieval_date,
            )
        )

        all_rows.extend(site_rows)

    matches = pd.DataFrame(
        all_rows
    )

    # --------------------------------------------------------
    # Build activity-level wide table
    # --------------------------------------------------------

    activity_features = (
        build_activity_features(
            samples,
            matches,
        )
    )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    validate_outputs(
        samples,
        matches,
        activity_features,
    )

    # --------------------------------------------------------
    # QC summaries
    # --------------------------------------------------------

    (
        coverage_detail,
        coverage_summary,
        missing_summary,
        provenance_completeness,
    ) = build_qc_reports(
        matches,
        len(samples),
    )

    # --------------------------------------------------------
    # Save outputs
    # --------------------------------------------------------

    # FIX (2026-09): the original filenames here
    # (method2_activity_features.parquet, method2_environmental_matches.parquet)
    # are the SAME paths scripts/13_build_interim_activity_features.py already
    # writes, with a much simpler schema (plain values only, no provenance).
    # Running this script after 13 would silently overwrite that file with
    # this one's richer 20-field schema -- the same class of collision bug
    # already found and fixed elsewhere in this repo (see
    # UNRESOLVED_ISSUES.md). Renamed with a distinct suffix so both can
    # coexist; this script has not yet been run (needs live USGS access), so
    # no existing file was overwritten by this fix.
    matches_file = (
        outdir
        / "method2_environmental_matches_full_provenance.parquet"
    )

    activity_file = (
        outdir
        / "method2_activity_features_full_provenance.parquet"
    )

    matches.to_parquet(
        matches_file,
        index=False,
    )

    activity_features.to_parquet(
        activity_file,
        index=False,
    )

    coverage_detail.to_csv(
        outdir
        / "method2_match_method_summary.csv",
        index=False,
    )

    coverage_summary.to_csv(
        outdir
        / "method2_match_coverage_summary.csv",
        index=False,
    )

    missing_summary.to_csv(
        outdir
        / "method2_missing_reason_summary.csv",
        index=False,
    )

    provenance_completeness.to_csv(
        outdir
        / "method2_provenance_completeness.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    with open(
        outdir
        / "method2_api_column_diagnostics.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            diagnostics,
            f,
            indent=2,
            default=str,
        )

    print("\n==============================")
    print("OUTPUTS")
    print("==============================")

    print(matches_file)
    print(activity_file)

    print(
        outdir
        / "method2_match_coverage_summary.csv"
    )

    print(
        outdir
        / "method2_missing_reason_summary.csv"
    )

    print(
        outdir
        / "method2_provenance_completeness.csv"
    )

    print("\nCoverage:")
    print(
        coverage_summary.to_string(
            index=False
        )
    )

    print("\nMissing reasons:")
    print(
        missing_summary.to_string(
            index=False
        )
    )

    print("\nAPI column diagnostics:")

    for key, value in diagnostics.items():

        print(
            f"  {key}: "
            f"{value!r}"
        )

    print("\nDone.")


# ============================================================
# 19. NOTEBOOK DETECTION
# ============================================================

def _in_notebook():

    import sys

    return (
        "ipykernel" in sys.modules
        or "google.colab" in sys.modules
    )


if (
    __name__ == "__main__"
    and not _in_notebook()
):
    main()