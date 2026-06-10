"""
Lock the commodity classifier and status harmonizer. These are the rules that decide a
point's COLOR and which tier it lands in — a silent regression here mislabels the map, so
the mapping from messy raw source strings to our fixed taxonomy is pinned here.
"""

import normalize
import pytest


class TestClassify:
    @pytest.mark.parametrize(
        "raw, bucket",
        [
            (["Gold"], "gold"),
            (["Au"], "gold"),                 # element symbol, exact-token
            (["Copper"], "copper"),
            (["Cu"], "copper"),
            (["Spodumene"], "lithium"),       # mineral name -> lithium
            (["REE"], "ree"),
            (["Rare Earth Elements"], "ree"),
            (["Monazite"], "ree"),
            (["Platinum"], "platinum"),
            (["PGE"], "platinum"),
            (["Palladium"], "platinum"),
            (["Iron"], "iron"),
            (["Magnetite"], "iron"),
            (["Fe"], "iron"),
            (["Bauxite"], "bauxite"),
            (["Aluminum"], "bauxite"),
            (["Manganese"], "manganese"),
            (["Uranium"], "uranium"),
            (["U"], "uranium"),               # single-letter symbol, exact only
            (["Tungsten"], "other_metals"),
            (["Chromite"], "other_metals"),
        ],
    )
    def test_named_buckets(self, raw, bucket):
        assert normalize.classify(raw) == bucket

    @pytest.mark.parametrize(
        "raw",
        [
            ["Coal"],
            ["Sand and Gravel"],
            ["Limestone"],
            ["Phosphate"],
            [""],
            [],
            ["Unobtanium"],
        ],
    )
    def test_unmapped_is_other(self, raw):
        assert normalize.classify(raw) == "other"

    def test_primary_is_first_matching_token_in_field_order(self):
        # Field order is primary-first; the first token that maps to a named bucket wins.
        assert normalize.classify(["Silver", "Gold"]) == "silver"
        assert normalize.classify(["Gold", "Silver"]) == "gold"
        # A leading unmapped token is skipped, not treated as "other".
        assert normalize.classify(["Sand and Gravel", "Copper"]) == "copper"

    def test_symbols_never_match_as_substring(self):
        # "CO" (cobalt) must not fire inside COPPER/COBALT words; "U" must not fire on URANINITE
        # via substring — symbols are exact-token only. Full element names still classify.
        assert normalize.bucket_for_token("COPPER") == "copper"   # not cobalt
        assert normalize.bucket_for_token("CO") == "cobalt"       # exact symbol
        assert normalize.bucket_for_token("COBALT") == "cobalt"
        assert normalize.bucket_for_token("TIN") == "other_metals"  # not platinum via "TI"/"IN"


class TestTokensFrom:
    def test_splits_on_delimiters_and_and(self):
        assert normalize.tokens_from("Gold; Copper") == ["GOLD", "COPPER"]
        assert normalize.tokens_from("Lead/Zinc") == ["LEAD", "ZINC"]
        assert normalize.tokens_from("Copper, Gold, Silver") == ["COPPER", "GOLD", "SILVER"]

    def test_and_is_word_boundaried(self):
        # "Sand and Gravel" splits on the standalone "and" but NOT the "and" inside "Sand".
        assert normalize.tokens_from("Sand and Gravel") == ["SAND", "GRAVEL"]

    def test_empty_and_non_string(self):
        assert normalize.tokens_from("") == []
        assert normalize.tokens_from(None) == []
        assert normalize.tokens_from(float("nan")) == []


class TestSecondaryNames:
    def test_excludes_primary_bucket_and_dedupes(self):
        out = normalize.secondary_names(["Gold", "Copper", "Silver"], "gold")
        assert out == ["Copper", "Silver"]

    def test_drops_bulk_industrial_tokens(self):
        out = normalize.secondary_names(["Copper", "Sand", "Gravel"], "copper")
        assert out == []

    def test_respects_limit(self):
        raw = ["Gold", "Copper", "Silver", "Lead", "Zinc", "Tin", "Nickel"]
        assert len(normalize.secondary_names(raw, "gold", limit=3)) == 3


class TestStatusFor:
    def test_mrds_explicit_mapping(self):
        assert normalize.status_for("Producer", "mrds") == "producer"
        assert normalize.status_for("Past Producer", "mrds") == "past"
        assert normalize.status_for("Prospect", "mrds") == "deposit"
        assert normalize.status_for(None, "mrds") == "deposit"

    @pytest.mark.parametrize(
        "raw, expect",
        [
            ("Operating", "producer"),
            ("Active mine", "producer"),
            ("In production", "producer"),
            ("Closed", "past"),
            ("Abandoned", "past"),
            ("Historic", "past"),
            ("Past producer", "past"),
            ("Developed prospect", "deposit"),
            ("", "deposit"),
            (None, "deposit"),
        ],
    )
    def test_generic_source_keywords(self, raw, expect):
        assert normalize.status_for(raw, "bc_minfile") == expect
