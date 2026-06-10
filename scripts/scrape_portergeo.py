"""
One-off / occasional maintenance scrape: fetch each PorterGeo deposit page for its
coordinates and write a committed `scripts/portergeo_index.json` (mineid, name, country,
lat, lng, commodity buckets). The build pipeline reads that committed index OFFLINE — it
never scrapes — so coordinate-based linking is deterministic and CI stays network-light.

Run manually when refreshing PorterGeo data:  python scripts/scrape_portergeo.py
Pages are cached under scripts/.cache/portergeo_pages/ so re-runs resume cheaply.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import portergeo  # noqa: E402
from schema import CACHE, ROOT  # noqa: E402

_UA = "Mozilla/5.0 (deposit-globe data pipeline; +https://github.com/Alexander-ai/global-deposit-globe)"
_PAIR = re.compile(r"(-?\d{1,2}\.\d{3,}),\s*(-?\d{1,3}\.\d{3,})")
# DMS fallback: "6&deg; 58' 48&quot;S, 78&deg; 30' 44&quot;W" (seconds optional).
_DEG = r"(?:&deg;|°)"
_DMS = re.compile(
    rf"(\d{{1,3}})\s*{_DEG}\s*(\d{{1,2}})\s*['’]\s*([\d.]+)?\s*(?:[\"”]|&quot;)?\s*([NSEW])"
    rf"\s*,\s*"
    rf"(\d{{1,3}})\s*{_DEG}\s*(\d{{1,2}})\s*['’]\s*([\d.]+)?\s*(?:[\"”]|&quot;)?\s*([NSEW])",
    re.I,
)
_PAGES = CACHE / "portergeo_pages"
OUT = ROOT / "scripts" / "portergeo_index.json"


def _dms(d, m, s, hemi) -> float:
    val = int(d) + int(m) / 60 + (float(s) if s else 0) / 3600
    return round(-val if hemi.upper() in ("S", "W") else val, 5)


def _fetch(mineid: str) -> Path:
    dest = _PAGES / f"{mineid}.html"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = portergeo.PAGE_URL + mineid
    last = None
    for attempt in range(3):  # short timeout + retry so a hung socket fails fast, not stalls
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
            if data:
                dest.write_bytes(data)
                return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last or RuntimeError("empty")


def _valid(la, lo, out) -> bool:
    return -90 <= la <= 90 and -180 <= lo <= 180 and (la, lo) not in out and (la or lo)


def _coords(page: str, cap: int = 4) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for la, lo in _PAIR.findall(page):  # decimal degrees (most precise) first
        la, lo = round(float(la), 5), round(float(lo), 5)
        if _valid(la, lo, out):
            out.append((la, lo))
        if len(out) >= cap:
            break
    if out:
        return out
    for m in _DMS.finditer(page):  # fall back to degrees-minutes-seconds
        la = _dms(m.group(1), m.group(2), m.group(3), m.group(4))
        lo = _dms(m.group(5), m.group(6), m.group(7), m.group(8))
        if _valid(la, lo, out):
            out.append((la, lo))
        if len(out) >= cap:
            break
    return out


def main() -> None:
    _PAGES.mkdir(parents=True, exist_ok=True)
    html = portergeo.ensure_cached(portergeo.LISTING_URL, "portergeo_listing.html").read_text(
        encoding="utf-8", errors="replace"
    )
    meta = {}  # mineid -> (name, country, commodities_html)
    for mineid, name_html, country, comm in portergeo._ROW.findall(html):
        name = re.sub(r"\s+", " ", re.sub(r"&[a-z]+;", " ", name_html)).strip()
        meta[mineid] = (name, country.strip(), comm)
    ids = sorted(meta)
    print(f"  fetching {len(ids)} PorterGeo pages (cached resume) ...", flush=True)

    done = fail = fetched = 0
    DELAY = 0.375  # seconds between real fetches (~2.7 req/s) — 4× faster, still well-behaved

    # Sequential, spaced. Cached pages are skipped with NO delay so resume is fast.
    for mid in ids:
        dest = _PAGES / f"{mid}.html"
        done += 1
        if dest.exists() and dest.stat().st_size > 0:
            continue
        try:
            _fetch(mid)
            fetched += 1
        except Exception:  # noqa: BLE001
            fail += 1
        time.sleep(DELAY)
        if fetched and fetched % 50 == 0:
            print(f"    {done}/{len(ids)} seen, {fetched} fetched, {fail} failed", flush=True)
    print(f"  done: {fetched} newly fetched, {fail} failed after retries", flush=True)

    rows = []
    for mid in ids:
        page = (_PAGES / f"{mid}.html")
        if not page.exists():
            continue
        name, country, comm = meta[mid]
        buckets = sorted(portergeo._buckets(comm))
        for la, lo in _coords(page.read_text(encoding="utf-8", errors="replace")):
            rows.append({"id": mid, "name": name, "country": country,
                         "lat": la, "lng": lo, "b": buckets})
    OUT.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    located = len({r["id"] for r in rows})
    print(f"  wrote {len(rows)} coord rows for {located}/{len(ids)} deposits -> {OUT.name}")


if __name__ == "__main__":
    main()
