"""
Notifications API: in-app alert feed for the current user / org.
"""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_org, get_current_user
from app.models import Organization, User, Notification
from app.schemas import NotificationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


def _visible(query, org: Organization, user: User):
    """Notifications for this org that are either org-wide or addressed to this user."""
    return query.filter(
        Notification.organization_id == org.id,
        or_(Notification.user_id.is_(None), Notification.user_id == user.id),
    )


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = _visible(db.query(Notification), org, user)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    return q.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/unread-count")
async def unread_count(
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = _visible(db.query(Notification), org, user).filter(
        Notification.is_read.is_(False)
    ).count()
    return {"unread": count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = _visible(db.query(Notification), org, user).filter(
        Notification.id == notification_id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/read-all")
async def mark_all_read(
    org: Organization = Depends(get_current_org),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = _visible(db.query(Notification), org, user).filter(
        Notification.is_read.is_(False)
    ).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"marked_read": updated}
