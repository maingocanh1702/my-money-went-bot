"""Tests for interactive cashback learning flow (MCC exclusion + keyword extraction
+ self-learning priority matching)."""
import sheets as sh


# ── Keyword extraction (pure, no fixture needed) ──────────────


def test_extract_shopee_with_code():
    assert sh.extract_keyword_from_description("SHOPEE 2024123456 VN") == "shopee"


def test_extract_grab_star():
    assert sh.extract_keyword_from_description("GRAB*SERVICE 123") == "grab"


def test_extract_vinfast():
    assert sh.extract_keyword_from_description("VINFAST SERVICE CTY ABC") == "vinfast"


def test_extract_bachhoaxanh():
    assert sh.extract_keyword_from_description("BACHHOAXANH CN TAN PHU") == "bachhoaxanh"


def test_extract_traveloka():
    assert sh.extract_keyword_from_description("TRAVELOKA.COM VN 123456") == "traveloka"


def test_extract_lazada():
    assert sh.extract_keyword_from_description("LAZADA-VN/ORDER#999") == "lazada"


def test_extract_empty():
    assert sh.extract_keyword_from_description("") == ""


def test_extract_all_numeric_fallback():
    result = sh.extract_keyword_from_description("TK 01234")
    assert result  # falls back to first token


# ── Multi-word specific keyword extraction ─────────────────────


def test_extract_specific_shopee_food():
    result = sh.extract_keyword_from_description("SHOPEE FOOD ORDER 456", specific=True)
    assert result == "shopee food"


def test_extract_specific_grab_food():
    result = sh.extract_keyword_from_description("GRAB FOOD MERCHANT ABC", specific=True)
    assert result == "grab food"


def test_extract_specific_single_word():
    """When only 1 alpha token, specific=True still returns it."""
    result = sh.extract_keyword_from_description("SHOPEE 2024123456 VN", specific=True)
    assert result == "shopee"  # only 1 alpha token ≥3 chars


def test_extract_specific_default_false():
    """Default (specific=False) returns single word only."""
    result = sh.extract_keyword_from_description("SHOPEE FOOD ORDER 456")
    assert result == "shopee"  # not "shopee food"


# ── MCC exclusion (needs fake spreadsheet) ─────────────────────


def test_exclusion_add_and_check(fake_ss):
    sh.add_mcc_exclusion("netflix")
    assert sh.is_mcc_excluded("NETFLIX VN 123456")
    assert sh.is_mcc_excluded("netflix subscription")


def test_exclusion_non_excluded_returns_false(fake_ss):
    assert not sh.is_mcc_excluded("SHOPEE 123456")


def test_exclusion_idempotent(fake_ss):
    assert sh.add_mcc_exclusion("spotify") is True
    assert sh.add_mcc_exclusion("spotify") is False  # duplicate


def test_exclusion_cache_invalidation(fake_ss):
    sh.add_mcc_exclusion("hulu")
    assert sh.is_mcc_excluded("HULU SUBSCRIPTION")
    sh.invalidate_cashback_caches()
    # After cache bust, re-read from sheet — still works
    assert sh.is_mcc_excluded("HULU SUBSCRIPTION")


def test_exclusion_empty_description(fake_ss):
    assert not sh.is_mcc_excluded("")


def test_exclusion_normalized_matching(fake_ss):
    sh.add_mcc_exclusion("ĐIỆN THOẠI")
    assert sh.is_mcc_excluded("dien thoai ABC")


# ── Priority matching (resolve_mcc_or_exclusion) ──────────────


def test_resolve_mcc_wins_when_no_exclusion(fake_ss, fake_ws):
    """MCC match wins when there's no exclusion for this pattern."""
    ws = fake_ws("MCC Map", sh.MCC_MAP_HEADER)
    ws.update("A2:G2", [["shopee", "5262", "Sàn TMĐT", "", "0", "TRUE", ""]])
    sh.invalidate_cashback_caches()

    result = sh.resolve_mcc_or_exclusion("SHOPEE ELECTRONICS 123")
    assert result is not None
    assert result["mcc_code"] == "5262"


def test_resolve_exclusion_wins_when_longer(fake_ss, fake_ws):
    """Exclusion pattern wins when it's longer (more specific) than MCC."""
    ws = fake_ws("MCC Map", sh.MCC_MAP_HEADER)
    ws.update("A2:G2", [["shopee", "5262", "Sàn TMĐT", "", "0", "TRUE", ""]])
    sh.invalidate_cashback_caches()

    # Add longer exclusion
    sh.add_mcc_exclusion("shopee food")

    # "SHOPEE FOOD ORDER" → exclusion "shopee food" (11) > MCC "shopee" (6)
    result = sh.resolve_mcc_or_exclusion("SHOPEE FOOD ORDER 456")
    assert result is None  # exclusion wins

    # "SHOPEE ELECTRONICS" → MCC "shopee" (6), no exclusion match → MCC wins
    result2 = sh.resolve_mcc_or_exclusion("SHOPEE ELECTRONICS 123")
    assert result2 is not None
    assert result2["mcc_code"] == "5262"


def test_resolve_no_match(fake_ss, fake_ws):
    """No MCC and no exclusion → returns None."""
    fake_ws("MCC Map", sh.MCC_MAP_HEADER)
    sh.invalidate_cashback_caches()

    result = sh.resolve_mcc_or_exclusion("RANDOM MERCHANT 123")
    assert result is None


def test_resolve_equal_length_exclusion_wins(fake_ss, fake_ws):
    """When exclusion pattern is same length as MCC, exclusion wins (>=)."""
    ws = fake_ws("MCC Map", sh.MCC_MAP_HEADER)
    ws.update("A2:G2", [["grab", "4121", "Di chuyển", "", "0", "TRUE", ""]])
    sh.invalidate_cashback_caches()

    sh.add_mcc_exclusion("grab")

    result = sh.resolve_mcc_or_exclusion("GRAB SERVICE 123")
    assert result is None  # exclusion wins (same length = exclusion priority)
