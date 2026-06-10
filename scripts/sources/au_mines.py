"""Geoscience Australia — Australian Operating Mines (current producing mines, CC-BY)."""

from __future__ import annotations

import json
import re

import pandas as pd

from .base import ensure_cached

ID = "au_mines"
LABEL = "Geoscience Australia Operating Mines"
LICENSE = "CC-BY 4.0 (Geoscience Australia)"
VINTAGE = "2025"
PRIORITY = 35  # current national producers
STATUS_KEEP = None

URL = ("https://services.ga.gov.au/gis/rest/services/AustralianOperatingMines/MapServer/0/"
       "query?where=1%3D1&outFields=*&f=geojson&returnGeometry=true")


def _commodities(group: str) -> list[str]:
    """Parse GA's 'commodity_group' into ordered tokens, e.g.
    'Base metals - Cu (Zn, Pb, Mo, Ag, Au)' -> ['Cu ', 'Zn, Pb, Mo, Ag, Au']."""
    main = (group or "").split(" - ", 1)[-1]
    primary = main.split("(")[0]
    parens = re.findall(r"\(([^)]*)\)", main)
    return [primary] + parens


def load() -> pd.DataFrame:
    path = ensure_cached(URL, "au-mines.geojson")
    g = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for f in g["features"]:
        p = f["properties"]
        rows.append({
            "magnitude": 2.3,  # current national producing mines
            "name": p.get("name"),
            "lat": p.get("latitude"),
            "lng": p.get("longitude"),
            "commodities": _commodities(p.get("commodity_group", "")),
            "status_raw": p.get("status"),  # "Operating mine" -> producer
            "depositType": None,
            "source": ID,
            "country": "Australia",
            "source_id": p.get("objectid"),
        })
    return pd.DataFrame(rows)
