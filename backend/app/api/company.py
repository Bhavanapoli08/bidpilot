"""
Company profile API: create, read, update the company "DNA" used for scoring.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_org, require_admin
from app.models import CompanyProfile, Organization, User
from app.schemas import CompanyProfileCreate, CompanyProfileResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/company", tags=["company"])


@router.post("/profile", response_model=CompanyProfileResponse)
async def create_or_update_profile(
    data: CompanyProfileCreate,
    org: Organization = Depends(get_current_org),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create or update the organization's company profile."""
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.organization_id == org.id)
        .first()
    )

    if profile:
        # Update existing
        profile.company_name = data.company_name
        profile.annual_turnover = data.annual_turnover
        profile.net_worth = data.net_worth
        profile.team_size = data.team_size
        profile.sectors = data.sectors
        profile.operating_states = data.operating_states
        profile.certifications = data.certifications
        profile.registrations = data.registrations
        profile.years_in_business = data.years_in_business
    else:
        profile = CompanyProfile(
            organization_id=org.id,
            company_name=data.company_name,
            annual_turnover=data.annual_turnover,
            net_worth=data.net_worth,
            team_size=data.team_size,
            sectors=data.sectors,
            operating_states=data.operating_states,
            certifications=data.certifications,
            registrations=data.registrations,
            years_in_business=data.years_in_business,
        )
        db.add(profile)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profile", response_model=CompanyProfileResponse)
async def get_profile(
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Get the organization's company profile."""
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.organization_id == org.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="No company profile yet")
    return profile


@router.post("/profile/projects")
async def add_past_project(
    project: dict,
    org: Organization = Depends(get_current_org),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Append a past project to the company profile (for experience scoring)."""
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.organization_id == org.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Create a company profile first")

    projects = list(profile.past_projects or [])
    projects.append(project)
    profile.past_projects = projects
    db.commit()
    return {"status": "added", "total_projects": len(projects)}
