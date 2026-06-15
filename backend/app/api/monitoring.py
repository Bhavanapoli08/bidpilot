"""
Monitoring API: configure tender sources, run scans, triage discovered tenders.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_org, get_current_user, require_admin
from app.models import (
    Organization, User, TenderSource, DiscoveredTender, DiscoveredStatus,
    Bid, BidStage, BidEvent,
)
from app.schemas import (
    TenderSourceCreate, TenderSourceUpdate, TenderSourceResponse,
    DiscoveredTenderResponse, ScanResult, BidResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ---- Sources ----
@router.post("/sources", response_model=TenderSourceResponse)
async def create_source(
    payload: TenderSourceCreate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register a portal/feed to monitor (admins only)."""
    if payload.source_type not in ("rss", "http_json", "sample"):
        raise HTTPException(status_code=400, detail="Invalid source_type")
    source = TenderSource(
        organization_id=org.id,
        name=payload.name,
        source_type=payload.source_type,
        url=payload.url,
        config=payload.config,
        keywords=payload.keywords,
        sectors=payload.sectors,
        states=payload.states,
        min_value=payload.min_value,
        max_value=payload.max_value,
        is_active=payload.is_active,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/sources", response_model=list[TenderSourceResponse])
async def list_sources(
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    return (
        db.query(TenderSource)
        .filter(TenderSource.organization_id == org.id)
        .order_by(TenderSource.created_at.desc())
        .all()
    )


@router.patch("/sources/{source_id}", response_model=TenderSourceResponse)
async def update_source(
    source_id: UUID,
    payload: TenderSourceUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    source = _get_source(db, source_id, org)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    source = _get_source(db, source_id, org)
    db.delete(source)
    db.commit()
    return {"status": "deleted", "source_id": str(source_id)}


# ---- Scan ----
@router.post("/scan", response_model=ScanResult)
async def scan_now(
    org: Organization = Depends(get_current_org),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Run all active sources for this org synchronously and return what was found."""
    from app.monitoring.scanner import scan_organization
    totals = scan_organization(db, org.id)
    return ScanResult(
        sources_scanned=totals["sources"],
        new_discovered=totals["new"],
        alerts_created=totals["alerts"],
    )


# ---- Discovered tenders ----
@router.get("/discovered", response_model=list[DiscoveredTenderResponse])
async def list_discovered(
    status: str = Query("new"),
    min_match: float = Query(0.0, ge=0.0, le=1.0),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List discovered opportunities, newest/best first. `status=all` for everything."""
    q = db.query(DiscoveredTender).filter(DiscoveredTender.organization_id == org.id)
    if status != "all":
        q = q.filter(DiscoveredTender.status == status)
    if min_match > 0:
        q = q.filter(DiscoveredTender.match_score >= min_match)
    return q.order_by(
        DiscoveredTender.match_score.desc(), DiscoveredTender.discovered_at.desc()
    ).all()


@router.post("/discovered/{discovered_id}/dismiss", response_model=DiscoveredTenderResponse)
async def dismiss_discovered(
    discovered_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    discovered = _get_discovered(db, discovered_id, org)
    discovered.status = DiscoveredStatus.DISMISSED
    db.commit()
    db.refresh(discovered)
    return discovered


@router.post("/discovered/{discovered_id}/import", response_model=BidResponse)
async def import_discovered(
    discovered_id: UUID,
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Promote a discovered tender into the bid pipeline."""
    discovered = _get_discovered(db, discovered_id, org)
    if discovered.status == DiscoveredStatus.IMPORTED:
        existing = (
            db.query(Bid)
            .filter(Bid.discovered_tender_id == discovered.id)
            .order_by(Bid.created_at.desc())
            .first()
        )
        if existing:
            return existing

    bid = Bid(
        organization_id=org.id,
        discovered_tender_id=discovered.id,
        title=discovered.title,
        stage=BidStage.IDENTIFIED,
        created_by_id=user.id,
        tender_value=discovered.tender_value,
        bid_deadline=discovered.bid_deadline,
        win_probability=discovered.match_score,
    )
    db.add(bid)
    db.flush()
    db.add(BidEvent(
        bid_id=bid.id,
        organization_id=org.id,
        actor_id=user.id,
        event_type="created",
        to_value=BidStage.IDENTIFIED.value,
        note="Imported from monitoring",
    ))
    discovered.status = DiscoveredStatus.IMPORTED
    db.commit()
    db.refresh(bid)
    return bid


# ---- helpers ----
def _get_source(db: Session, source_id: UUID, org: Organization) -> TenderSource:
    source = (
        db.query(TenderSource)
        .filter(TenderSource.id == source_id, TenderSource.organization_id == org.id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


def _get_discovered(db: Session, discovered_id: UUID, org: Organization) -> DiscoveredTender:
    discovered = (
        db.query(DiscoveredTender)
        .filter(DiscoveredTender.id == discovered_id, DiscoveredTender.organization_id == org.id)
        .first()
    )
    if not discovered:
        raise HTTPException(status_code=404, detail="Discovered tender not found")
    return discovered
