"""USGS Global Rare Earth Element Occurrence Database — global REE deposits."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, read_csv_zip

ID = "ree"
LABEL = "USGS Global REE database"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2018"
PRIORITY = 60
STATUS_KEEP = None

URL = "https://mrdata.usgs.gov/ree/ree-csv.zip"


def load() -> pd.DataFrame:
    raw = read_csv_zip(ensure_cached(URL, "ree-csv.zip"), "ree/main.csv")
    return pd.DataFrame({
        "magnitude": 1.5,
        "name": raw["depname"],
        "lat": raw["latitude"],
        "lng": raw["longitude"],
        "commodities": [["Rare Earth"]] * len(raw),
        "status_raw": raw["status"],
        "depositType": "Rare-earth deposit",
        "source": ID,
        "country": raw["country"],
        "source_id": raw["rec_id"],
    })
