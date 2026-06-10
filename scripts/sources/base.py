"""Shared download/caching + readers for source loaders."""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
from schema import CACHE  # noqa: E402

_UA = "Mozilla/5.0 (deposit-globe data pipeline; contact: project maintainer)"


def ensure_cached(url: str, filename: str) -> Path:
    """Download `url` to scripts/.cache/<filename> once; return the cached path."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / filename
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  downloading {filename} ...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def mag_from_tonnage(series) -> list[float]:
    """Magnitude (1.3–3.0) from an ore-tonnage column (million tonnes), log-scaled."""
    import math
    t = pd.to_numeric(series, errors="coerce").fillna(0)
    return [min(3.0, max(1.3, 1.3 + 0.5 * math.log10(1 + v))) for v in t]


def fetch_arcgis_geojson(query_base: str, out_name: str, page: int = 2000) -> Path:
    """Page through an ArcGIS FeatureServer /query endpoint and cache one combined GeoJSON."""
    import json as _json
    dest = CACHE / out_name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    CACHE.mkdir(parents=True, exist_ok=True)
    feats, off = [], 0
    while True:
        u = (f"{query_base}?where=1%3D1&outFields=*&returnGeometry=true&f=geojson"
             f"&resultOffset={off}&resultRecordCount={page}")
        req = urllib.request.Request(u, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = _json.loads(r.read())
        fs = d.get("features", [])
        feats += fs
        if len(fs) < page:
            break
        off += page
    dest.write_text(_json.dumps({"type": "FeatureCollection", "features": feats}),
                    encoding="utf-8")
    return dest


def read_csv_zip(zip_path: Path, member: str, encoding: str = "latin-1",
                 usecols=None) -> pd.DataFrame:
    """Read one CSV member out of a zip as all-string columns."""
    with zipfile.ZipFile(zip_path) as z, z.open(member) as fh:
        text = io.TextIOWrapper(fh, encoding=encoding)
        return pd.read_csv(text, usecols=usecols, dtype=str, low_memory=False)


def read_shp_records(zip_path: Path, basename: str, encoding: str = "latin-1") -> list[dict]:
    """Read a shapefile's DBF attribute records (no GDAL — pure-python pyshp)."""
    import shapefile  # pyshp
    with zipfile.ZipFile(zip_path) as z:
        shp = io.BytesIO(z.read(basename + ".shp"))
        dbf = io.BytesIO(z.read(basename + ".dbf"))
        shx = io.BytesIO(z.read(basename + ".shx"))
    r = shapefile.Reader(shp=shp, dbf=dbf, shx=shx, encoding=encoding)
    flds = [f[0] for f in r.fields[1:]]
    return [dict(zip(flds, rec)) for rec in r.records()]


def zip_member_named(zip_path: Path, suffix: str) -> str:
    """Find the first member in a zip whose name ends with `suffix` (e.g. '.csv')."""
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            if n.lower().endswith(suffix.lower()):
                return n
    raise FileNotFoundError(f"no *{suffix} member in {zip_path.name}")
