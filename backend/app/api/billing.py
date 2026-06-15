"""
Billing API: subscribe, usage, Razorpay webhook.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.dependencies import get_current_org, require_owner
from app.models import Subscription, Organization, User, SubscriptionStatus
from app.schemas import UsageResponse
from app.billing.razorpay_handler import razorpay_handler, TIER_LIMITS, TIER_PRICES
from app.billing.usage_tracker import usage_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/subscribe")
async def subscribe(
    tier: str,
    org: Organization = Depends(get_current_org),
    _: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Create a subscription for the organization."""
    if tier not in ("starter", "pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid tier")

    if tier == "enterprise":
        return {"message": "Contact sales for enterprise pricing", "tier": tier}

    result = razorpay_handler.create_subscription(tier)

    sub = db.query(Subscription).filter(Subscription.organization_id == org.id).first()
    if sub:
        sub.razorpay_subscription_id = result["subscription_id"]
        sub.tier = tier
        sub.status = SubscriptionStatus.ACTIVE
        sub.price_per_month = TIER_PRICES[tier]
    else:
        sub = Subscription(
            organization_id=org.id,
            razorpay_subscription_id=result["subscription_id"],
            tier=tier,
            status=SubscriptionStatus.ACTIVE,
            price_per_month=TIER_PRICES[tier],
        )
        db.add(sub)

    org.max_monthly_analyses = TIER_LIMITS[tier]
    db.commit()

    return {
        "subscription_id": result["subscription_id"],
        "payment_url": result.get("short_url"),
        "tier": tier,
    }


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Get current month usage against quota."""
    sub = db.query(Subscription).filter(Subscription.organization_id == org.id).first()
    tier = sub.tier if sub else "free"
    limit = TIER_LIMITS.get(tier, 3)
    used = usage_tracker.current_usage(db, str(org.id))

    return UsageResponse(
        tier=tier,
        tenders_analyzed=used,
        tenders_limit=limit,
        percent_used=round((used / limit) * 100, 1) if limit else 0,
    )


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Razorpay subscription lifecycle webhooks."""
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not razorpay_handler.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    payload = json.loads(body)
    event = razorpay_handler.parse_webhook_event(payload)

    sub = (
        db.query(Subscription)
        .filter(Subscription.razorpay_subscription_id == event["subscription_id"])
        .first()
    )
    if not sub:
        return {"status": "ignored", "reason": "subscription not found"}

    if event["event"] == "subscription.activated":
        sub.status = SubscriptionStatus.ACTIVE
    elif event["event"] == "subscription.halted":
        sub.status = SubscriptionStatus.HALTED
        org = db.query(Organization).filter(Organization.id == sub.organization_id).first()
        if org:
            org.is_active = False
    elif event["event"] == "subscription.cancelled":
        sub.status = SubscriptionStatus.CANCELED

    db.commit()
    return {"status": "processed", "event": event["event"]}
