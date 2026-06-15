"""
Bids API: the procurement pipeline — create, advance stages, assign, calendar.
"""
import logging
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_org, get_current_user
from app.models import (
    Organization, User, Bid, BidEvent, BidStage, TERMINAL_BID_STAGES,
    Tender, TenderAnalysis, TenderScore, DiscoveredTender, NotificationType,
)
from app.schemas import (
    BidCreate, BidResponse, BidDetailResponse, BidStageUpdate, BidAssign,
    CalendarEvent,
)
from app.notifications.service import create_notification
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bids", tags=["bids"])

VALID_STAGES = {s.value for s in BidStage}


@router.post("", response_model=BidResponse)
async def create_bid(
    payload: BidCreate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a bid from an uploaded tender, a discovered tender, or manually."""
    title = payload.title
    value = None
    deadline = None
    win_prob = None

    if payload.tender_id:
        tender = (
            db.query(Tender)
            .filter(Tender.id == payload.tender_id, Tender.organization_id == org.id)
            .first()
        )
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")
        title = title or tender.file_name
        analysis = (
            db.query(TenderAnalysis)
            .filter(TenderAnalysis.tender_id == tender.id)
            .first()
        )
        if analysis:
            value = analysis.tender_value
            deadline = analysis.bid_deadline
        score = (
            db.query(TenderScore)
            .filter(TenderScore.tender_id == tender.id)
            .order_by(TenderScore.created_at.desc())
            .first()
        )
        if score:
            win_prob = score.win_probability

    elif payload.discovered_tender_id:
        discovered = (
            db.query(DiscoveredTender)
            .filter(
                DiscoveredTender.id == payload.discovered_tender_id,
                DiscoveredTender.organization_id == org.id,
            )
            .first()
        )
        if not discovered:
            raise HTTPException(status_code=404, detail="Discovered tender not found")
        title = title or discovered.title
        value = discovered.tender_value
        deadline = discovered.bid_deadline
        win_prob = discovered.match_score

    if not title:
        raise HTTPException(status_code=400, detail="A title is required for a manual bid")

    if payload.assigned_to_id:
        _require_org_user(db, payload.assigned_to_id, org)

    bid = Bid(
        organization_id=org.id,
        tender_id=payload.tender_id,
        discovered_tender_id=payload.discovered_tender_id,
        title=title,
        stage=BidStage.IDENTIFIED,
        assigned_to_id=payload.assigned_to_id,
        created_by_id=user.id,
        tender_value=value,
        bid_deadline=deadline,
        win_probability=win_prob,
        notes=payload.notes,
    )
    db.add(bid)
    db.flush()
    db.add(BidEvent(
        bid_id=bid.id, organization_id=org.id, actor_id=user.id,
        event_type="created", to_value=BidStage.IDENTIFIED.value,
    ))
    db.commit()
    db.refresh(bid)
    return bid


@router.get("", response_model=list[BidResponse])
async def list_bids(
    stage: str = Query(None),
    assigned_to_id: UUID = Query(None),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List bids (optionally filtered) — newest first. Group by `stage` for a board."""
    q = db.query(Bid).filter(Bid.organization_id == org.id)
    if stage:
        q = q.filter(Bid.stage == stage)
    if assigned_to_id:
        q = q.filter(Bid.assigned_to_id == assigned_to_id)
    return q.order_by(Bid.updated_at.desc()).all()


@router.get("/calendar", response_model=list[CalendarEvent])
async def bid_calendar(
    days: int = Query(60, ge=1, le=365),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Upcoming deadlines: active bids plus analysed tenders not yet in the pipeline."""
    now = datetime.utcnow()
    horizon = now + timedelta(days=days)
    events: list[CalendarEvent] = []

    bids = (
        db.query(Bid)
        .filter(
            Bid.organization_id == org.id,
            Bid.bid_deadline.isnot(None),
            Bid.bid_deadline <= horizon,
            Bid.stage.notin_([s.value for s in TERMINAL_BID_STAGES]),
        )
        .all()
    )
    bid_tender_ids = set()
    for bid in bids:
        if bid.tender_id:
            bid_tender_ids.add(bid.tender_id)
        events.append(CalendarEvent(
            bid_id=bid.id,
            tender_id=bid.tender_id,
            title=bid.title,
            deadline=bid.bid_deadline,
            stage=bid.stage,
            days_remaining=(bid.bid_deadline.date() - now.date()).days,
        ))

    # Analysed tenders with a deadline that haven't been pulled into a bid yet.
    analyses = (
        db.query(TenderAnalysis)
        .filter(
            TenderAnalysis.organization_id == org.id,
            TenderAnalysis.bid_deadline.isnot(None),
            TenderAnalysis.bid_deadline <= horizon,
        )
        .all()
    )
    for a in analyses:
        if a.tender_id in bid_tender_ids:
            continue
        events.append(CalendarEvent(
            bid_id=None,
            tender_id=a.tender_id,
            title=a.summary[:80] if a.summary else "Tender",
            deadline=a.bid_deadline,
            stage=None,
            days_remaining=(a.bid_deadline.date() - now.date()).days,
        ))

    events.sort(key=lambda e: e.deadline)
    return events


@router.get("/{bid_id}", response_model=BidDetailResponse)
async def get_bid(
    bid_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    bid = _get_bid(db, bid_id, org)
    return bid


@router.patch("/{bid_id}/stage", response_model=BidResponse)
async def update_stage(
    bid_id: UUID,
    payload: BidStageUpdate,
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move a bid to a new pipeline stage; records an audit event."""
    if payload.stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {payload.stage}")
    bid = _get_bid(db, bid_id, org)
    if bid.stage == payload.stage:
        return bid

    previous = bid.stage
    bid.stage = payload.stage
    if payload.stage in {s.value for s in TERMINAL_BID_STAGES}:
        bid.decided_at = datetime.utcnow()
    else:
        bid.decided_at = None

    db.add(BidEvent(
        bid_id=bid.id, organization_id=org.id, actor_id=user.id,
        event_type="stage_change", from_value=previous, to_value=payload.stage,
        note=payload.note,
    ))

    # Notify the assignee (if someone other than the actor).
    if bid.assigned_to_id and bid.assigned_to_id != user.id:
        create_notification(
            db, organization_id=org.id, type=NotificationType.STAGE_CHANGED,
            title=f"Bid moved to '{payload.stage}': {bid.title[:120]}",
            body=f"{user.email} moved this bid from '{previous}' to '{payload.stage}'.",
            link=f"{settings.FRONTEND_URL}/dashboard/bids/{bid.id}",
            user_id=bid.assigned_to_id, bid_id=bid.id, commit=False,
        )

    db.commit()
    db.refresh(bid)
    return bid


@router.patch("/{bid_id}/assign", response_model=BidResponse)
async def assign_bid(
    bid_id: UUID,
    payload: BidAssign,
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign (or unassign, with null) a reviewer to a bid."""
    bid = _get_bid(db, bid_id, org)
    previous = str(bid.assigned_to_id) if bid.assigned_to_id else None

    if payload.assigned_to_id:
        _require_org_user(db, payload.assigned_to_id, org)
    bid.assigned_to_id = payload.assigned_to_id

    db.add(BidEvent(
        bid_id=bid.id, organization_id=org.id, actor_id=user.id,
        event_type="assigned", from_value=previous,
        to_value=str(payload.assigned_to_id) if payload.assigned_to_id else None,
        note=payload.note,
    ))

    if payload.assigned_to_id and payload.assigned_to_id != user.id:
        create_notification(
            db, organization_id=org.id, type=NotificationType.BID_ASSIGNED,
            title=f"You were assigned a bid: {bid.title[:120]}",
            body=payload.note or f"Assigned by {user.email}.",
            link=f"{settings.FRONTEND_URL}/dashboard/bids/{bid.id}",
            user_id=payload.assigned_to_id, bid_id=bid.id, email=True, commit=False,
        )

    db.commit()
    db.refresh(bid)
    return bid


@router.delete("/{bid_id}")
async def delete_bid(
    bid_id: UUID,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    bid = _get_bid(db, bid_id, org)
    db.query(BidEvent).filter(BidEvent.bid_id == bid.id).delete()
    db.delete(bid)
    db.commit()
    return {"status": "deleted", "bid_id": str(bid_id)}


# ---- helpers ----
def _get_bid(db: Session, bid_id: UUID, org: Organization) -> Bid:
    bid = (
        db.query(Bid)
        .filter(Bid.id == bid_id, Bid.organization_id == org.id)
        .first()
    )
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    return bid


def _require_org_user(db: Session, user_id: UUID, org: Organization) -> User:
    target = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == org.id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=400, detail="Assignee must be a member of your organization")
    return target
