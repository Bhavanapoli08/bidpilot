"""
Lightweight opportunity matcher.

Discovered tenders carry only listing metadata (title, value, sector, location,
deadline) — not a full parsed document — so the heavy 5-factor scorer in
`app.scoring.scorer` can't run yet. This computes a fast 0-1 "should we look at
this?" fit score from metadata alone, reusing the same intuitions: sector
overlap, geographic fit, and project-value-vs-turnover sanity. It complements
the full scorer (which runs later, after a matched opportunity is imported and
its PDF processed) rather than replacing it.
"""
from datetime import datetime
from typing import Any, Dict, List, Tuple

# Reuse the scorer's notion of neighbouring states for geographic fit.
from app.scoring.scorer import STATE_NEIGHBORS


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def quick_match(discovered: Dict[str, Any], company: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Return (score in [0,1], human-readable reasons).

    `discovered` keys: title, description, sector, location, tender_value, bid_deadline.
    `company` keys: sectors, operating_states, annual_turnover.

    Scores from available signals only and renormalises, so a sparse listing
    isn't unfairly penalised for missing fields.
    """
    reasons: List[str] = []
    parts: List[Tuple[float, float]] = []  # (weight, score)

    text = f"{_norm(discovered.get('title'))} {_norm(discovered.get('description'))}"
    company_sectors = [_norm(s) for s in (company.get("sectors") or [])]

    # --- Sector fit (weight 0.45) ---
    sector = _norm(discovered.get("sector"))
    if company_sectors:
        if sector and any(cs in sector or sector in cs for cs in company_sectors):
            parts.append((0.45, 1.0))
            reasons.append(f"✓ Sector match: {discovered.get('sector')}")
        elif any(cs and cs in text for cs in company_sectors):
            parts.append((0.45, 0.8))
            reasons.append("✓ One of your sectors appears in the listing")
        else:
            parts.append((0.45, 0.0))
            reasons.append("✗ Outside your registered sectors")

    # --- Geographic fit (weight 0.25) ---
    location = discovered.get("location")
    op_states = company.get("operating_states") or []
    if location and op_states:
        loc_n = _norm(location)
        if any(_norm(st) in loc_n or loc_n in _norm(st) for st in op_states):
            parts.append((0.25, 1.0))
            reasons.append(f"✓ Within your operating states: {location}")
        else:
            neighbours = set()
            for st in op_states:
                neighbours.update(STATE_NEIGHBORS.get(st, []))
            if any(_norm(n) in loc_n for n in neighbours):
                parts.append((0.25, 0.6))
                reasons.append(f"~ Neighbouring state: {location}")
            else:
                parts.append((0.25, 0.2))
                reasons.append(f"✗ Outside your operating geography: {location}")

    # --- Value sanity vs turnover (weight 0.30) ---
    value = discovered.get("tender_value")
    turnover = company.get("annual_turnover")
    if value and turnover and turnover > 0:
        ratio = float(value) / float(turnover)
        if ratio <= 1.0:
            parts.append((0.30, 1.0))
            reasons.append("✓ Project value is comfortable vs turnover")
        elif ratio <= 3.0:
            parts.append((0.30, 0.6))
            reasons.append("~ Project value is large vs turnover")
        else:
            parts.append((0.30, 0.1))
            reasons.append("✗ Project value far exceeds turnover — likely ineligible")

    if not parts:
        # No company signal to match against — neutral, prompt profile setup.
        return 0.5, ["No company profile signals to match against — complete your profile for accurate matching"]

    total_weight = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / total_weight
    return round(score, 3), reasons


def passes_source_filters(item: Dict[str, Any], source: Dict[str, Any]) -> bool:
    """Apply a source's configured keyword/sector/state/value filters to a raw item."""
    text = f"{_norm(item.get('title'))} {_norm(item.get('description'))} {_norm(item.get('sector'))}"

    keywords = [_norm(k) for k in (source.get("keywords") or []) if k]
    if keywords and not any(k in text for k in keywords):
        return False

    sectors = [_norm(s) for s in (source.get("sectors") or []) if s]
    if sectors and item.get("sector"):
        if not any(s in _norm(item["sector"]) for s in sectors):
            return False

    value = item.get("tender_value")
    if value is not None:
        if source.get("min_value") is not None and float(value) < float(source["min_value"]):
            return False
        if source.get("max_value") is not None and float(value) > float(source["max_value"]):
            return False

    return True
