"""
Lock the PorterGeo crosswalk's matching rules. The danger here is a WRONG link (sending a
reader to a different deposit), so these pin the conservative guards: name canonicalization,
the commodity guard, the country disambiguation, and the no-link defaults.
"""

import portergeo


# A small listing fragment exercising: a unique distinctive name, a stoplist/commodity-word
# alias that must NOT be indexed, an "X Complex - members" pattern, and a name shared by two
# deposits in different countries.
_HTML = """
<a href="mineinfo.php?mineid=mn204">Escondida</a></td>
<td class="results displayUpdateCountry">Chile</td>
<td class="results displayCommodities"> Cu</td>

<a href="mineinfo.php?mineid=mn170">Sudbury Complex - Frood, Creighton</a></td>
<td class="results displayUpdateCountry">Canada</td>
<td class="results displayCommodities"> Ni, Cu</td>

<a href="mineinfo.php?mineid=mn900">Eagle, Copper - X41</a></td>
<td class="results displayUpdateCountry">United States of America</td>
<td class="results displayCommodities"> Ni</td>

<a href="mineinfo.php?mineid=mn910">Phoenix</a></td>
<td class="results displayUpdateCountry">Canada</td>
<td class="results displayCommodities"> U</td>

<a href="mineinfo.php?mineid=mn911">Phoenix</a></td>
<td class="results displayUpdateCountry">Australia</td>
<td class="results displayCommodities"> Au</td>
"""

IDX = portergeo.load_index(_HTML)
P = portergeo.PAGE_URL


def test_index_parsing_and_stoplist():
    assert "escondida" in IDX
    assert "sudbury" in IDX                # "Complex"/members stripped to the core name
    assert "eagle" in IDX
    assert "copper" not in IDX             # bare commodity word never becomes a lookup key


def test_unique_distinctive_name_links_when_country_agrees_or_unknown():
    assert portergeo.link_for("Escondida", "Chile", "copper", IDX) == P + "mn204"
    # our record carried no country — a globally unique name is still safe
    assert portergeo.link_for("Escondida", None, "copper", IDX) == P + "mn204"
    # variant phrasing canonicalizes the same
    assert portergeo.link_for("Escondida open pit mine", "Chile", "copper", IDX) == P + "mn204"


def test_complex_member_pattern_recovered():
    assert portergeo.link_for("Sudbury", "Canada", "nickel", IDX) == P + "mn170"


def test_commodity_guard_blocks_wrong_eagle():
    # PorterGeo's Eagle is nickel; a gold "Eagle" must not link to it.
    assert portergeo.link_for("Eagle", "United States", "gold", IDX) is None
    assert portergeo.link_for("Eagle", "United States", "nickel", IDX) == P + "mn900"


def test_country_mismatch_on_unique_name_does_not_link():
    # Unique name but our country contradicts PorterGeo's -> likely a different site.
    assert portergeo.link_for("Escondida", "Peru", "copper", IDX) is None


def test_ambiguous_name_needs_country():
    # "Phoenix" exists in two countries; commodity narrows, but test the country path too.
    assert portergeo.link_for("Phoenix", "Canada", "uranium", IDX) == P + "mn910"
    assert portergeo.link_for("Phoenix", "Australia", "gold", IDX) == P + "mn911"
    # no country + genuinely ambiguous (two ids survive the commodity filter) -> no link
    assert portergeo.link_for("Phoenix", None, "other", IDX) is None


def test_unmatched_name_is_none():
    assert portergeo.link_for("Nonexistent Ridge", "Canada", "gold", IDX) is None
    assert portergeo.link_for("", "Canada", "gold", IDX) is None


def test_common_name_gate_in_add_links():
    # A name SCATTERED across many cells (common label) must not link any record, even though
    # each matches by name+country+commodity. A co-located name (one cell) still links.
    import pandas as pd

    df = pd.DataFrame(
        {
            "name": ["Escondida"] * 4 + ["Phoenix"] * 3,
            # 4 Escondidas in 4 distinct cells = scattered -> gated out
            "lat": [-10, -20, -30, -40] + [55, 55, 55],
            "lng": [-70, -68, -66, -64] + [-100, -100, -100],
            "country": ["Chile"] * 4 + ["Canada"] * 3,
            "commodity": ["copper"] * 4 + ["uranium"] * 3,
        }
    )
    out, n = portergeo.add_links(df, byname=IDX)
    got = [None if pd.isna(u) else u for u in out["porterUrl"]]
    assert got == [None, None, None, None] + [portergeo.PAGE_URL + "mn910"] * 3
    assert n == 3

