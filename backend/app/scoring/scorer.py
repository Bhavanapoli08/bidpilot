"""
Tender Scoring Engine — the competitive moat.

Combines extracted tender data + company profile into a multi-factor
bid-suitability score:

  win_probability = 0.35*eligibility + 0.25*fit + 0.15*timeline
                  + 0.15*(1-risk) + 0.10*(1-competition)

Each sub-score is independently computed and fully explainable.
"""
import logging
from datetime import datetime
from statistics import mean
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# State adjacency for geographic fit (abbreviated; extend as needed)
STATE_NEIGHBORS = {
    "Maharashtra": ["Gujarat", "Karnataka", "Goa", "Madhya Pradesh", "Telangana"],
    "Gujarat": ["Maharashtra", "Rajasthan", "Madhya Pradesh"],
    "Karnataka": ["Maharashtra", "Tamil Nadu", "Kerala", "Telangana", "Goa"],
    "Telangana": ["Maharashtra", "Karnataka", "Andhra Pradesh"],
    "Tamil Nadu": ["Karnataka", "Kerala", "Andhra Pradesh"],
    "Delhi": ["Haryana", "Uttar Pradesh"],
}

WEIGHTS = {
    "eligibility": 0.35,
    "fit": 0.25,
    "timeline": 0.15,
    "risk": 0.15,
    "competition": 0.10,
}


class TenderScorer:
    """Multi-factor tender scorer."""

    def __init__(self, tender: Dict[str, Any], company: Dict[str, Any]):
        self.tender = tender
        self.company = company

    def score(self) -> Dict[str, Any]:
        eligibility = self._score_eligibility()
        fit = self._score_fit()
        timeline = self._score_timeline()
        risk = self._score_risk(eligibility, timeline)
        competition = self._score_competition()

        win_prob = (
            eligibility["score"] * WEIGHTS["eligibility"]
            + fit["score"] * WEIGHTS["fit"]
            + timeline["score"] * WEIGHTS["timeline"]
            + (1 - risk["score"]) * WEIGHTS["risk"]
            + (1 - competition["score"]) * WEIGHTS["competition"]
        )

        # Hard gate: if not legally eligible, cap win probability
        if not eligibility["can_legally_bid"]:
            win_prob = min(win_prob, 0.35)

        recommendation = self._recommend(win_prob, risk["level"])

        return {
            "win_probability": round(win_prob, 3),
            "eligibility_score": round(eligibility["score"], 3),
            "fit_score": round(fit["score"], 3),
            "risk_level": risk["level"],
            "risk_score": round(risk["score"], 3),
            "competition_intensity": competition["level"],
            "recommendation": recommendation,
            "factors": {
                "eligibility": eligibility["breakdown"],
                "fit": fit["breakdown"],
                "timeline": timeline["breakdown"],
                "risk": risk["factors"],
                "competition": competition["breakdown"],
            },
            "reasoning": self._reasoning(eligibility, fit, timeline, risk, recommendation),
        }

    # ---------- ELIGIBILITY (35%) ----------
    def _score_eligibility(self) -> Dict[str, Any]:
        criteria = self.tender.get("eligibility_criteria", []) or []
        met = 0
        total = max(len(criteria), 1)
        breakdown: List[Dict[str, Any]] = []

        for c in criteria:
            ctype = c.get("type")
            passed = False
            detail = ""

            if ctype == "turnover":
                req = c.get("amount", 0)
                have = self.company.get("annual_turnover", 0)
                passed = have >= req
                detail = f"Turnover need ₹{req}L, have ₹{have}L"
            elif ctype == "net_worth":
                req = c.get("amount", 0)
                have = self.company.get("net_worth", 0)
                passed = have >= req
                detail = f"Net worth need ₹{req}L, have ₹{have}L"
            elif ctype == "certification":
                name = c.get("name", "")
                passed = bool(self.company.get("certifications", {}).get(name))
                detail = f"{name}: {'present' if passed else 'missing (waiver may apply)'}"
            elif ctype == "experience":
                sector = c.get("sector")
                req_n = c.get("min_projects", 1)
                have_n = len([
                    p for p in self.company.get("past_projects", [])
                    if sector in (p.get("sectors") or [])
                ])
                passed = have_n >= req_n
                detail = f"{sector} experience: need {req_n}, have {have_n}"
            elif ctype == "registration":
                name = c.get("name", "")
                val = self.company.get("registrations", {}).get(name)
                passed = bool(val)
                detail = f"{name} registration: {'yes' if passed else 'no'}"
            else:
                detail = f"Unknown criterion: {ctype}"

            met += int(passed)
            breakdown.append({
                "name": c.get("name", ctype),
                "met": passed,
                "detail": detail,
                "severity": "high" if ctype in ("turnover", "net_worth", "registration") else "medium",
            })

        score = met / total
        return {
            "score": score,
            "can_legally_bid": score >= 0.70,
            "breakdown": breakdown,
            "met": met,
            "total": total,
        }

    # ---------- FIT (25%) ----------
    def _score_fit(self) -> Dict[str, Any]:
        scores = []
        breakdown = []

        # Sector overlap
        t_sectors = set(self.tender.get("sectors", []) or [])
        c_sectors = set(self.company.get("sectors", []) or [])
        overlap = len(t_sectors & c_sectors) / max(len(t_sectors), 1) if t_sectors else 0.5
        scores.append(overlap)
        breakdown.append({
            "factor": "Sector fit",
            "score": round(overlap, 2),
            "detail": f"Overlap: {t_sectors & c_sectors or 'none'}",
        })

        # Team size
        req_team = self.tender.get("required_team_size")
        if req_team:
            have_team = self.company.get("team_size", 0)
            ratio = have_team / req_team if req_team else 1
            team_score = min(ratio / 1.2, 1.0)
            scores.append(team_score)
            breakdown.append({
                "factor": "Team size",
                "score": round(team_score, 2),
                "detail": f"Have {have_team}, need {req_team}",
            })

        # Geographic fit
        location = self.tender.get("location")
        if location:
            c_states = self.company.get("operating_states", []) or []
            if location in c_states:
                geo = 1.0
                geo_detail = f"Operating in {location}"
            elif any(n in c_states for n in STATE_NEIGHBORS.get(location, [])):
                geo = 0.7
                geo_detail = f"Operating near {location}"
            else:
                geo = 0.3
                geo_detail = f"Not in {location}; expansion needed"
            scores.append(geo)
            breakdown.append({"factor": "Geographic fit", "score": geo, "detail": geo_detail})

        # Project value fit
        t_value = self.tender.get("tender_value", 0) or 0
        c_turnover = (self.company.get("annual_turnover", 0) or 0) * 100000  # lakhs -> rupees
        if t_value and c_turnover:
            if t_value > c_turnover:
                val_score = 0.4
                val_detail = "Tender exceeds annual turnover (risky)"
            elif t_value < c_turnover * 0.01:
                val_score = 0.6
                val_detail = "Tender small for company size"
            else:
                val_score = 1.0
                val_detail = "Project value in sweet spot"
            scores.append(val_score)
            breakdown.append({"factor": "Value fit", "score": val_score, "detail": val_detail})

        fit_score = mean(scores) if scores else 0.5
        return {"score": fit_score, "breakdown": breakdown}

    # ---------- TIMELINE (15%) ----------
    def _score_timeline(self) -> Dict[str, Any]:
        deadline = self.tender.get("bid_deadline")
        if not deadline:
            return {"score": 1.0, "days_available": None,
                    "breakdown": {"detail": "No deadline specified"}}

        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except ValueError:
                return {"score": 0.5, "days_available": None,
                        "breakdown": {"detail": "Could not parse deadline"}}

        days = (deadline.replace(tzinfo=None) - datetime.utcnow()).days

        if days >= 14:
            score, status = 1.0, "ample"
        elif days >= 10:
            score, status = 0.9, "good"
        elif days >= 7:
            score, status = 0.7, "tight"
        elif days >= 3:
            score, status = 0.4, "very tight"
        else:
            score, status = 0.1, "almost expired"

        return {
            "score": score,
            "days_available": days,
            "breakdown": {"detail": f"{days} days to prepare ({status})"},
        }

    # ---------- RISK (15%, inverted) ----------
    def _score_risk(self, eligibility: Dict, timeline: Dict) -> Dict[str, Any]:
        risk = 0.0
        factors = []

        t_value = self.tender.get("tender_value", 0) or 0

        # Penalty severity
        penalties = self.tender.get("penalty_clauses", []) or []
        max_pen = max([p.get("amount", 0) for p in penalties], default=0)
        if t_value and max_pen > t_value * 0.10:
            risk += 0.2
            factors.append({"risk": "Severe penalties", "severity": "high",
                            "detail": f"Up to {round(max_pen / t_value * 100)}% of contract"})

        # Performance bond
        bonds = [p for p in penalties if p.get("type") == "performance_bond"]
        if bonds:
            pct = bonds[0].get("percentage", 5)
            if pct > 10:
                risk += 0.15
                factors.append({"risk": "High performance bond", "severity": "medium",
                                "detail": f"{pct}% of contract value"})

        # Eligibility gaps
        unmet = [b for b in eligibility["breakdown"] if not b["met"]]
        if unmet:
            risk += 0.1 * len(unmet)
            factors.append({"risk": "Eligibility gaps", "severity": "medium",
                            "detail": f"{len(unmet)} criteria unmet"})

        # Timeline pressure
        days = timeline.get("days_available")
        if days is not None and days < 3:
            risk += 0.35
            factors.append({"risk": "Deadline risk", "severity": "critical",
                            "detail": "Insufficient prep time"})
        elif days is not None and days < 7:
            risk += 0.15
            factors.append({"risk": "Timeline pressure", "severity": "high",
                            "detail": "Limited prep time"})

        # Track record
        success_rate = self.company.get("bid_success_rate", 0.5)
        if success_rate < 0.3:
            risk += 0.15
            factors.append({"risk": "Low win history", "severity": "medium",
                            "detail": f"{round(success_rate * 100)}% historical win rate"})

        risk = min(risk, 1.0)
        level = "high" if risk > 0.6 else "medium" if risk > 0.3 else "low"
        return {"score": risk, "level": level, "factors": factors}

    # ---------- COMPETITION (10%, inverted) ----------
    def _score_competition(self) -> Dict[str, Any]:
        t_value = self.tender.get("tender_value", 0) or 0

        if t_value > 1000_00_000:
            score, level, bidders = 0.8, "very_high", 50
        elif t_value > 100_00_000:
            score, level, bidders = 0.6, "high", 20
        elif t_value > 10_00_000:
            score, level, bidders = 0.4, "medium", 8
        else:
            score, level, bidders = 0.2, "low", 3

        sector = (self.tender.get("sectors", ["unknown"]) or ["unknown"])[0]
        if sector in ("construction", "IT", "management"):
            score = min(score + 0.1, 1.0)

        return {
            "score": score,
            "level": level,
            "breakdown": {"detail": f"~{bidders} expected bidders ({level})"},
        }

    # ---------- RECOMMENDATION ----------
    @staticmethod
    def _recommend(win_prob: float, risk_level: str) -> str:
        if win_prob >= 0.75 and risk_level in ("low", "medium"):
            return "high_priority"
        if win_prob >= 0.60 and risk_level == "low":
            return "medium_priority"
        if win_prob >= 0.50 and risk_level == "medium":
            return "medium_priority"
        if risk_level == "high":
            return "low_priority"
        if win_prob < 0.40:
            return "skip"
        return "maybe"

    @staticmethod
    def _reasoning(eligibility, fit, timeline, risk, recommendation) -> List[str]:
        out = []
        out.append(f"Meets {eligibility['met']}/{eligibility['total']} eligibility criteria.")
        positives = [b for b in eligibility["breakdown"] if b["met"]][:2]
        for p in positives:
            out.append(f"✓ {p['detail']}")
        negatives = [b for b in eligibility["breakdown"] if not b["met"]][:2]
        for n in negatives:
            out.append(f"✗ {n['detail']}")
        if timeline.get("days_available") is not None:
            out.append(f"⏱ {timeline['breakdown']['detail']}")
        for f in risk["factors"]:
            if f["severity"] in ("high", "critical"):
                out.append(f"⚠ {f['risk']}: {f['detail']}")
        out.append(f"→ Recommendation: {recommendation.replace('_', ' ').title()}")
        return out


def score_tender(tender: Dict[str, Any], company: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience wrapper."""
    return TenderScorer(tender, company).score()


