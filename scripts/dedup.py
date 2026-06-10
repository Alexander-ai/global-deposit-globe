"""
Cross-source de-duplication. The same major mine appears in MRDS + MINFAC + porphyry-Cu;
merge true duplicates without merging distinct nearby deposits.

Conservative and deterministic — biased to FALSE-SPLIT (a missed merge = a faint doubled
dot, honest; a wrong merge silently deletes a real deposit). Every merge is logged via the
stats returned to the orchestrator.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

import pandas as pd
from rapidfuzz.fuzz import token_set_ratio

import normalize
from sources import SOURCES

PRIORITY = {s.ID: s.PRIORITY for s in SOURCES}  # lower = preferred survivor

MERGE_KM = 1.5    # max distance for a FUZZY-name candidate duplicate
CLOSE_KM = 0.2    # below this, loosen the name requirement
UNNAMED_KM = 0.3  # unnamed points only merge if this close AND same bucket
DIAM_KM = 3.0     # a fuzzy cluster wider than this is too diffuse -> keep all

# Name-anchored matching is trusted far (different databases geocode the same mine km
# apart; some sources list one site once per commodity). But ONLY for LOCALIZED names: a
# name occupying few ~1° cells is one mine, so same-named records within 100 km are merged
# (the owner's call). A name scattered across many cells is a common name ("Gold King" =
# 81 distinct mines) and gets the tight radius instead.
EXACT_NAME_KM = 100.0          # localized name, compatible commodity
EXACT_NAME_XBUCKET_KM = 15.0   # localized name, conflicting commodity buckets
SAME_SRC_NAME_KM = 2.0         # within one source: near-coincident only (per-commodity dups)
COMMON_NAME_KM = 2.0           # dispersed/common names: tight, regardless of source
DISPERSE_CELLS = 3             # a name in > this many 1° cells is "common" (many mines)
NAME_DIAM_KM = 150.0           # diameter cap for clusters united by one localized name
GRID = 0.02       # ~2 km blocking grid (fuzzy pass)

# Only strip genuinely generic descriptors. Directional/ordinal words (north, south, no. 5,
# upper, new) are DISTINGUISHING — keeping them prevents merging distinct neighbours.
# Facility words (mine/plant/refinery/smelter…) are stripped so "Mufulira Mine",
# "Mufulira Refinery" and "Plant near Mufulira" canonicalize to the same site name.
_NOISE = re.compile(
    r"\b(mine|mines|deposit|deposits|prospect|prospects|project|workings|occurrence|"
    r"occurrences|claim|claims|plant|plants|refinery|refineries|smelter|smelters|"
    r"mill|mills|facility|quarry|quarries|pit|pits|open|near|at)\b"
)


def _haversine_km(a_lat, a_lng, b_lat, b_lng) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _canon(name) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    n = _NOISE.sub(" ", n)
    return " ".join(n.split())


def _raw_tokens(commodities) -> set:
    return {t for f in commodities for t in normalize.tokens_from(f)}


# Commodity words inside NAMES ("Musselwhite Gold Mine") are non-distinguishing — the
# commodity lives in the data. Used to pick the name's distinctive anchor token.
_COMMODITY_WORDS = {
    kw.lower() for kws in normalize.COMMODITY_MAP.values() for kw in kws if " " not in kw
} | {"gold", "silver", "copper", "zinc", "lead", "nickel", "iron", "uranium", "lithium",
     "cobalt", "manganese", "bauxite", "alumina", "aluminum", "aluminium", "platinum",
     "coal", "diamond", "diamonds", "potash", "salt", "phosphate", "rare", "earth"}


def _anchor(canon_name: str) -> str | None:
    """The name's first distinctive token (len >= 5, not a commodity word) — the blocking
    key for core-name matching ("Musselwhite Gold Mine" -> "musselwhite")."""
    for t in canon_name.split():
        if len(t) >= 5 and t not in _COMMODITY_WORDS:
            return t
    return None


def _bucket_compat(a, b) -> bool:
    """Commodities are compatible (same bucket, either unbucketed, or share a raw token)."""
    return (
        a["commodity"] == b["commodity"]
        or a["commodity"] == "other"
        or b["commodity"] == "other"
        or bool(_raw_tokens(a["commodities"]) & _raw_tokens(b["commodities"]))
    )


def _name_match(a_name, b_name, dist_km):
    """True/False if both named; None if one/both effectively unnamed."""
    ca, cb = _canon(a_name), _canon(b_name)
    if not ca or not cb:
        return None
    if ca == cb:
        return True
    ratio = token_set_ratio(ca, cb)
    if dist_km <= CLOSE_KM:
        return ratio >= 80
    return ratio >= 90


def _can_merge(a, b) -> tuple[bool, float]:
    # Cross-source only. A source's own near-duplicates are its inherent noise (and the
    # exact-coord dedup already removed its exact dups); fuzzy-merging within one source
    # risks deleting distinct numbered workings ("Kidd Ranch #1" vs "#5").
    if a["source"] == b["source"]:
        return False, 0.0
    d = _haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    if d > MERGE_KM:
        return False, d
    # Commodity guard: distinct non-"other" buckets with no shared raw token -> keep both.
    if (
        a["commodity"] != "other"
        and b["commodity"] != "other"
        and a["commodity"] != b["commodity"]
        and not (_raw_tokens(a["commodities"]) & _raw_tokens(b["commodities"]))
    ):
        return False, d
    nm = _name_match(a["name"], b["name"], d)
    if nm is None:
        # One/both unnamed: only merge ACROSS sources (don't collapse a source's own
        # distinct unnamed occurrences), and only when very close + same bucket.
        cross = a["source"] != b["source"]
        return (cross and d <= UNNAMED_KM and a["commodity"] == b["commodity"]), d
    return nm, d


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _completeness(r) -> int:
    return (
        bool(r["name"]) + bool(r["depositType"]) + bool(r["status_raw"])
        + bool(r["country"]) + len(_raw_tokens(r["commodities"]))
    )


def merge(df: pd.DataFrame):
    """Collapse duplicate clusters. Returns (deduped_frame, stats) where stats has the
    removed count, merges by source-pair, and the widest accepted merges for audit."""
    from collections import Counter as _Counter
    rows = df.to_dict("records")
    n = len(rows)
    stats = {"removed": 0, "by_pair": _Counter(), "widest": []}

    # Spatial blocking: bucket each row into a coarse cell.
    cells = defaultdict(list)
    for i, r in enumerate(rows):
        cells[(round(r["lat"] / GRID), round(r["lng"] / GRID))].append(i)

    uf = _UF(n)
    # ---- pass 1: spatial blocking + fuzzy-name rules (close range, conservative) ----
    for (cx, cy), idxs in cells.items():
        # candidates = this cell + 8 neighbours, comparing each ordered pair once
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(cells.get((cx + dx, cy + dy), ()))
        for a in idxs:
            for b in cand:
                if b <= a:
                    continue
                ok, _ = _can_merge(rows[a], rows[b])
                if ok:
                    uf.union(a, b)

    # ---- pass 2: name-anchored matching (wide range) -------------------------
    # Catches the same site listed once per commodity, geocoded km apart by different
    # databases, or under name VARIANTS sharing the core name ("Musselwhite" vs
    # "Musselwhite Gold Mine"): canon token-sets that are equal or subset-contained
    # count as the same name.
    canon = [_canon(r["name"]) for r in rows]
    toks = [frozenset(c.split()) for c in canon]
    anchor_of = [_anchor(c) for c in canon]

    # Geographic dispersion: the set of 1° cells each name/anchor/distinctive-token occupies.
    # A localized name (few cells) is one mine; a name scattered across many cells is a
    # common label ("Gold King" = 81 mines, "Unnamed Iron Deposit" = thousands).
    anchor_cells = defaultdict(set)
    canon_cells = defaultdict(set)
    token_cells = defaultdict(set)
    for i, r in enumerate(rows):
        cell = (round(r["lat"]), round(r["lng"]))
        if anchor_of[i]:
            anchor_cells[anchor_of[i]].add(cell)
        if len(canon[i]) >= 4:
            canon_cells[canon[i]].add(cell)
        for t in toks[i]:
            if len(t) >= 5 and t not in _COMMODITY_WORDS:
                token_cells[t].add(cell)

    def _localized(i: int) -> bool:
        """True if this record's name names ONE mine (few cells), not a common name."""
        an = anchor_of[i]
        cells = anchor_cells[an] if an else canon_cells[canon[i]]
        return len(cells) <= DISPERSE_CELLS

    def _localized_token(t: str) -> bool:
        """A distinctive token that occupies few cells (so it names one site, not a type)."""
        return len(t) >= 5 and t not in _COMMODITY_WORDS and len(token_cells[t]) <= DISPERSE_CELLS

    def _name_pair(a: int, b: int) -> None:
        ra, rb = rows[a], rows[b]
        d = _haversine_km(ra["lat"], ra["lng"], rb["lat"], rb["lng"])
        localized = _localized(a) and _localized(b)
        if ra["source"] == rb["source"]:
            # Within a source: a truly-named site merges its variants (Malmberget /
            # Malmberget Mine); a generic label ("Unnamed Iron Deposit") only merges when
            # near-coincident, so distinct occurrences 1-2 km apart are preserved.
            lim = SAME_SRC_NAME_KM if localized else CLOSE_KM
        elif not localized:
            lim = COMMON_NAME_KM    # common name across sources: tight
        else:
            lim = EXACT_NAME_KM if _bucket_compat(ra, rb) else EXACT_NAME_XBUCKET_KM
        if d <= lim:
            uf.union(a, b)

    # 2a — identical canonical names (works even when no anchor token exists).
    groups = defaultdict(list)
    for i, cn in enumerate(canon):
        if len(cn) >= 4:
            groups[cn].append(i)
    for idxs in groups.values():
        if len(idxs) < 2 or len(idxs) > 400:  # hyper-common names: leave to pass 1
            continue
        for k, a in enumerate(idxs):
            for b in idxs[k + 1:]:
                _name_pair(a, b)

    # 2b — core-name variants, blocked by the distinctive anchor token; a pair matches
    # when one name's token set contains the other's.
    anchors = defaultdict(list)
    for i, cn in enumerate(canon):
        an = _anchor(cn)
        if an:
            anchors[an].append(i)
    for idxs in anchors.values():
        if len(idxs) < 2 or len(idxs) > 400:
            continue
        for k, a in enumerate(idxs):
            for b in idxs[k + 1:]:
                if toks[a] <= toks[b] or toks[b] <= toks[a]:
                    _name_pair(a, b)

    comps = defaultdict(list)
    for i in range(n):
        comps[uf.find(i)].append(i)

    drop = set()
    for members in comps.values():
        if len(members) < 2:
            continue
        # Chain-sweep guard: a cluster may span the wide name radius ONLY if every member
        # shares one LOCALIZED distinctive token (a true site name like "musselwhite", in
        # few cells) — not a generic descriptor ("unnamed", "diggings") that appears in
        # thousands of cells and would chain distinct sites across a whole region.
        shared = frozenset.intersection(*(toks[i] for i in members)) if members else frozenset()
        one_name = any(_localized_token(t) for t in shared)
        cap = NAME_DIAM_KM if one_name else DIAM_KM
        diffuse = any(
            _haversine_km(rows[i]["lat"], rows[i]["lng"], rows[j]["lat"], rows[j]["lng"]) > cap
            for k, i in enumerate(members) for j in members[k + 1:]
        )
        if diffuse:
            continue
        # Canonical survivor: source priority -> completeness -> deterministic tuple.
        survivor = min(
            members,
            key=lambda i: (
                PRIORITY.get(rows[i]["source"], 999),
                -_completeness(rows[i]),
                str(rows[i]["source"]), str(rows[i]["source_id"]),
                rows[i]["lat"], rows[i]["lng"],
            ),
        )
        s = rows[survivor]
        # Provenance: how many distinct databases corroborate this site (shown in the card).
        s["corrob"] = len({rows[i]["source"] for i in members})
        # Magnitude: a site is as big as its biggest estimate across sources.
        s["magnitude"] = max(float(rows[i].get("magnitude") or 0) for i in members) or None
        for i in members:
            if i == survivor:
                continue
            o = rows[i]
            if not s["depositType"] and o["depositType"]:
                s["depositType"] = o["depositType"]
            if not s.get("miningTechnique") and o.get("miningTechnique"):
                s["miningTechnique"] = o["miningTechnique"]
            if not s["country"] and o["country"]:
                s["country"] = o["country"]
            # Union co-commodities (survivor order first) so 'also' reflects all sources.
            s["commodities"] = list(s["commodities"]) + [
                f for f in o["commodities"] if f not in s["commodities"]
            ]
            drop.add(i)
            d = _haversine_km(s["lat"], s["lng"], o["lat"], o["lng"])
            pair = tuple(sorted((s["source"], o["source"])))
            stats["by_pair"][pair] += 1
            stats["widest"].append((d, f"{o['name']}/{o['source']}", f"{s['name']}/{s['source']}"))

    stats["removed"] = len(drop)
    stats["widest"].sort(reverse=True)
    stats["widest"] = stats["widest"][:10]
    keep = [i for i in range(n) if i not in drop]
    return pd.DataFrame([rows[i] for i in keep]), stats
