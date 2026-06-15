"""
Usage tracking and quota enforcement.
"""
import logging
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models import UsageLog, Subscription, Organization
from app.billing.razorpay_handler import TIER_LIMITS

logger = logging.getLogger(__name__)


class UsageTracker:
    """Tracks monthly tender analysis usage and enforces tier quotas."""

    @staticmethod
    def _current_month() -> date:
        today = date.today()
        return date(today.year, today.month, 1)

    def current_usage(self, db: Session, org_id: str) -> int:
        """Return tenders analyzed in the current month."""
        log = (
            db.query(UsageLog)
            .filter(UsageLog.organization_id == org_id, UsageLog.month == self._current_month())
            .first()
        )
        return log.tenders_analyzed if log else 0

    def check_quota(self, db: Session, org_id: str):
        """Raise 429 if the org has exceeded its monthly quota."""
        sub = db.query(Subscription).filter(Subscription.organization_id == org_id).first()
        tier = sub.tier if sub else "free"
        limit = TIER_LIMITS.get(tier, 3)

        used = self.current_usage(db, org_id)
        if used >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly quota reached ({used}/{limit}). Upgrade your plan to continue.",
            )

    def increment(self, db: Session, org_id: str, count: int = 1):
        """Increment the org's tender count for the current month."""
        month = self._current_month()
        log = (
            db.query(UsageLog)
            .filter(UsageLog.organization_id == org_id, UsageLog.month == month)
            .first()
        )
        if log:
            log.tenders_analyzed += count
        else:
            log = UsageLog(
                organization_id=org_id,
                month=month,
                tenders_analyzed=count,
            )
            db.add(log)
        db.commit()


usage_tracker = UsageTracker()
