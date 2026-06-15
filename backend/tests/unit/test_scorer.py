"""
Unit tests for the tender scoring engine.
"""
from datetime import datetime, timedelta
from app.scoring.scorer import TenderScorer, score_tender


def _strong_company():
    return {
        "annual_turnover": 200,  # lakhs
        "net_worth": 100,
        "team_size": 50,
        "sectors": ["construction", "civil"],
        "operating_states": ["Maharashtra"],
        "certifications": {"ISO_9001": True, "ISO_14001": True},
        "registrations": {"GST": "27ABCDE1234F1Z5", "PAN": "ABCDE1234F"},
        "past_projects": [
            {"sectors": ["construction"], "contract_value": 5000000},
            {"sectors": ["construction"], "contract_value": 8000000},
        ],
        "bid_success_rate": 0.6,
    }


def _matching_tender():
    return {
        "tender_value": 5000000,
        "bid_deadline": (datetime.utcnow() + timedelta(days=20)).isoformat(),
        "sectors": ["construction"],
        "location": "Maharashtra",
        "eligibility_criteria": [
            {"type": "turnover", "amount": 50},
            {"type": "certification", "name": "ISO_9001"},
            {"type": "registration", "name": "GST"},
            {"type": "experience", "sector": "construction", "min_projects": 1},
        ],
        "required_documents": [],
        "penalty_clauses": [],
    }


def test_strong_match_high_win_probability():
    result = score_tender(_matching_tender(), _strong_company())
    assert result["win_probability"] > 0.7
    assert result["eligibility_score"] == 1.0
    assert result["recommendation"] in ("high_priority", "medium_priority")


def test_ineligible_company_capped():
    company = _strong_company()
    company["annual_turnover"] = 10  # below required 50
    company["certifications"] = {}  # missing ISO
    company["registrations"] = {}  # missing GST
    result = score_tender(_matching_tender(), company)
    # Hard gate caps win probability when not legally eligible
    assert result["win_probability"] <= 0.35
    assert result["eligibility_score"] < 0.7


def test_tight_deadline_increases_risk():
    tender = _matching_tender()
    tender["bid_deadline"] = (datetime.utcnow() + timedelta(days=2)).isoformat()
    result = score_tender(tender, _strong_company())
    assert result["risk_level"] in ("medium", "high")


def test_severe_penalties_flagged():
    tender = _matching_tender()
    tender["penalty_clauses"] = [{"type": "penalty", "amount": 2000000}]  # 40% of value
    result = score_tender(tender, _strong_company())
    risk_factors = result["factors"]["risk"]
    assert any("penal" in f["risk"].lower() for f in risk_factors)


def test_large_tender_high_competition():
    tender = _matching_tender()
    tender["tender_value"] = 2000000000  # 200 crore
    result = score_tender(tender, _strong_company())
    assert result["competition_intensity"] in ("high", "very_high")


def test_reasoning_is_populated():
    result = score_tender(_matching_tender(), _strong_company())
    assert len(result["reasoning"]) > 0
    assert any("Recommendation" in r for r in result["reasoning"])
