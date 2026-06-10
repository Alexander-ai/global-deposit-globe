"""
Accuracy harness: geographic-balance metric + famous-deposit spot-checks.

Used by prepare-data.py's report, and runnable standalone against public/deposits.json:
    python scripts/validate.py            # print report, exit 0
    python scripts/validate.py --strict   # non-zero exit if any spot-check FAILs
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

US_NAMES = {"united states", "usa", "us", "united states of america", "u.s.a.", "u.s."}


def is_us(country, lat: float, lng: float) -> bool:
    if isinstance(country, str) and country.strip().lower() in US_NAMES:
        return True
    if isinstance(country, str) and country.strip():
        return False  # trust an explicit non-US country
    # No country given (e.g. MRDS rows without it) -> bounding-box fallback.
    conus = 24 <= lat <= 50 and -125 <= lng <= -66
    alaska = 51 <= lat <= 72 and -170 <= lng <= -129
    hawaii = 18 <= lat <= 23 and -161 <= lng <= -154
    return conus or alaska or hawaii


def continent_of(lat: float, lng: float) -> str:
    if lat < -60:
        return "Antarctica"
    if -56 <= lat <= 14 and -82 <= lng <= -34:
        return "South America"
    if 7 <= lat <= 84 and -168 <= lng <= -52:
        return "North America"
    if -50 <= lat <= 0 and 110 <= lng <= 179:
        return "Oceania"
    if 34 <= lat <= 72 and -25 <= lng <= 45:
        return "Europe"
    if -36 <= lat <= 38 and -20 <= lng <= 52:
        return "Africa"
    if -12 <= lat <= 82 and 25 <= lng <= 180:
        return "Asia"
    return "Other"


def haversine_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


# name, country, allowed buckets, lat, lng, tolerance km, expectation
SPOTCHECKS = [
    ("Escondida",        "Chile",     {"copper"},            -24.27, -69.07, 30, "present"),
    ("Olympic Dam",      "Australia", {"copper", "uranium"}, -30.44, 136.88, 30, "present"),
    ("Grasberg",         "Indonesia", {"copper", "gold"},     -4.06, 137.11, 30, "present"),
    ("Norilsk",          "Russia",    {"nickel", "copper"},   69.33,  88.22, 40, "present"),
    ("Oyu Tolgoi",       "Mongolia",  {"copper", "gold"},     43.00, 106.86, 40, "present"),
    ("Greenbushes",      "Australia", {"lithium"},           -33.86, 116.06, 30, "present"),
    ("Bayan Obo",        "China",     {"ree"},                41.77, 109.97, 40, "present"),
    ("Sudbury",          "Canada",    {"nickel", "copper"},   46.49, -81.00, 40, "present"),
    ("Mufulira",         "Zambia",    {"copper"},            -12.55,  28.24, 30, "present"),
    ("Cerro Verde",      "Peru",      {"copper"},            -16.53, -71.59, 30, "present"),
    ("Antamina",         "Peru",      {"copper", "zinc"},     -9.53, -77.05, 30, "present"),
    ("Cigar Lake",       "Canada",    {"uranium"},            58.06,-104.50, 40, "present"),
    # Controls
    ("Bingham Canyon",   "USA",       {"copper"},             40.52,-112.15, 30, "present"),  # US regression
    ("Mountain Pass",    "USA",       {"ree"},                35.48,-115.53, 30, "present"),  # US regression
    # Expanded-palette powerhouse deposits (Africa / Australia)
    ("Bushveld (PGE)",   "S.Africa",  {"platinum"},          -25.67,  27.24, 60, "present"),
    ("Sishen (iron)",    "S.Africa",  {"iron"},              -27.78,  22.99, 40, "present"),
    ("Kalahari Mn",      "S.Africa",  {"manganese"},         -27.23,  22.96, 50, "present"),
    ("Pilbara iron",     "Australia", {"iron"},              -23.36, 119.68, 60, "present"),
    ("Weipa bauxite",    "Australia", {"bauxite"},           -12.66, 141.88, 50, "present"),
]


def spotcheck(records: list[dict]) -> tuple[list[tuple], int]:
    """Returns (rows, n_fail). Each row: (status, name, detail)."""
    rows = []
    fails = 0
    for name, _country, buckets, lat, lng, tol, expect in SPOTCHECKS:
        near = [r for r in records if haversine_km(lat, lng, r["lat"], r["lng"]) <= tol]
        if expect == "absent":
            ok = len(near) == 0 or all(r["commodity"] == "other" for r in near)
            detail = "absent/other" if ok else f"unexpectedly present ({len(near)})"
        else:
            hit = [r for r in near if not buckets or r["commodity"] in buckets]
            present = len(hit) > 0
            ok = present
            if not present:
                detail = f"MISSING (0 of {len(near)} near match {sorted(buckets)})"
            else:
                dup = "" if len(hit) == 1 else f"  [x{len(hit)} nearby]"
                detail = f"{hit[0]['commodity']}  {len(near)} within {tol}km{dup}"
        rows.append(("PASS" if ok else "FAIL", name, detail))
        if not ok:
            fails += 1
    return rows, fails


def geographic_balance(records: list[dict]) -> dict:
    total = len(records)
    us = sum(1 for r in records if is_us(r.get("country"), r["lat"], r["lng"]))
    cont = Counter(continent_of(r["lat"], r["lng"]) for r in records)
    return {"total": total, "us": us,
            "us_pct": 100 * us / total if total else 0,
            "continents": cont}


def print_report(records: list[dict], baseline_us_pct: float | None = None) -> int:
    geo = geographic_balance(records)
    print("\n  GEOGRAPHIC BALANCE")
    base = f"  (baseline MRDS-only {baseline_us_pct:.1f}%)" if baseline_us_pct else ""
    print(f"    US share: {geo['us_pct']:.1f}%  of {geo['total']:,}{base}   target <50%")
    print("    by continent:")
    for c, n in geo["continents"].most_common():
        print(f"      {c:<15} {n:>8,}  ({100*n/geo['total']:.1f}%)")

    rows, fails = spotcheck(records)
    print("\n  SPOT-CHECKS (famous deposits)")
    for status, name, detail in rows:
        mark = "ok " if status == "PASS" else "XX "
        print(f"    [{mark}] {name:<18} {detail}")
    passed = len(rows) - fails
    print(f"    {passed}/{len(rows)} passed")
    return fails


def main() -> None:
    strict = "--strict" in sys.argv
    path = ROOT / "public" / "deposits.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    fails = print_report(records)
    if strict and fails:
        sys.exit(f"\n  {fails} spot-check(s) FAILED (--strict)")


if __name__ == "__main__":
    main()
