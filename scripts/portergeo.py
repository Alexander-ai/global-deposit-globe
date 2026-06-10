"""
PorterGeo Ore Deposit Database crosswalk.

NOT a data source — it adds nothing to the point count. It ATTACHES a `porterUrl` to the
deposits we can confidently match against PorterGeo's ~1,800-deposit listing, so the detail
card can link out to their in-depth geological write-up.

PorterGeo keys pages by an opaque numeric id (mineinfo.php?mineid=mn204) with no relation to
the deposit name. scrape_portergeo.py harvests every page's COORDINATES into a committed
`portergeo_index.json`; this module matches our deposits to PorterGeo by PROXIMITY (+ a
commodity guard), which is far more robust than name matching and is read entirely offline.

Conservative on purpose: a missed link is harmless, but a WRONG link sends a reader to the
wrong deposit — so a link needs the deposit to be either right on top of a PorterGeo entry
(R_PROX) or in the same region with an agreeing name (R_NAME), and commodity-compatible.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import normalize  # noqa: E402  (commodity bucketing — the match's commodity guard)
from schema import ROOT  # noqa: E402
from sources.base import ensure_cached  # noqa: E402  (reuse cache + polite UA, for the scraper)

LISTING_URL = "https://portergeo.com.au/database/display.php"
PAGE_URL = "https://portergeo.com.au/database/mineinfo.php?mineid="

# One listing row: the linked name, then the country and commodities cells.
_ROW = re.compile(
    r'mineinfo\.php\?mineid=(mn\d+)">(.*?)</a>.*?displayUpdateCountry">(.*?)</td>'
    r'.*?displayCommodities">(.*?)</td>',
    re.S,
)

# Generic descriptors stripped before comparing names (so "Escondida open pit mine" and
# "Escondida" canonicalize the same). Directional/ordinal words are kept — they distinguish.
_NOISE = re.compile(
    r"\b(mine|mines|deposit|deposits|prospect|prospects|project|projects|group|groups|"
    r"open|pit|pits|opencast|underground|cut|workings|operation|operations|complex|"
    r"complexes|belt|belts|zone|zones|system|district|districts|field|fields|camp|area|"
    r"smelter|smelters|refinery|refineries|mill|mills|plant|plants|concentrator|"
    r"concentrators|division|at|near|in|the|and)\b",
    re.I,
)

# A PorterGeo name often packs commodity/qualifier words ("…, Copper - X41") that, once split
# into aliases, would become dangerously generic lookup keys. An alias is only indexed if it
# keeps a DISTINCTIVE token (not purely commodity/direction words).
_STOP = {
    "copper", "zinc", "lead", "gold", "silver", "iron", "nickel", "cobalt", "uranium",
    "lithium", "manganese", "bauxite", "aluminium", "aluminum", "alumina", "platinum",
    "palladium", "tin", "chromium", "chrome", "chromite", "tungsten", "molybdenum",
    "vanadium", "tantalum", "niobium", "antimony", "bismuth", "mercury", "graphite",
    "fluorite", "fluorspar", "barite", "phosphate", "potash", "coal", "diamond", "diamonds",
    "rare", "earth", "earths", "ree", "pge", "sulphide", "sulfide", "oxide", "polymetallic",
    "north", "south", "east", "west", "upper", "lower", "main", "central", "new", "old",
}

_C_ALIAS = {
    "usa": "united states", "us": "united states", "u s a": "united states",
    "united states of america": "united states",
    "drc": "democratic republic of the congo",
    "democratic republic of congo": "democratic republic of the congo",
    "congo kinshasa": "democratic republic of the congo",
    "russian federation": "russia", "uk": "united kingdom",
    "great britain": "united kingdom",
}


def _canon(name: str) -> str:
    n = re.sub(r"&[a-z]+;", " ", name or "")          # drop HTML entities
    n = re.sub(r"[^a-z0-9 ]", " ", n.lower())
    n = _NOISE.sub(" ", n)
    return " ".join(n.split())


def _country(c) -> str:
    s = " ".join(re.sub(r"[^a-z ]", " ", (c or "").lower()).split())
    return _C_ALIAS.get(s, s)


def _aliases(name_html: str) -> list[str]:
    """A listing name may pack several aliases ('Mes Aynak, Mis Ainak and Darband') and a
    'X Complex - member, member' member list — split on commas/and/slash/semicolon and dashes."""
    txt = re.sub(r"&[a-z]+;", " ", name_html)
    return [p.strip() for p in re.split(r",|\band\b|/|;|\s[-–]\s", txt, flags=re.I) if p.strip()]


def _distinctive(canon: str) -> bool:
    """True if a canonical alias carries a token that isn't a bare commodity/qualifier word."""
    toks = canon.split()
    return len(canon) >= 3 and any(t not in _STOP for t in toks)


def _buckets(commodities_html: str) -> frozenset:
    """Commodity buckets named in a listing cell ('Cu, Au' / ' Fe') for the match guard."""
    txt = re.sub(r"&[a-z]+;", " ", commodities_html or "")
    out = set()
    for tok in re.split(r"[\s,;/]+", txt):
        b = normalize.bucket_for_token(tok.strip().upper()) if tok.strip() else None
        if b:
            out.add(b)
    return frozenset(out)


# --- name-based fallback (used where we have no PorterGeo coordinate) ----------
# A name unique in PorterGeo can still be COMMON in our data ("Escondida" = dozens of small
# "hidden" sites), so the name fallback only links a name LOCALIZED on our side (its records
# occupy ≤ this many ~1° cells). Coordinates, when present, supersede this entirely.
MAX_NAME_CELLS = 2


def load_index(html: str) -> dict[str, set]:
    """canonical-name -> {(country, buckets, mineid)} from the listing HTML."""
    byname: dict[str, set] = defaultdict(set)
    for mineid, name_html, country, comm in _ROW.findall(html):
        entry = (_country(country), _buckets(comm), mineid)
        for alias in _aliases(name_html):
            c = _canon(alias)
            if _distinctive(c):
                byname[c].add(entry)
    return byname


def link_for(name, country, commodity, byname: dict[str, set]) -> str | None:
    """Name-based PorterGeo URL (pure/testable): the name must match AND the commodity be
    compatible; a unique name links when country agrees/unknown, an ambiguous one needs an
    exact country match."""
    c = _canon(name or "")
    if not c or c not in byname:
        return None
    co = _country(country)
    compat = [
        (cc, mid)
        for (cc, buckets, mid) in byname[c]
        if commodity == "other" or not buckets or commodity in buckets
    ]
    ids = {mid for _, mid in compat}
    if len(ids) == 1:
        mid = next(iter(ids))
        countries = {cc for cc, m in compat if m == mid}
        if not co or co in countries:
            return PAGE_URL + mid
        return None
    if co:
        hit = {mid for (cc, mid) in compat if cc == co}
        if len(hit) == 1:
            return PAGE_URL + next(iter(hit))
    return None


# --- coordinate-based matching ------------------------------------------------
# The committed index (built by scrape_portergeo.py) gives every PorterGeo deposit a
# location, so we match by PROXIMITY — far more robust than names: it links variants
# (Norilsk <-> "Talnakh Complex"), disambiguates common names (only the "Escondida" AT
# Escondida's coords matches), and is read offline so the build never scrapes.
INDEX_PATH = ROOT / "scripts" / "portergeo_index.json"
R_PROX_KM = 5.0    # same spot + compatible commodity -> link (strong on its own)
R_NAME_KM = 30.0   # same region AND the name agrees -> link (catches coordinate noise)
_GRID = 0.5        # ~55 km blocking cells


def _haversine_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = math.radians(b_lat - a_lat), math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _name_agrees(a: str, b: str) -> bool:
    if not a or not b or len(a) < 3 or len(b) < 3:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    return ta <= tb or tb <= ta


def build_grid(index: list[dict]) -> dict:
    """Spatial blocking grid over PorterGeo entries, each enriched with canon + bucket set."""
    grid: dict = defaultdict(list)
    for e in index:
        ent = {"id": e["id"], "lat": float(e["lat"]), "lng": float(e["lng"]),
               "b": set(e.get("b") or []), "canon": _canon(e.get("name", ""))}
        grid[(round(ent["lat"] / _GRID), round(ent["lng"] / _GRID))].append(ent)
    return grid


def best_link(lat: float, lng: float, commodity: str, canon: str, grid: dict) -> str | None:
    """PorterGeo URL for a deposit (pure/testable): the nearest commodity-compatible entry
    within R_PROX, else the nearest name-agreeing entry within R_NAME, else None."""
    cx, cy = round(lat / _GRID), round(lng / _GRID)
    near_d, near = R_PROX_KM, None
    name_d, name = R_NAME_KM, None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for e in grid.get((cx + dx, cy + dy), ()):
                if not (commodity == "other" or not e["b"] or commodity in e["b"]):
                    continue
                d = _haversine_km(lat, lng, e["lat"], e["lng"])
                if d < near_d:
                    near_d, near = d, e
                if d < name_d and _name_agrees(canon, e["canon"]):
                    name_d, name = d, e
    e = near or name
    return PAGE_URL + e["id"] if e else None


def add_links(df, index: list[dict] | None = None, byname: dict[str, set] | None = None):
    """Attach a `porterUrl` column. HYBRID: match by PROXIMITY from the committed coordinate
    index first (precise, variant-tolerant), then fall back to NAME matching from the listing
    for deposits the (possibly incomplete) coordinate index doesn't cover. Returns
    (df, n_linked)."""
    df = df.copy()
    # coordinate index (committed; may be partial or absent → just fewer proximity matches)
    if index is None:
        try:
            index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            index = []
    grid = build_grid(index) if index else {}
    # name index (one cached listing page) for the fallback
    if byname is None:
        try:
            path = ensure_cached(LISTING_URL, "portergeo_listing.html")
            byname = load_index(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:  # no listing AND no coords -> no links, don't break the build
            byname = {}
            if not grid:
                print(f"  PorterGeo: skipped ({e})")
                df["porterUrl"] = None
                return df, 0

    canons = [_canon(n or "") for n in df["name"]]
    name_cells: dict[str, set] = defaultdict(set)  # name dispersion for the fallback gate
    for cn, lat, lng in zip(canons, df["lat"], df["lng"]):
        if cn:
            name_cells[cn].add((round(float(lat)), round(float(lng))))

    n_prox = 0
    urls = []
    for name, cn, lat, lng, country, comm in zip(
        df["name"], canons, df["lat"], df["lng"], df["country"], df["commodity"]
    ):
        u = best_link(float(lat), float(lng), comm, cn, grid) if grid else None
        if u is not None:
            n_prox += 1
        elif byname and cn and len(name_cells[cn]) <= MAX_NAME_CELLS:
            u = link_for(name, country, comm, byname)
        urls.append(u)
    df["porterUrl"] = urls
    total = sum(1 for u in urls if u)
    if grid:
        print(f"  PorterGeo: {n_prox:,} matched by coordinates, {total - n_prox:,} by name")
    return df, total
