#!/usr/bin/env python3
"""
Multi-source mineral-deposit pipeline -> public/deposits.json

Loads every registered source (scripts/sources/), normalizes commodities into the nine
color buckets (scripts/normalize.py), de-duplicates within and across sources, and writes a
compact JSON. Accuracy is checked on every run by scripts/validate.py (geographic balance +
famous-deposit spot-checks).

Usage:
    python scripts/prepare-data.py            # build public/deposits.json + report
    python scripts/prepare-data.py --report   # report only, write nothing

Single-source (MRDS-only) output is byte-identical to the original pipeline; the `source`
field is added to records once a second source is registered.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
import geo  # noqa: E402
import normalize  # noqa: E402
import validate  # noqa: E402
from schema import OUT, ROOT  # noqa: E402
from sources import SOURCES  # noqa: E402

KEEP_OTHER = False  # drop the unbucketed "other" commodity for a clean critical-minerals view

STATUS_KEEP_BY_ID = {s.ID: getattr(s, "STATUS_KEEP", None) for s in SOURCES}
LABEL_BY_ID = {s.ID: s.LABEL for s in SOURCES}
MULTI_SOURCE = len(SOURCES) > 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="report only; write no file")
    args = ap.parse_args()

    # ---- load sources --------------------------------------------------------
    frames, loaded = [], {}
    for src in SOURCES:
        df = src.load()
        loaded[src.ID] = len(df)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    total_in = len(df)
    dropped: Counter = Counter()

    # ---- Step 1: clean -------------------------------------------------------
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")

    bad = df["lat"].isna() | df["lng"].isna()
    dropped["non-numeric or missing lat/lng"] = int(bad.sum())
    df = df[~bad]
    null_island = (df["lat"] == 0) & (df["lng"] == 0)
    dropped["null island (0,0)"] = int(null_island.sum())
    df = df[~null_island]
    oor = (df["lat"] < -90) | (df["lat"] > 90) | (df["lng"] < -180) | (df["lng"] > 180)
    dropped["lat/lng out of range"] = int(oor.sum())
    df = df[~oor]

    df["lat"] = df["lat"].round(4)
    df["lng"] = df["lng"].round(4)
    # Tidy names (mojibake repair, drop ';'-list tails, "Mine at X" -> "X", collapse doubled
    # phrases) before everything downstream — dedup matching, PorterGeo linking, search.
    df["name"] = [normalize.clean_name(n) for n in df["name"].fillna("")]

    # Coordinate-integrity (#2): drop records whose coords fall well outside their stated
    # country (lat/lng swaps, sign errors, gross geocodes). Unknown countries are kept.
    before = len(df)
    ok = [geo.consistent(c, la, lo) for c, la, lo in zip(df["country"], df["lat"], df["lng"])]
    df = df[pd.Series(ok, index=df.index)]
    dropped["country/coord mismatch"] = before - len(df)

    # Exact within/cross-source dedup (keep first). Fuzzy cross-source dedup is layered in
    # once multiple sources exist (scripts/dedup.py).
    before = len(df)
    df = df.drop_duplicates(subset=["lat", "lng", "name"], keep="first")
    dropped["exact duplicate (lat, lng, name)"] = before - len(df)

    # Separate mining technique (open-pit, underground, …) and facility labels (mine, plant)
    # out of the deposit-type field. Done before dedup so a record whose only "type" was a
    # method can absorb a real geological type from a merged duplicate.
    split = [normalize.split_deposit_type(dt) for dt in df["depositType"]]
    df["depositType"] = [s[0] for s in split]
    df["miningTechnique"] = [s[1] for s in split]

    # ---- Steps 2-3: classify commodity (needed by the fuzzy dedup's guard) ----
    df["commodity"] = [normalize.classify(c) for c in df["commodities"]]

    dedup_stats = None
    if MULTI_SOURCE:
        import dedup  # noqa: E402  (only needed with >1 source)
        before = len(df)
        df, dedup_stats = dedup.merge(df)
        dropped["cross-source duplicate (fuzzy)"] = before - len(df)

    # 'also' is computed after dedup, which may absorb co-commodities into the survivor.
    df["also"] = [
        normalize.secondary_names(c, b) for c, b in zip(df["commodities"], df["commodity"])
    ]

    # ---- Step 4: v1 filters --------------------------------------------------
    if not KEEP_OTHER:
        before = len(df)
        df = df[df["commodity"] != "other"]
        dropped['commodity = "other"'] = before - len(df)

    # Per-source status keep (MRDS: producers/past only; catalog sources: keep all).
    keep_mask = [
        STATUS_KEEP_BY_ID.get(s) is None or sr in STATUS_KEEP_BY_ID[s]
        for s, sr in zip(df["source"], df["status_raw"])
    ]
    before = len(df)
    df = df[pd.Series(keep_mask, index=df.index)]
    dropped["status not kept (per-source filter)"] = before - len(df)

    df["status"] = [
        normalize.status_for(sr, s) for sr, s in zip(df["status_raw"], df["source"])
    ]

    # PorterGeo crosswalk: attach a link to the in-depth description page for the (major)
    # deposits we can confidently match by name + country + commodity.
    import portergeo  # noqa: E402
    df, n_porter = portergeo.add_links(df)

    # ---- Report --------------------------------------------------------------
    print("=" * 70)
    print("  multi-source deposits  ·  build report")
    print("=" * 70)
    print("  sources loaded:")
    for sid, n in loaded.items():
        print(f"    {sid:<12} {n:>8,}  ({LABEL_BY_ID[sid]})")
    print(f"\n  records in:  {total_in:>8,}")
    print(f"  records out: {len(df):>8,}")
    print("  dropped:")
    for reason, n in dropped.items():
        if n:
            print(f"    {n:>8,}  {reason}")

    print("\n  per commodity bucket:")
    out_counts = Counter(df["commodity"])
    for b in normalize.NAMED_BUCKETS:
        print(f"    {b:<9} {out_counts.get(b, 0):>8,}")
    print(f"    {'TOTAL':<9} {len(df):>8,}")

    if MULTI_SOURCE:
        print("\n  per source x bucket (output):")
        for sid in loaded:
            sc = Counter(df[df["source"] == sid]["commodity"])
            top = ", ".join(f"{b}:{sc[b]}" for b in normalize.NAMED_BUCKETS if sc[b])
            print(f"    {sid:<12} {sum(sc.values()):>7,}  {top}")

    print(f"\n  PorterGeo: linked {n_porter:,} deposits to in-depth descriptions")

    if dedup_stats:
        print(f"\n  DEDUP: removed {dedup_stats['removed']:,} duplicate records")
        print("    merges by source-pair:")
        for pair, n in dedup_stats["by_pair"].most_common():
            print(f"      {pair[0]} <-> {pair[1]}: {n:,}")
        print("    widest accepted merges (audit for over-merge):")
        for d, a, b in dedup_stats["widest"]:
            print(f"      {d:5.2f} km  {a[:34]:<34} <- {b[:34]}")

    # ---- Build output records ------------------------------------------------
    if "corrob" not in df.columns:
        df["corrob"] = None
    if "magnitude" not in df.columns:
        df["magnitude"] = None
    if "miningTechnique" not in df.columns:
        df["miningTechnique"] = None
    if "porterUrl" not in df.columns:
        df["porterUrl"] = None
    records = []
    cols = ["name", "lat", "lng", "commodity", "status", "depositType", "miningTechnique",
            "also", "source", "country", "magnitude", "corrob", "porterUrl"]
    for (name, lat, lng, commodity, status, dtype, mining, also, source, country, mag,
         corrob, porter) in zip(*(df[c] for c in cols)):
        rec = {
            "name": name if name else "Unnamed site",
            "lat": float(lat),
            "lng": float(lng),
            "commodity": commodity,
            "status": status,
        }
        if isinstance(dtype, str) and dtype.strip():
            rec["depositType"] = dtype.strip()
        if isinstance(mining, str) and mining.strip():
            rec["miningTechnique"] = mining.strip()
        if also:
            rec["also"] = also
        if isinstance(country, str) and country.strip():
            rec["country"] = country.strip()
        if MULTI_SOURCE:
            rec["source"] = LABEL_BY_ID.get(source, source)
        if pd.notna(mag) and float(mag) > 0:
            rec["m"] = round(float(mag), 2)  # magnitude 1.2–3 -> dot size
        if pd.notna(corrob) and int(corrob) > 1:
            rec["corrob"] = int(corrob)  # distinct databases corroborating this site
        if isinstance(porter, str) and porter:
            rec["porterUrl"] = porter  # link to PorterGeo's in-depth description
        records.append(rec)

    validate.print_report(records)  # records now carry country for the balance metric

    if args.report:
        print("\n  --report: no file written.")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, separators=(",", ":"))
    size_mb = OUT.stat().st_size / 1_048_576
    print(f"\n  wrote {len(records):,} deposits -> {OUT.relative_to(ROOT)}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
