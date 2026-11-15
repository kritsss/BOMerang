from engine.normalize import conversion_factor, extract_dims, normalize_text, synonym_key, dims_equal
from engine.rules import STARTER_SYNONYMS

K = synonym_key(STARTER_SYNONYMS)


def test_synonyms_multilingual():
    assert "shaft" in normalize_text("Welle", K)
    assert "stainless" in normalize_text("Edelstahl", K)
    assert normalize_text("1.4301", K) == normalize_text("V2A", K) == "stainless 304"
    assert "nbr" in normalize_text("Buna-N", K)


def test_glued_words_are_split():
    assert normalize_text("SS304", K) == "stainless stainless 304"


def test_dimensions():
    assert extract_dims("16x200") == [(16.0, 200.0)]
    assert extract_dims("m6x20") == [(6.0, 20.0)]
    assert extract_dims("0.5 x 2 in")[0] == (12.7, 50.8)
    assert dims_equal((8, 120), (120, 8))


def test_units_never_guessed():
    assert conversion_factor("C", "EA") == 100
    assert conversion_factor("M", "EA") == 1000           # per thousand for count units
    assert conversion_factor("m", "mm") == 1000           # metre for length
    assert conversion_factor("DZ", "EA") == 12
    assert conversion_factor("BX", "EA") is None          # unknown unit: flagged, not guessed
    assert conversion_factor("PK", "EA") is None          # PK only if defined
    assert conversion_factor("PK", "EA", [{"purchase_uom": "PK", "base_uom": "EA", "factor": 10}]) == 10
    assert abs(conversion_factor("lb", "kg") - 0.45359237) < 1e-9
