"""USGS Volcanogenic Massive Sulfide Deposits of the World — global polymetallic (Cu/Zn/Pb/Au/Ag)."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, mag_from_tonnage, read_csv_zip

ID = "vms"
LABEL = "USGS VMS Deposits of the World"
LICENSE = "public domain (U.S. Government)"
VINTAGE = "2009"
PRIORITY = 60
STATUS_KEEP = None

URL = "https://mrdata.usgs.gov/vms/vms-csv.zip"


def load() -> pd.DataFrame:
    raw = read_csv_zip(ensure_cached(URL, "vms-csv.zip"), "vms/main.csv")
    cu = pd.to_numeric(raw["cugrd"], errors="coerce").fillna(0)
    zn = pd.to_numeric(raw["zngrd"], errors="coerce").fillna(0)
    pb = pd.to_numeric(raw["pbgrd"], errors="coerce").fillna(0)
    au = pd.to_numeric(raw["augrd"], errors="coerce").fillna(0)
    ag = pd.to_numeric(raw["aggrd"], errors="coerce").fillna(0)
    commodities = []
    for c_, z, p, a, s in zip(cu, zn, pb, au, ag):
        prim, other = ("Copper", "Zinc") if c_ >= z else ("Zinc", "Copper")
        c = [prim]
        if (z if prim == "Copper" else c_) > 0:
            c.append(other)
        if p > 0:
            c.append("Lead")
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
        "depositType": "Volcanogenic massive sulfide",
        "source": ID,
        "country": raw["country"],
        "source_id": raw["rec_id"],
    })
