"""USGS "Mineral Industries of Africa" geospatial compilation — mines/deposits across 58
African countries (served as an ArcGIS FeatureServer)."""

from __future__ import annotations

import json

import pandas as pd

from .base import fetch_arcgis_geojson

ID = "usgs_africa"
LABEL = "USGS Mineral Industries of Africa"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2021"
PRIORITY = 45
STATUS_KEEP = None

QUERY = ("https://services2.arcgis.com/rtefou6JFIxFvYTf/arcgis/rest/services/"
         "AFR_Mineral_Facilities_shp/FeatureServer/0/query")
# Keep actual mineral sites; drop oil & gas fields/refineries.
KEEP_TYPES = {"Mines and Quarries", "Mineral Processing Plants", "Brine"}


def load() -> pd.DataFrame:
    path = fetch_arcgis_geojson(QUERY, "usgs-africa.geojson")
    g = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for f in g["features"]:
        p = f["properties"]
        if p.get("FeatureTyp") not in KEEP_TYPES:
            continue
        rows.append({
            "magnitude": 1.9,  # nationally significant mines/plants
            "name": p.get("FeatureNam"),
            "lat": p.get("Latitude"),
            "lng": p.get("Longitude"),
            "commodities": [p.get("DsgAttr02")],  # e.g. "Gold", "Iron and steel", "Platinum"
            "status_raw": p.get("LocOpStat"),        # "Assumed Active" / "Inactive" / ...
            "depositType": p.get("FeatureTyp"),
            "source": ID,
            "country": p.get("Country"),
            "source_id": p.get("FeatureUID"),
        })
    return pd.DataFrame(rows)
