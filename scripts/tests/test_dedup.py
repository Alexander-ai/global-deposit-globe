"""
Lock the cross-source de-duplication rules. These regression-test the behaviour the project
owner asked for and the over-merge bugs that were fixed along the way:

  * a distinctively-named site merges its variants across sources within 100 km
    (Musselwhite), absorbing corroboration count + max magnitude;
  * a COMMON name ("Gold King" = dozens of distinct mines) does NOT merge over distance,
    even cross-source — the spatial-dispersion guard keeps them split;
  * the commodity guard never merges two different-bucket sites with no shared raw token;
  * generic/unnamed labels are preserved (no chain-sweep collapsing distinct occurrences);
  * a localized name's variants merge within a source ("Malmberget" / "Malmberget Mine").
"""

import dedup
import normalize
import pandas as pd
import pytest

_DEFAULTS = dict(
    commodities=["Gold"], status_raw=None, depositType=None,
    country=None, source_id=None, magnitude=None,
)


def rec(name, lat, lng, source, commodities=None, **over):
    """One pre-classification row in the unified shape merge() consumes."""
    r = dict(_DEFAULTS)
    r.update(name=name, lat=lat, lng=lng, source=source)
    if commodities is not None:
        r["commodities"] = commodities
    r.update(over)
    r["commodity"] = normalize.classify(r["commodities"])
    return r


def frame(records):
    return pd.DataFrame(records)


def merge_names(records):
    out, _ = dedup.merge(frame(records))
    return out


def test_distinctive_name_merges_across_sources_within_100km():
    # Two databases geocode the same mine ~33 km apart, same name -> one site.
    recs = [
        rec("Musselwhite", 52.616, -90.417, "mrds", magnitude=1.5),
        rec("Musselwhite", 52.916, -90.417, "nrcan", magnitude=2.4),
    ]
    out, stats = dedup.merge(frame(recs))
    assert len(out) == 1
    survivor = out.to_dict("records")[0]
    assert survivor["corrob"] == 2                 # both databases corroborate
    assert survivor["magnitude"] == 2.4            # site is as big as its biggest estimate
    assert stats["removed"] == 1


def test_core_name_variant_merges():
    # "Musselwhite" vs "Musselwhite Gold Mine" — token-subset containment = same name.
    recs = [
        rec("Musselwhite", 52.616, -90.417, "mrds"),
        rec("Musselwhite Gold Mine", 52.70, -90.45, "minfac"),
    ]
    assert len(merge_names(recs)) == 1


def test_common_name_stays_split_even_when_near():
    # "Gold King" names dozens of distinct mines. Spread across >3 one-degree cells it reads
    # as a COMMON label, so two of them 33 km apart cross-source must NOT merge.
    recs = [
        rec("Gold King", 40.0, -110.0, "mrds"),
        rec("Gold King", 40.3, -110.0, "bc_minfile"),  # ~33 km from the first
        rec("Gold King", 42.0, -110.0, "mrds"),
        rec("Gold King", 44.0, -110.0, "mrds"),
        rec("Gold King", 46.0, -110.0, "mrds"),
    ]
    assert len(merge_names(recs)) == 5  # nothing merges


def test_commodity_guard_rejects_unrelated_buckets():
    # The fuzzy pass must never merge two nearby points whose commodities classify to
    # different non-"other" buckets with no shared raw token (gold vs copper) — that would
    # collapse two genuinely different deposits.
    a = rec("Ridge", 30.0, 30.0, "mrds", commodities=["Gold"])
    b = rec("Ridge", 30.001, 30.0, "porcu", commodities=["Copper"])
    ok, _ = dedup._can_merge(a, b)
    assert ok is False
    # But a shared raw token (the same site listed under "Copper, Gold" and "Copper") is fine.
    c = rec("Ridge", 30.0, 30.0, "mrds", commodities=["Copper, Gold"])
    d = rec("Ridge", 30.001, 30.0, "porcu", commodities=["Copper"])
    ok2, _ = dedup._can_merge(c, d)
    assert ok2 is True


def test_same_named_site_unions_per_commodity_rows():
    # Intended counterpart to the guard: a single facility listed once per commodity by one
    # source (Mufulira copper + Mufulira cobalt at one spot) collapses to one site, and the
    # secondary commodity survives for the card's "Also present" line.
    recs = [
        rec("Mufulira", -12.55, 28.24, "minfac", commodities=["Copper"]),
        rec("Mufulira", -12.551, 28.24, "minfac", commodities=["Cobalt"]),
    ]
    out = merge_names(recs).to_dict("records")
    assert len(out) == 1
    union = {c.upper() for c in out[0]["commodities"]}
    assert {"COPPER", "COBALT"} <= union


def test_unnamed_occurrences_are_preserved():
    # Generic "Unnamed Iron Deposit" scattered across many cells reads as non-localized, so a
    # pair 1.1 km apart in ONE source stays split (distinct occurrences, not a duplicate).
    spread = [rec("Unnamed Iron Deposit", lat, -110.0, "mrds", commodities=["Iron"])
              for lat in (41.0, 42.0, 43.0, 44.0, 45.0)]
    pair = [
        rec("Unnamed Iron Deposit", 40.00, -110.0, "mrds", commodities=["Iron"]),
        rec("Unnamed Iron Deposit", 40.01, -110.0, "mrds", commodities=["Iron"]),  # ~1.1 km
    ]
    out = merge_names(spread + pair)
    # The 1.1 km pair must not collapse; total stays at the full input count.
    assert len(out) == len(spread) + len(pair)


def test_localized_variant_merges_within_one_source():
    # A truly-named site recorded twice in one database under name variants -> one site.
    recs = [
        rec("Malmberget", 67.170, 20.660, "mrds", commodities=["Iron"]),
        rec("Malmberget Mine", 67.178, 20.665, "mrds", commodities=["Iron"]),  # ~1 km
    ]
    assert len(merge_names(recs)) == 1


def test_survivor_unions_commodities_and_keeps_country():
    recs = [
        rec("Olympic Dam", -30.44, 136.88, "minfac",
            commodities=["Copper"], country="Australia", magnitude=3.0),
        rec("Olympic Dam", -30.45, 136.89, "pp1802",
            commodities=["Uranium", "Gold"], country=None, magnitude=2.0),
    ]
    out = merge_names(recs).to_dict("records")
    assert len(out) == 1
    s = out[0]
    assert s["country"] == "Australia"
    # Co-commodities from the merged record feed the card's "Also present" line.
    assert "Uranium" in s["commodities"] or "URANIUM" in [c.upper() for c in s["commodities"]]


def test_empty_frame_is_safe():
    out, stats = dedup.merge(frame([]))
    assert len(out) == 0
    assert stats["removed"] == 0
