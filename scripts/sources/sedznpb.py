"""USGS Sediment-hosted Zinc-Lead Deposits of the World — global zinc (with Pb/Ag/Cu)."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, mag_from_tonnage, read_csv_zip

ID = "sedznpb"
LABEL = "USGS Sediment-hosted Zn-Pb of the World"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2009"
PRIORITY = 60
STATUS_KEEP = None

URL = "https://mrdata.usgs.gov/sedznpb/sedznpb-csv.zip"


def load() -> pd.DataFrame:
    raw = read_csv_zip(ensure_cached(URL, "sedznpb-csv.zip"), "sedznpb/main.csv")
    pb = pd.to_numeric(raw["pbgrd"], errors="coerce").fillna(0)
    cu = pd.to_numeric(raw["cugrd"], errors="coerce").fillna(0)
    ag = pd.to_numeric(raw["aggrd"], errors="coerce").fillna(0)
    commodities = []
    for p, c_, s in zip(pb, cu, ag):
        c = ["Zinc"]  # the Zn-Pb catalog -> zinc bucket; lead/silver/copper as secondaries
        if p > 0:
            c.append("Lead")
        if c_ > 0:
            c.append("Copper")
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
        "depositType": "Sediment-hosted Zn-Pb",
        "source": ID,
        "country": raw["country"],
        "source_id": raw["rec_id"],
    })
