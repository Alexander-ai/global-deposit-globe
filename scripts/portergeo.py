"""
PorterGeo Ore Deposit Database crosswalk.

NOT a data source — it adds nothing to the point count. It ATTACHES a `porterUrl` to the
deposits we can confidently match against PorterGeo's ~1,800-deposit listing, so the detail
card can link out to their in-depth geological write-up.

PorterGeo keys pages by an opaque numeric id (mineinfo.php?mineid=mn204) with no relation to
the deposit name, but publishes one structured listing page (name → id, country, commodity).
We parse that once and match by canonical name + country.

Conservative on purpose: a missed link is harmless, but a WRONG link sends a reader to the
wrong deposit. So we link only when the canonical name is globally UNIQUE in PorterGeo, or
when an ambiguous name is disambiguated by an exact country match. Anything else: no link.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import normalize  # noqa: E402  (commodity bucketing — the match's commodity guard)
from sources.base import ensure_cached  # noqa: E402  (reuse cache + polite UA)

LISTING_URL = "https://portergeo.com.au/database/display.php"
PAGE_URL = "https://portergeo.com.au/database/mineinfo.php?mineid="

# A name unique in PorterGeo can still be COMMON in our data ("Escondida" = "hidden" names
# dozens of small Latin-American deposits). Linking all of them to one famous page is wrong,
# so only link a name that is also LOCALIZED on our side: its records occupy few ~1° cells
# (one site, possibly listed several times) rather than scattering across the map. Counting
# cells, not records, so an un-merged but co-located major (Olympic Dam ×8) still counts as one.
MAX_NAME_CELLS = 2

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
    """The PorterGeo URL for a deposit, or None if no confident match (pure / testable).

    Requires the name to match AND the commodity to be compatible (so a gold "Eagle" never
    links to a nickel "Eagle"). A name unique to one PorterGeo deposit links when our country
    is unknown or agrees; an ambiguous name needs an exact country match."""
    c = _canon(name or "")
    if not c or c not in byname:
        return None
    co = _country(country)
    # keep only commodity-compatible candidates
    compat = [
        (cc, mid)
        for (cc, buckets, mid) in byname[c]
        if commodity == "other" or not buckets or commodity in buckets
    ]
    ids = {mid for _, mid in compat}
    if len(ids) == 1:
        mid = next(iter(ids))
        countries = {cc for cc, m in compat if m == mid}
        if not co or co in countries:        # unique name + country agrees (or unknown)
            return PAGE_URL + mid
        return None
    if co:                                   # ambiguous name -> need an exact country match
        hit = {mid for (cc, mid) in compat if cc == co}
        if len(hit) == 1:
            return PAGE_URL + next(iter(hit))
    return None


def add_links(df, byname: dict[str, set] | None = None):
    """Attach a `porterUrl` column to a (deduped) frame. Returns (df, n_linked)."""
    df = df.copy()
    if byname is None:
        try:
            path = ensure_cached(LISTING_URL, "portergeo_listing.html")
            byname = load_index(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:  # network/parse failure: degrade to no links, don't break build
            print(f"  PorterGeo: skipped ({e})")
            df["porterUrl"] = None
            return df, 0
    canons = [_canon(n or "") for n in df["name"]]
    cells: dict[str, set] = defaultdict(set)  # distinct ~1° cells each name occupies
    for cn, lat, lng in zip(canons, df["lat"], df["lng"]):
        if cn:
            cells[cn].add((round(float(lat)), round(float(lng))))
    urls = [
        link_for(n, c, b, byname) if (cn and len(cells[cn]) <= MAX_NAME_CELLS) else None
        for n, cn, c, b in zip(df["name"], canons, df["country"], df["commodity"])
    ]
    df["porterUrl"] = urls
    return df, sum(1 for u in urls if u)
