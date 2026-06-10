"""Saskatchewan Mineral Deposits Index (SMDI) — kept to significant deposits (producers or
sites with defined reserves/resources), heavy on Athabasca Basin uranium. OGL-Saskatchewan."""

from __future__ import annotations

import json

import pandas as pd

from .base import fetch_arcgis_geojson

ID = "sk_smdi"
LABEL = "Saskatchewan SMDI"
LICENSE = "Open Government Licence – Saskatchewan"
VINTAGE = "current"
PRIORITY = 66
STATUS_KEEP = None

QUERY = ("https://gis.saskatchewan.ca/egis/rest/services/Economy/Mineral_Exploration/"
         "FeatureServer/2/query")


def load() -> pd.DataFrame:
    path = fetch_arcgis_geojson(QUERY, "sk-smdi.geojson")
    g = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for f in g["features"]:
        p = f["properties"]
        if p.get("PRODUCTION") != "Yes" and p.get("RESERVESRESOURCES") != "Yes":
            continue  # drop pure exploration occurrences
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates") or [None, None]
        commods = [p.get("PRIMARYCOMMODITIES"), p.get("ASSOCIATEDCOMMODITIES")]
        rows.append({
            "magnitude": 2.0 if p.get("PRODUCTION") == "Yes" else 1.5,
            "name": p.get("NAME"),
            "lat": coords[1],
            "lng": coords[0],
            "commodities": [c for c in commods if c],
            "status_raw": "Producer" if p.get("PRODUCTION") == "Yes" else "Deposit",
            "depositType": p.get("DISCOVERYTYPE"),
            "source": ID,
            "country": "Canada",
            "source_id": p.get("SMDI"),
        })
    return pd.DataFrame(rows)
