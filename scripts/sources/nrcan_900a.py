"""NRCan "900A" Principal Mineral Areas — current producing metal mines in Canada."""

from __future__ import annotations

import pandas as pd

from .base import ensure_cached, read_shp_records

ID = "nrcan"
LABEL = "NRCan 900A (Canada)"
LICENSE = "Open Government Licence – Canada"
VINTAGE = "2025"
PRIORITY = 30  # authoritative current national producers
STATUS_KEEP = None

URL = ("https://ftp.maps.canada.ca/pub/nrcan_rncan/Mining-industry_Industrie-miniere/"
       "900A_and_top_100/SHP/900A_75th_2025_shape.zip")
BASENAME = "900A_75th_shape/900A_75th_ProducingMines"


def load() -> pd.DataFrame:
    recs = read_shp_records(ensure_cached(URL, "nrcan-900a.zip"), BASENAME, encoding="utf-8")
    raw = pd.DataFrame(recs)
    return pd.DataFrame({
        "magnitude": 2.3,  # current national producing mines
        "name": raw["NAME_E"],
        "lat": raw["LATITUDE"],
        "lng": raw["LONGITUDE"],
        "commodities": [[p] for p in raw["PRD_DESC_E"]],
        "status_raw": "Producer",  # the 900A "Producing Mines" layer
        "depositType": raw["FACILITY_E"],
        "source": ID,
        "country": "Canada",
        "source_id": None,
    })
