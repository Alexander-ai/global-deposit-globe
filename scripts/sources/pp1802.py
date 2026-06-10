"""USGS "Global Distribution of Selected Mines, Deposits, and Districts of Critical
Minerals" (Professional Paper 1802) — global, 150 countries, 22 critical commodities."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, read_shp_records

ID = "pp1802"
LABEL = "USGS Global Critical Minerals"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2017"
PRIORITY = 55
STATUS_KEEP = None

URL = ("https://www.sciencebase.gov/catalog/file/get/594d3c8ee4b062508e39b332?"
       "f=__disk__0a%2Fd5%2F3c%2F0ad53ca985bbc6ac61a3587176a0c37b57ac8053")
BASENAME = "PP1802_CritMin_pts"


def load() -> pd.DataFrame:
    recs = read_shp_records(ensure_cached(URL, "pp1802.zip"), BASENAME, encoding="latin-1")
    raw = pd.DataFrame(recs)
    return pd.DataFrame({
        "magnitude": 1.7,  # globally significant critical-mineral deposits/districts
        "name": raw["DEPOSIT_NA"],
        "lat": raw["LATITUDE"],
        "lng": raw["LONGITUDE"],
        "commodities": [[c] for c in raw["CRITICAL_M"]],
        "status_raw": None,
        "depositType": raw["DEPOSIT_TY"],
        "source": ID,
        "country": raw["LOCATION"],
        "source_id": None,
    })
