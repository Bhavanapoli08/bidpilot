"""
Scoring API: compute and retrieve bid-suitability scores.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_org
from app.models import (
    Tender, TenderAnalysis, TenderScore, CompanyProfile,
    Organization, TenderStatus,
)
from app.schemas import TenderScoreResponse
from app.scoring.scorer import score_tender

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenders", tags=["scoring"])


def _build_tender_dict(analysis: TenderAnalysis) -> dict:
    """Convert a TenderAnalysis row into the dict the scorer expects."""
    return {
        "tender_value": float(analysis.tender_value) if analysis.tender_value else 0,
        "bid_deadline": analysis.bid_deadline.isoformat() if analysis.bid_deadline else None,
        "sectors": [analysis.sector] if analysis.sector else [],
        "location": analysis.location,
        "eligibility_criteria": analysis.eligibility_criteria or [],
        "required_documents": analysis.required_documents or [],
        "penalty_clauses": analysis.penalty_clauses or [],
    }


def _build_company_dict(profile: CompanyProfile) -> dict:
    return {
        "annual_turnover": float(profile.annual_turnover) if profile.annual_turnover else 0,
        "net_worth": float(profile.net_worth) if profile.net_worth else 0,
        "team_size": profile.team_size,
        "sectors": profile.sectors or [],
        "operating_states": profile.operating_states or [],
        "certifications": profile.certifications or {},
        "registrations": profile.registrations or {},
        "past_projects": profile.past_projects or [],
        "bid_success_rate": profile.bid_success_rate,
    }


@router.post("/{tender_id}/score", response_model=TenderScoreResponse)
async def compute_score(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Compute the bid-suitability score for a tender using the org's company profile."""
    tender = (
        db.query(Tender)
        .filter(Tender.id == tender_id, Tender.organization_id == org.id)
        .first()
    )
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    if tender.status != TenderStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Tender still processing")

    analysis = (
        db.query(TenderAnalysis)
        .filter(TenderAnalysis.tender_id == tender_id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Tender analysis not available")

    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.organization_id == org.id)
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No company profile found. Create one at /company/profile first.",
        )

    result = score_tender(_build_tender_dict(analysis), _build_company_dict(profile))

    # Persist score
    score_row = TenderScore(
        tender_id=tender_id,
        company_profile_id=profile.id,
        organization_id=org.id,
        win_probability=result["win_probability"],
        eligibility_score=result["eligibility_score"],
        fit_score=result["fit_score"],
        risk_level=result["risk_level"],
        risk_score=result["risk_score"],
        competition_intensity=result["competition_intensity"],
        recommendation=result["recommendation"],
        factors=result["factors"],
        reasoning=result["reasoning"],
    )
    db.add(score_row)
    db.commit()

    return TenderScoreResponse(
        win_probability=result["win_probability"],
        eligibility_score=result["eligibility_score"],
        fit_score=result["fit_score"],
        risk_level=result["risk_level"],
        competition_intensity=result["competition_intensity"],
        recommendation=result["recommendation"],
        reasoning=result["reasoning"],
    )


@router.get("/{tender_id}/score", response_model=TenderScoreResponse)
async def get_latest_score(
    tender_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Retrieve the most recent score for a tender."""
    score = (
        db.query(TenderScore)
        .filter(TenderScore.tender_id == tender_id, TenderScore.organization_id == org.id)
        .order_by(TenderScore.created_at.desc())
        .first()
    )
    if not score:
        raise HTTPException(status_code=404, detail="No score found. Compute one first.")

    return TenderScoreResponse(
        win_probability=score.win_probability,
        eligibility_score=score.eligibility_score,
        fit_score=score.fit_score,
        risk_level=score.risk_level,
        competition_intensity=score.competition_intensity,
        recommendation=score.recommendation,
        reasoning=score.reasoning or [],
    )
