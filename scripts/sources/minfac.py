"""USGS Mineral Operations Outside the United States (MINFAC) — global mines/plants by commodity."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, read_csv_zip

ID = "minfac"
LABEL = "USGS Mineral Operations (outside US)"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "compiled ~2003–2010"
PRIORITY = 40  # current operations; preferred over MRDS, below curated national/world sets
STATUS_KEEP = None  # keep all (already a curated operations list)

URL = "https://mrdata.usgs.gov/mineral-operations/minfac-csv.zip"
_COLS = ["rec_id", "country", "commodity", "fac_name", "fac_type",
         "latitude", "longitude", "status"]


def load() -> pd.DataFrame:
    path = ensure_cached(URL, "minfac-csv.zip")
    raw = read_csv_zip(path, "minfac.csv", encoding="latin-1", usecols=_COLS)
    return pd.DataFrame({
        "magnitude": 1.8,  # nationally significant operating facilities
        "name": raw["fac_name"],
        "lat": raw["latitude"],
        "lng": raw["longitude"],
        "commodities": [[c] for c in raw["commodity"]],
        "status_raw": raw["status"],
        "depositType": raw["fac_type"],
        "source": ID,
        "country": raw["country"],
        "source_id": raw["rec_id"],
    })
