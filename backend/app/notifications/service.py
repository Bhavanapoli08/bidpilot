"""
Notification creation helper.

Centralises the "create an in-app alert (+ optionally email the relevant users)"
flow so the scanner, deadline sweep, and bid workflow all behave consistently —
including dedup, which is what keeps a daily deadline sweep from spamming the
same bid every run.
"""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Notification, User
from app.notifications.email_service import send_email

logger = logging.getLogger(__name__)


def create_notification(
    db: Session,
    organization_id,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    user_id=None,
    bid_id=None,
    discovered_tender_id=None,
    dedup_key: Optional[str] = None,
    email: bool = False,
    commit: bool = True,
) -> Optional[Notification]:
    """Create a notification, skipping if `dedup_key` already exists for the org.

    Returns the created Notification, or None if it was deduped.
    """
    if dedup_key:
        exists = (
            db.query(Notification.id)
            .filter(
                Notification.organization_id == organization_id,
                Notification.dedup_key == dedup_key,
            )
            .first()
        )
        if exists:
            return None

    notif = Notification(
        organization_id=organization_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        bid_id=bid_id,
        discovered_tender_id=discovered_tender_id,
        dedup_key=dedup_key,
    )
    db.add(notif)
    if commit:
        db.commit()
        db.refresh(notif)

    if email:
        _dispatch_email(db, organization_id, user_id, title, body, link)

    return notif


def _dispatch_email(db: Session, organization_id, user_id, title, body, link) -> None:
    """Email the targeted user, or all active org users for an org-wide alert."""
    q = db.query(User).filter(User.organization_id == organization_id, User.is_active.is_(True))
    if user_id is not None:
        q = q.filter(User.id == user_id)
    recipients: List[User] = q.all()

    text = body or title
    if link:
        text = f"{text}\n\n{link}"
    for user in recipients:
        send_email(user.email, f"[BidPilot] {title}", text)
