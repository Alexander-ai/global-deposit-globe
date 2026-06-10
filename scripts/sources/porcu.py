"""USGS Porphyry Copper Deposits of the World — global copper (with Au/Ag/Mo by grade)."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, mag_from_tonnage, read_csv_zip

ID = "porcu"
LABEL = "USGS Porphyry Copper of the World"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2008"
PRIORITY = 60
STATUS_KEEP = None

URL = "https://mrdata.usgs.gov/porcu/porcu-csv.zip"


def load() -> pd.DataFrame:
    raw = read_csv_zip(ensure_cached(URL, "porcu-csv.zip"), "porcu/main.csv")
    au = pd.to_numeric(raw["augrd"], errors="coerce").fillna(0)
    ag = pd.to_numeric(raw["aggrd"], errors="coerce").fillna(0)
    mo = pd.to_numeric(raw["mogrd"], errors="coerce").fillna(0)
    commodities = []
    for a, s, m in zip(au, ag, mo):
        c = ["Copper"]
        if m > 0:
            c.append("Molybdenum")
        if a > 0:
            c.append("Gold")
        if s > 0:
            c.append("Silver")
        commodities.append(c)
    name = raw["depname"].fillna("").where(raw["depname"].fillna("").str.strip() != "",
                                           raw["altname"])
    return pd.DataFrame({
        "magnitude": mag_from_tonnage(raw["oreton"]),
        "name": name,
        "lat": raw["latitude"],
        "lng": raw["longitude"],
        "commodities": commodities,
        "status_raw": None,
        "depositType": "Porphyry copper",
        "source": ID,
        "country": raw["country"],
        "source_id": raw["rec_id"],
    })
