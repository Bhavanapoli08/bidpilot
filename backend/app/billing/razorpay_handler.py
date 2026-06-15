"""
Razorpay billing integration: subscriptions, webhooks, usage quotas.
"""
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import razorpay
from app.config import settings

logger = logging.getLogger(__name__)

# Tier -> monthly tender quota
TIER_LIMITS = {
    "free": 3,
    "starter": 10,
    "pro": 50,
    "enterprise": 100000,  # effectively unlimited
}

# Tier -> Razorpay plan ID (configure in Razorpay dashboard)
TIER_PLAN_IDS = {
    "starter": "plan_starter_001",
    "pro": "plan_pro_001",
    "enterprise": "plan_enterprise_001",
}

# Tier -> price in INR/month
TIER_PRICES = {
    "free": 0,
    "starter": 999,
    "pro": 4999,
    "enterprise": 0,  # custom / contact sales
}


class RazorpayHandler:
    """Wraps the Razorpay client for subscription management."""

    def __init__(self):
        self.enabled = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        if self.enabled:
            self.client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
        else:
            self.client = None
            logger.warning("Razorpay not configured; billing disabled")

    def create_subscription(self, tier: str) -> Dict[str, Any]:
        """Create a Razorpay subscription for the given tier."""
        if not self.enabled:
            raise RuntimeError("Razorpay is not configured")
        if tier not in TIER_PLAN_IDS:
            raise ValueError(f"Invalid tier: {tier}")

        subscription = self.client.subscription.create({
            "plan_id": TIER_PLAN_IDS[tier],
            "customer_notify": 1,
            "total_count": 12,
            "start_at": int((datetime.utcnow() + timedelta(days=1)).timestamp()),
        })

        return {
            "subscription_id": subscription["id"],
            "status": subscription["status"],
            "tier": tier,
            "short_url": subscription.get("short_url"),
        }

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Razorpay is not configured")
        return self.client.subscription.cancel(subscription_id)

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant details from a webhook event."""
        event = payload.get("event", "")
        sub_entity = (
            payload.get("payload", {})
            .get("subscription", {})
            .get("entity", {})
        )
        return {
            "event": event,
            "subscription_id": sub_entity.get("id"),
            "status": sub_entity.get("status"),
        }


razorpay_handler = RazorpayHandler()
