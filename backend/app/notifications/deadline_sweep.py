"""
Deadline alert sweep.

Walks active bids and fires an alert as each deadline threshold is crossed
(7 / 3 / 1 days out). Idempotent: every fired threshold is recorded on the bid's
`deadline_alerts_sent`, so re-running the sweep (e.g. the daily beat task) never
duplicates an alert. If multiple thresholds are crossed at once (a bid added with
a deadline 2 days out), it fires a single alert for the most urgent and records
the rest as already handled.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models import Bid, BidStage, NotificationType, TERMINAL_BID_STAGES
from app.notifications.service import create_notification
from app.config import settings

logger = logging.getLogger(__name__)

THRESHOLDS = [7, 3, 1]  # days-remaining checkpoints, descending


def _days_remaining(deadline: datetime) -> int:
    return (deadline.date() - datetime.utcnow().date()).days


def sweep_deadlines(db: Session, organization_id=None) -> Dict[str, int]:
    """Fire deadline alerts for active bids. Returns {'alerts': n}."""
    q = db.query(Bid).filter(
        Bid.bid_deadline.isnot(None),
        Bid.stage.notin_([s.value for s in TERMINAL_BID_STAGES]),
    )
    if organization_id is not None:
        q = q.filter(Bid.organization_id == organization_id)

    alerts = 0
    for bid in q.all():
        days = _days_remaining(bid.bid_deadline)
        sent = list(bid.deadline_alerts_sent or [])
        crossed = [t for t in THRESHOLDS if days <= t and t not in sent]
        if not crossed:
            continue

        # Most urgent newly-crossed threshold drives the single alert.
        urgent = min(crossed)
        when = "today or overdue" if days <= 0 else f"in {days} day{'s' if days != 1 else ''}"
        created = create_notification(
            db,
            organization_id=bid.organization_id,
            type=NotificationType.DEADLINE_APPROACHING,
            title=f"Deadline {when}: {bid.title[:120]}",
            body=f"Bid is in stage '{bid.stage}'. Submission deadline {bid.bid_deadline:%d %b %Y}.",
            link=f"{settings.FRONTEND_URL}/dashboard/bids/{bid.id}",
            user_id=bid.assigned_to_id,
            bid_id=bid.id,
            dedup_key=f"deadline:{bid.id}:{urgent}",
            email=True,
            commit=False,
        )
        # Record every crossed threshold so we don't backfill alerts next run.
        bid.deadline_alerts_sent = sorted(set(sent + crossed), reverse=True)
        if created:
            alerts += 1

    db.commit()
    return {"alerts": alerts}
