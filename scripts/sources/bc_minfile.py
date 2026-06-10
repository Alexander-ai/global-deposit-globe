"""British Columbia MINFILE — provincial mineral inventory (Open Government Licence).

Kept to developed deposits (producers, past producers, developed prospects, prospects);
the ~10k minor "showings"/anomalies are dropped so BC doesn't swamp the global balance.
"""

from __future__ import annotations

import csv

import pandas as pd

from .base import ensure_cached

ID = "bc_minfile"
LABEL = "BC MINFILE (British Columbia)"
LICENSE = "Open Government Licence – British Columbia"
VINTAGE = "current"
PRIORITY = 65  # authoritative for BC; preferred over MRDS there
STATUS_KEEP = None

URL = ("https://catalogue.data.gov.bc.ca/dataset/92206d94-bc64-4111-a295-cd14eb5a501c/"
       "resource/120d5ee6-bff5-4cbe-b106-e419c790c395/download/minfile_mineral.csv")
KEEP_STATUS = {"PROD", "PAPR", "DEPR", "PROS"}  # drop SHOW / ANOM / ****


def load() -> pd.DataFrame:
    path = ensure_cached(URL, "bc-minfile.csv")
    rows = []
    with open(path, encoding="latin-1", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("STATUS_CODE", "").strip() not in KEEP_STATUS:
                continue
            commods = [
                r.get(f"COMMODITY_DESCRIPTION{i}", "").strip()
                for i in range(1, 9)
            ]
            rows.append({
                "magnitude": {"PROD": 2.1, "PAPR": 1.6, "DEPR": 1.5}.get(
                    r.get("STATUS_CODE", "").strip(), 1.3),
                "name": (r.get("MINFILE_NAME1") or "").strip(),
                "lat": r.get("DECIMAL_LATITUDE"),
                "lng": r.get("DECIMAL_LONGITUDE"),
                "commodities": [c for c in commods if c],
                "status_raw": (r.get("STATUS_DESCRIPTION") or "").strip(),
                "depositType": (r.get("DEPOSIT_TYPE_DESCRIPTION1") or "").strip() or None,
                "source": ID,
                "country": "Canada",
                "source_id": r.get("MINERAL_FILE_NUMBER"),
            })
    return pd.DataFrame(rows)
