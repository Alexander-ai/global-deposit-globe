"""USGS Mineral Resources Data System (MRDS) — global, US-heavy, historical (frozen 2011)."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, read_csv_zip

ID = "mrds"
LABEL = "USGS MRDS"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "not updated since 2011"
PRIORITY = 100  # lowest priority canonical (noisiest); highest number = picked last
# MRDS is ~305k sites; keep only current/past producers so the map stays legible.
STATUS_KEEP = {"Producer", "Past Producer"}

URL = "https://mrdata.usgs.gov/mrds/mrds-csv.zip"
_COLS = ["site_name", "latitude", "longitude", "commod1", "commod2", "commod3",
         "dep_type", "dev_stat", "country", "prod_size"]

# Production-size letter -> magnitude (drives dot size). L/M/S is the modern coding;
# Y/N is an older yes/no producer flag.
_MAG = {"L": 3.0, "M": 2.4, "S": 1.7, "Y": 1.8, "N": 1.2, "U": 1.3}


def load() -> pd.DataFrame:
    path = ensure_cached(URL, "mrds-csv.zip")
    raw = read_csv_zip(path, "mrds.csv", encoding="latin-1", usecols=_COLS)
    return pd.DataFrame({
        "magnitude": [_MAG.get(p, 1.3) for p in raw["prod_size"].fillna("")],
        "name": raw["site_name"],
        "lat": raw["latitude"],
        "lng": raw["longitude"],
        "commodities": raw[["commod1", "commod2", "commod3"]].values.tolist(),
        "status_raw": raw["dev_stat"],
        "depositType": raw["dep_type"],
        "source": ID,
        "country": raw["country"],
        "source_id": None,
    })
