"""
Lock the PorterGeo coordinate matcher. The danger is a WRONG link (a reader sent to a
different deposit), so these pin the proximity bands, the commodity guard, and the
name-agreement fallback against a small synthetic coordinate index.
"""

import portergeo

P = portergeo.PAGE_URL

# A tiny coordinate index: Escondida (Cu, Chile), Olympic Dam (Cu/U, Australia),
# Talnakh Complex (Ni/Cu, Russia — the Norilsk orebody under a different name).
INDEX = [
    {"id": "mn204", "name": "Escondida", "country": "Chile",
     "lat": -24.2714, "lng": -69.0703, "b": ["copper"]},
    {"id": "mn001", "name": "Olympic Dam", "country": "Australia",
     "lat": -30.4400, "lng": 136.8800, "b": ["copper", "uranium"]},
    {"id": "mn175", "name": "Talnakh Complex", "country": "Russia",
     "lat": 69.4900, "lng": 88.3900, "b": ["nickel", "copper"]},
]
GRID = portergeo.build_grid(INDEX)


def link(lat, lng, commodity, name):
    return portergeo.best_link(lat, lng, commodity, portergeo._canon(name), GRID)


def test_proximity_links_when_right_on_top():
    # A copper deposit at Escondida's coordinates links, name irrelevant.
    assert link(-24.2714, -69.0703, "copper", "whatever") == P + "mn204"


def test_commodity_guard_blocks_wrong_commodity():
    # A gold deposit at the same spot must NOT link to the copper Escondida.
    assert link(-24.2714, -69.0703, "gold", "Escondida") is None


def test_proximity_catches_a_name_variant():
    # Our "Norilsk" sitting on the Talnakh orebody links despite the different name.
    assert link(69.4900, 88.3900, "nickel", "Norilsk") == P + "mn175"


def test_name_plus_region_links_within_30km():
    # ~17 km from Olympic Dam, name agrees, compatible commodity -> link.
    assert link(-30.5900, 136.8800, "copper", "Olympic Dam") == P + "mn001"


def test_name_far_away_does_not_link():
    # Right name, but ~220 km away -> different site -> no link.
    assert link(-22.2714, -69.0703, "copper", "Escondida") is None


def test_near_but_name_disagrees_and_beyond_prox():
    # ~17 km from Olympic Dam but the name doesn't agree and it's past R_PROX -> no link.
    assert link(-30.5900, 136.8800, "copper", "Random Ridge") is None


def test_other_commodity_is_permissive():
    # Our commodity 'other' can't be guarded, so proximity alone links.
    assert link(-24.2714, -69.0703, "other", "x") == P + "mn204"


def test_add_links_integration():
    import pandas as pd

    df = pd.DataFrame(
        {
            "name": ["Escondida", "Faraway", "Olympic Dam"],
            "lat": [-24.2714, 10.0, -30.5900],
            "lng": [-69.0703, 10.0, 136.8800],
            "country": ["Chile", "Nowhere", "Australia"],
            "commodity": ["copper", "gold", "copper"],
        }
    )
    out, n = portergeo.add_links(df, index=INDEX, byname={})
    got = [None if pd.isna(u) else u for u in out["porterUrl"]]
    assert got == [P + "mn204", None, P + "mn001"]
    assert n == 2


def test_name_fallback_when_no_coordinate():
    # With an EMPTY coordinate index, the hybrid falls back to name matching from the listing.
    import pandas as pd

    byname = {"escondida": {("chile", frozenset({"copper"}), "mn204")}}
    df = pd.DataFrame(
        {"name": ["Escondida"], "lat": [-24.27], "lng": [-69.07],
         "country": ["Chile"], "commodity": ["copper"]}
    )
    out, n = portergeo.add_links(df, index=[], byname=byname)
    assert list(out["porterUrl"]) == [P + "mn204"]
    assert n == 1
