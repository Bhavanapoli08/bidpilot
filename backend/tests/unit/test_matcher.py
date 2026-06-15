"""
Unit tests for the monitoring quick-match scorer and source filters.
"""
from app.monitoring.matcher import quick_match, passes_source_filters


def _company():
    return {
        "sectors": ["IT Services", "Software"],
        "operating_states": ["Maharashtra"],
        "annual_turnover": 20_000_000,
    }


def test_strong_match_scores_high():
    item = {
        "title": "AI software development for citizen portal",
        "description": "Build an AI platform",
        "sector": "IT Services",
        "location": "Maharashtra",
        "tender_value": 7_500_000,
    }
    score, reasons = quick_match(item, _company())
    assert score >= 0.7
    assert any("Sector match" in r for r in reasons)


def test_off_sector_and_geo_scores_low():
    item = {
        "title": "Construction of district office complex",
        "description": "Civil works",
        "sector": "Construction",
        "location": "Tamil Nadu",
        "tender_value": 95_000_000,
    }
    score, _ = quick_match(item, _company())
    assert score < 0.5


def test_neighbouring_state_is_partial():
    item = {
        "title": "Cloud migration", "description": "",
        "sector": "IT Services", "location": "Gujarat",  # neighbour of Maharashtra
        "tender_value": 10_000_000,
    }
    score, reasons = quick_match(item, _company())
    assert any("Neighbouring" in r for r in reasons)
    assert 0.5 <= score < 1.0


def test_no_company_signals_is_neutral():
    item = {"title": "Anything", "sector": "IT Services", "tender_value": 1000}
    score, _ = quick_match(item, {})
    assert score == 0.5


def test_keyword_filter_excludes_non_matching():
    source = {"keywords": ["software", "ai"]}
    assert passes_source_filters(
        {"title": "AI software dev", "description": "", "sector": "IT"}, source
    )
    assert not passes_source_filters(
        {"title": "Road construction", "description": "", "sector": "Civil"}, source
    )


def test_value_filter_bounds():
    source = {"min_value": 1_000_000, "max_value": 10_000_000}
    assert passes_source_filters({"title": "x", "tender_value": 5_000_000}, source)
    assert not passes_source_filters({"title": "x", "tender_value": 500_000}, source)
    assert not passes_source_filters({"title": "x", "tender_value": 50_000_000}, source)
