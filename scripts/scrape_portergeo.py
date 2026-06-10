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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import portergeo  # noqa: E402
from schema import CACHE, ROOT  # noqa: E402

_UA = "Mozilla/5.0 (deposit-globe data pipeline; +https://github.com/Alexander-ai/global-deposit-globe)"
_PAIR = re.compile(r"(-?\d{1,2}\.\d{3,}),\s*(-?\d{1,3}\.\d{3,})")
_PAGES = CACHE / "portergeo_pages"
OUT = ROOT / "scripts" / "portergeo_index.json"


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


def _coords(page: str, cap: int = 4) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for la, lo in _PAIR.findall(page):
        la, lo = round(float(la), 5), round(float(lo), 5)
        if -90 <= la <= 90 and -180 <= lo <= 180 and (la, lo) not in out and (la or lo):
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

    done = [0]
    fail = [0]

    def grab(mid):
        try:
            _fetch(mid)
        except Exception:  # noqa: BLE001
            fail[0] += 1
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"    {done[0]}/{len(ids)}  (failed {fail[0]})", flush=True)

    # Gentle: 3 workers so PorterGeo doesn't rate-limit/block the run.
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(grab, ids))
    print(f"  fetched; {fail[0]} pages failed after retries", flush=True)

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
