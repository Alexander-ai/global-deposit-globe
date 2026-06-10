"""
Country/coordinate consistency check (improvement #2).

Builds per-country bounding boxes from the Natural Earth countries GeoJSON the app already
ships (public/ne_110m_admin_0_countries.geojson), then flags records whose coordinates fall
well outside their stated country — catching lat/lng swaps, sign errors, and gross geocodes.
Conservative: if the country can't be resolved, the record is KEPT (never drop on a guess).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "public" / "ne_110m_admin_0_countries.geojson"
BUFFER_DEG = 3.0  # allow border/coast/island slop before calling a mismatch

# Common data-spelling -> Natural Earth NAME normalization (normalized, alnum-only keys).
_ALIAS = {
    "unitedstates": "unitedstatesofamerica",
    "usa": "unitedstatesofamerica",
    "us": "unitedstatesofamerica",
    "congokinshasa": "democraticrepublicofthecongo",
    "drcongo": "democraticrepublicofthecongo",
    "democraticrepublicofcongo": "democraticrepublicofthecongo",
    "congobrazzaville": "republicofthecongo",
    "congo": "republicofthecongo",
    "tanzania": "unitedrepublicoftanzania",
    "southkorea": "southkorea",
    "northkorea": "northkorea",
    "ivorycoast": "cotedivoire",
    "burma": "myanmar",
    "czechrepublic": "czechia",
    "laos": "laos",
    "russia": "russia",
    "iran": "iran",
    "syria": "syria",
    "vietnam": "vietnam",
    "bolivia": "bolivia",
    "venezuela": "venezuela",
    "tanzaniaunitedrepublicof": "unitedrepublicoftanzania",
    "macedonia": "northmacedonia",
}

_BBOX: dict[str, tuple] | None = None


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def _bbox_of(geom) -> tuple:
    minx = miny = 1e9
    maxx = maxy = -1e9

    def walk(coords):
        nonlocal minx, miny, maxx, maxy
        if coords and isinstance(coords[0], (int, float)):
            x, y = coords[0], coords[1]
            minx, maxx = min(minx, x), max(maxx, x)
            miny, maxy = min(miny, y), max(maxy, y)
        else:
            for c in coords:
                walk(c)

    walk(geom["coordinates"])
    return (minx, miny, maxx, maxy)


def _union(a: tuple, b: tuple) -> tuple:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _table() -> dict[str, tuple]:
    global _BBOX
    if _BBOX is not None:
        return _BBOX
    _BBOX = {}
    g = json.loads(GEOJSON.read_text(encoding="utf-8"))
    for f in g["features"]:
        bb = _bbox_of(f["geometry"])
        p = f["properties"]
        # Use the country/geounit NAME fields only — NOT SOVEREIGNT, which groups overseas
        # territories under the parent (e.g. Kerguelen under "France") and would otherwise
        # give metropolitan France an Indian-Ocean bbox. Union across features with the same
        # name so multi-part countries accumulate.
        for key in ("NAME", "NAME_LONG", "ADMIN", "FORMAL_EN", "GEOUNIT"):
            v = p.get(key)
            if isinstance(v, str) and v.strip():
                n = _norm(v)
                _BBOX[n] = _union(_BBOX[n], bb) if n in _BBOX else bb
    return _BBOX


def _resolve(country) -> tuple | None:
    if not isinstance(country, str) or not country.strip():
        return None
    tbl = _table()
    key = _norm(country)
    key = _ALIAS.get(key, key)
    if key in tbl:
        return tbl[key]
    # last resort: a unique containment match
    hits = [bb for name, bb in tbl.items() if key and (key in name or name in key)]
    return hits[0] if len(hits) == 1 else None


def consistent(country, lat: float, lng: float) -> bool:
    """True if coords plausibly lie within the stated country (or country unknown)."""
    bb = _resolve(country)
    if bb is None:
        return True
    minx, miny, maxx, maxy = bb
    return (minx - BUFFER_DEG <= lng <= maxx + BUFFER_DEG
            and miny - BUFFER_DEG <= lat <= maxy + BUFFER_DEG)
