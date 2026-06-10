"""
Shared normalization — the single source of truth for commodity bucketing, secondary
commodities, and status harmonization. Every source loader and the orchestrator reuse
these; no source does its own bucketing.

Extracted verbatim from the original single-source prepare-data.py so the MRDS path stays
byte-for-byte identical, then generalized to take an ORDERED LIST of raw commodity fields
(so a source with one delimited field and MRDS with commod1/2/3 share the same code).
"""

from __future__ import annotations

import re

# --- commodity normalization --------------------------------------------------
# Match on the upper-cased token. Symbols require an EXACT token match; everything
# else matches as a substring (so "RARE EARTH", "SPODUMENE", "MONAZITE" etc. catch).
COMMODITY_MAP: dict[str, list[str]] = {
    "gold":    ["GOLD", "AU"],
    "copper":  ["COPPER", "CU"],
    "lithium": ["LITHIUM", "LI", "SPODUMENE", "PETALITE", "LEPIDOLITE"],
    "cobalt":  ["COBALT", "CO"],
    "nickel":  ["NICKEL", "NI"],
    "ree":     ["RARE EARTH", "RARE-EARTH", "REE", "CERIUM", "LANTHANUM",
                "NEODYMIUM", "PRASEODYMIUM", "YTTRIUM", "SAMARIUM", "EUROPIUM",
                "GADOLINIUM", "DYSPROSIUM", "TERBIUM", "MONAZITE", "BASTNASITE",
                "BASTNAESITE"],
    "zinc":    ["ZINC", "ZN"],
    "uranium": ["URANIUM", "U3O8", "URANINITE", "PITCHBLENDE", "U"],
    "silver":  ["SILVER", "AG"],
    # --- focused palette expansion: the commodities that fill Africa/Australia/Canada ---
    "iron":      ["IRON", "HEMATITE", "MAGNETITE", "TACONITE", "FE"],
    "bauxite":   ["BAUXITE", "ALUMINUM", "ALUMINIUM", "ALUMINA", "GIBBSITE", "AL"],
    "platinum":  ["PLATINUM", "PALLADIUM", "RHODIUM", "IRIDIUM", "OSMIUM", "RUTHENIUM",
                  "PLATINUM-GROUP", "PLATINUM GROUP", "PGE", "PGM", "PT", "PD"],
    "manganese": ["MANGANESE", "PYROLUSITE", "MN"],
    # Catch-all for the remaining strategic/critical metals & minerals (kept, not dropped).
    "other_metals": ["TIN", "CASSITERITE", "SN", "CHROMIUM", "CHROME", "CHROMITE", "CR",
                     "TUNGSTEN", "WOLFRAM", "WOLFRAMITE", "SCHEELITE", "ANTIMONY", "STIBNITE",
                     "SB", "MOLYBDENUM", "MOLYBDENITE", "MO", "VANADIUM", "TANTALUM",
                     "TANTALITE", "COLUMBITE", "NIOBIUM", "BERYLLIUM", "BERYL", "TITANIUM",
                     "ILMENITE", "RUTILE", "ZIRCONIUM", "ZIRCON", "MAGNESIUM", "MAGNESITE",
                     "BISMUTH", "MERCURY", "CINNABAR", "GALLIUM", "GERMANIUM", "INDIUM",
                     "RHENIUM", "SELENIUM", "TELLURIUM", "SCANDIUM", "HAFNIUM", "CADMIUM",
                     "GRAPHITE", "FLUORITE", "FLUORSPAR", "FLUORINE", "BARITE", "BARYTE"],
}

# Short element symbols — exact token match only, never substring, otherwise "CO"
# would hit COPPER/COBALT and "U" would hit everything (or "TIN" inside "PLATINUM").
SYMBOL_KEYS = {"AU", "CU", "LI", "CO", "NI", "ZN", "AG", "U", "FE", "AL", "PT", "PD",
               "MN", "SN", "CR", "MO", "SB", "TA", "NB", "BE", "TI", "ZR", "MG", "BI",
               "HG", "GA", "GE", "RE", "SE", "TE", "SC", "HF", "CD"}

# Split a commodity field on ; , / and the standalone word "and" (word-boundaried so
# "Sand and Gravel" splits but the "AND" inside "SAND" does not).
SPLIT_RE = re.compile(r"[;,/]|\bAND\b")

NAMED_BUCKETS = list(COMMODITY_MAP.keys())

# Industrial/aggregate tokens that aren't interesting "co-commodity" context for a metal
# site — dropped from the secondary list so it stays meaningful.
SECONDARY_SKIP = {
    "SAND", "GRAVEL", "STONE", "CONSTRUCTION", "CRUSHED", "BROKEN", "GENERAL",
    "DIMENSION", "CLAY", "LIMESTONE", "SLATE",
}


def tokens_from(field) -> list[str]:
    if not isinstance(field, str) or not field.strip():
        return []
    parts = SPLIT_RE.split(field.upper())
    return [p.strip() for p in parts if p.strip()]


def bucket_for_token(tok: str) -> str | None:
    for bucket, keys in COMMODITY_MAP.items():
        for kw in keys:
            if kw in SYMBOL_KEYS:
                if tok == kw:
                    return bucket
            elif kw in tok:  # substring contains for full names / mineral names
                return bucket
    return None


def classify(commodities) -> str:
    """First token (in field order, primary first) that matches a named bucket wins;
    otherwise 'other'. `commodities` is an ordered list of raw commodity field strings."""
    for field in commodities:
        for tok in tokens_from(field):
            b = bucket_for_token(tok)
            if b is not None:
                return b
    return "other"


def secondary_names(commodities, primary_bucket: str, limit: int = 5) -> list[str]:
    """Other commodities recorded at the site (the card's 'Also present' line): distinct,
    in field order, excluding tokens of the primary bucket and bulk industrial materials."""
    out: list[str] = []
    for field in commodities:
        for tok in tokens_from(field):
            if tok in SECONDARY_SKIP or bucket_for_token(tok) == primary_bucket:
                continue
            name = tok.title()
            if name not in out:
                out.append(name)
                if len(out) >= limit:
                    return out
    return out


# --- status harmonization -----------------------------------------------------
# Output statuses: 'producer' (currently producing), 'past' (former producer),
# 'deposit' (known deposit, operating status unknown — most catalog sources).
_PRODUCING = ("operat", "active", "producing", "producer", "in production")
_FORMER = ("past", "former", "closed", "abandon", "inactive", "historic", "ceased")


def status_for(status_raw, source: str) -> str:
    if source == "mrds":
        return {"Producer": "producer", "Past Producer": "past"}.get(status_raw, "deposit")
    s = status_raw.strip().lower() if isinstance(status_raw, str) else ""
    if not s:
        return "deposit"
    if any(k in s for k in _FORMER):
        return "past"
    if any(k in s for k in _PRODUCING):
        return "producer"
    return "deposit"


# --- deposit type vs. mining technique ----------------------------------------
# Several sources record the EXTRACTION METHOD ("Open-pit", "Underground") or a FACILITY
# label ("Mine", "Concentrator", "Plant") in their deposit-type field. Those describe how a
# site is worked, not its geology, so they're split out: methods go to a Mining-technique
# field, bare facility words are dropped, and only the real geological type is kept.
# NOTE: "Placer" is a genuine deposit type (an alluvial concentration) — NOT a method — so it
# is deliberately absent here and stays in depositType.
_METHOD_RULES = [
    (re.compile(r"open[\s-]?pit|open[\s-]?cast|opencast", re.I), "Open-pit"),
    (re.compile(r"\bunderground\b", re.I), "Underground"),
    (re.compile(r"\bsurface\b", re.I), "Surface"),
    (re.compile(r"\bstrip\b", re.I), "Strip"),
    (re.compile(r"\bdredg", re.I), "Dredging"),
    (re.compile(r"heap[\s-]?leach", re.I), "Heap leach"),
    (re.compile(r"in[\s-]?situ|solution min", re.I), "In-situ leach"),
    (re.compile(r"\bhydraulic\b", re.I), "Hydraulic"),
]
# Facility / operation words that aren't a deposit type and aren't a technique worth keeping.
_FACILITY = re.compile(
    r"\b(mine|mines|concentrator|concentrators|plant|plants|refinery|refineries|"
    r"smelter|smelters|mill|mills|works|quarry|quarries)\b",
    re.I,
)
_DT_SPLIT = re.compile(r"[,;/]|\band\b", re.I)


def split_deposit_type(raw) -> tuple[str | None, str | None]:
    """(deposit_type, mining_technique) from a raw deposit-type string. Method tokens move to
    the technique; bare facility tokens are dropped; geological tokens are kept (in order)."""
    if not isinstance(raw, str) or not raw.strip():
        return None, None
    kept, methods = [], []
    for part in _DT_SPLIT.split(raw):
        tok = part.strip()
        if not tok:
            continue
        matched = [label for rx, label in _METHOD_RULES if rx.search(tok)]
        if matched:
            for m in matched:
                if m not in methods:
                    methods.append(m)
        elif _FACILITY.search(tok):
            continue  # facility/operation word — not a deposit type
        else:
            kept.append(tok)
    return (", ".join(kept) or None, ", ".join(methods) or None)
