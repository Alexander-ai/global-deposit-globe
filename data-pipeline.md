# Data pipeline — MRDS → deposits.json

The single fiddly part of this project. The goal: turn the raw USGS MRDS download into a
small, clean `public/deposits.json` where every record has one normalized commodity that
maps to a color bucket. Get the normalization right and the globe is honest; get it wrong
and it's subtly miscolored everywhere.

Write this as `scripts/prepare-data.py` (pandas) or `scripts/prepare-data.ts`. Python is
easier for the messy text wrangling — recommended.

## Step 0 — inspect the real file first (do not skip)

MRDS ships in several formats (a flat CSV, a relational set of tables, per-state files), and
**column names differ between them.** Before writing mapping logic, load the file and print
the columns and a few sample rows. Identify, by inspection:

- the **latitude** and **longitude** columns (often `latitude`/`longitude` or `lat`/`lon`),
- the **site name** column (often `site_name` or `name`),
- the **commodity** column(s) — MRDS usually has `commod1`, `commod2`, `commod3` holding the
  primary/secondary/tertiary commodities, each possibly a delimited list of names,
- optionally a **development status** column (`dev_stat`) and **deposit type**.

Adapt the column names below to what the actual download uses. Don't trust these names blindly.

## Step 1 — clean rows

- Coerce lat/lng to numeric; drop rows where either is missing or non-numeric.
- Drop rows at exactly `(0, 0)` — that's a null-island artifact, not a real deposit.
- Drop rows with lat outside [-90, 90] or lng outside [-180, 180].
- MRDS has known duplicates. Deduplicate on (rounded lat, rounded lng, site_name); keep first.

## Step 2 — parse commodities

Each commodity field may contain several commodities as a delimited string, e.g.
`"Gold; Silver; Copper"` or `"GOLD, LEAD, ZINC"`. For each record, build an ordered list of
commodity tokens by:

1. taking `commod1`, then `commod2`, then `commod3` (in that order — primary first),
2. splitting each on any of `; , /` and the word "and",
3. trimming whitespace and upper-casing each token for matching.

## Step 3 — normalize to a bucket

Match each token against this map (match on the upper-cased token; use substring/contains for
the multi-word REE and lithium-mineral cases). Assign the record to the bucket of the **first
token, in primary→secondary→tertiary order, that matches a named bucket.** If no token matches
any named bucket, the record is `"other"`.

```python
COMMODITY_MAP = {
    "gold":    ["GOLD", "AU"],
    "copper":  ["COPPER", "CU"],
    "lithium": ["LITHIUM", "LI", "SPODUMENE", "PETALITE", "LEPIDOLITE"],
    "cobalt":  ["COBALT", "CO"],
    "nickel":  ["NICKEL", "NI"],
    "ree":     ["RARE EARTH", "RARE-EARTH", "REE", "CERIUM", "LANTHANUM",
                "NEODYMIUM", "PRASEODYMIUM", "YTTRIUM", "SAMARIUM", "EUROPIUM",
                "GADOLINIUM", "DYSPROSIUM", "TERBIUM", "MONAZITE", "BASTNASITE",
                "BASTNAESITE"],
    "zinc":    ["ZINC", "ZN"],
    "uranium": ["URANIUM", "U3O8", "URANINITE", "PITCHBLENDE"],
    "silver":  ["SILVER", "AG"],
}
```

Matching rules and gotchas:

- For the **multi-word and mineral-name** entries (REE list, lithium minerals), test with
  `token contains keyword`. For the **short element symbols** (`AU`, `CU`, `CO`, `NI`, `LI`,
  `ZN`, `AG`, `U`), require an **exact token match**, never substring — otherwise `"CO"` would
  hit "COPPER"/"COBALT"/"COLD" and `"U"` would hit everything. Symbols are a fallback only;
  MRDS mostly uses full names, so prefer the full-name matches.
- `"U"` is risky as a bare symbol — only accept exact token `"U"` or `"U3O8"`. Prefer `URANIUM`.
- A `"Lead; Zinc; Silver"` deposit (primary = lead, unmatched) falls through to zinc — correct.
- A pure `"Iron"` or `"Molybdenum"` deposit becomes `"other"`.

## Step 4 — filter for v1

Keep the point count in the low thousands so react-globe.gl stays at 60fps:

- **Default v1:** keep only the nine named buckets; **drop `"other"`** so the globe is a clean
  critical-minerals-plus-major-metals view. (Make this a flag so you can flip it on later.)
- Optionally, if even that is too many points, further restrict by development status (e.g.,
  keep producers and past producers, drop minor occurrences) — but state any such filter in
  the UI so the picture stays honest.

## Step 5 — output

Write `public/deposits.json` as a compact array, coordinates rounded to 4 decimals:

```json
[
  { "name": "Example Mine", "lat": 48.1234, "lng": -79.5678, "commodity": "gold", "depositType": "vein" }
]
```

- `commodity` is the bucket key (`gold`, `copper`, `lithium`, `cobalt`, `nickel`, `ree`,
  `zinc`, `uranium`, `silver`, `other`) — matches the keys in `src/data/commodities.ts`.
- `depositType` optional; omit if absent.
- Target file size: keep it under ~1–2 MB. If larger, your v1 filter isn't tight enough.

## Step 6 — sanity check (print these before declaring done)

- Total records in vs. records out, and how many were dropped and why.
- A count per commodity bucket. If one bucket is suspiciously huge or empty, the mapping or
  column choice is wrong — investigate before shipping.
- Spot-check five known deposits against reality (e.g., a famous copper mine should be `copper`).
