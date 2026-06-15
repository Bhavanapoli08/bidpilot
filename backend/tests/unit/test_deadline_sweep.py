"""
Unit tests for the deadline alert sweep — focus on idempotency / dedup.
"""
import uuid
from datetime import datetime, timedelta

from app.models import Organization, Bid, BidStage, Notification
from app.notifications.deadline_sweep import sweep_deadlines


def _make_org(db):
    org = Organization(id=uuid.uuid4(), name="Acme", email=f"{uuid.uuid4()}@x.com")
    db.add(org)
    db.commit()
    return org


def _make_bid(db, org, days_out, stage=BidStage.PREPARING):
    bid = Bid(
        organization_id=org.id,
        title="Test bid",
        stage=stage,
        bid_deadline=datetime.utcnow() + timedelta(days=days_out),
        deadline_alerts_sent=[],
    )
    db.add(bid)
    db.commit()
    return bid


def test_sweep_fires_once_then_dedups(db_session):
    org = _make_org(db_session)
    _make_bid(db_session, org, days_out=2)  # within the 3-day threshold

    first = sweep_deadlines(db_session, org.id)
    assert first["alerts"] == 1
    assert db_session.query(Notification).count() == 1

    # Re-running must not create another alert for the same threshold.
    second = sweep_deadlines(db_session, org.id)
    assert second["alerts"] == 0
    assert db_session.query(Notification).count() == 1


def test_sweep_ignores_terminal_and_far_bids(db_session):
    org = _make_org(db_session)
    _make_bid(db_session, org, days_out=2, stage=BidStage.WON)   # terminal -> ignored
    _make_bid(db_session, org, days_out=30)                       # outside all thresholds

    result = sweep_deadlines(db_session, org.id)
    assert result["alerts"] == 0


def test_sweep_escalates_to_next_threshold(db_session):
    org = _make_org(db_session)
    bid = _make_bid(db_session, org, days_out=5)  # crosses 7-day only

    assert sweep_deadlines(db_session, org.id)["alerts"] == 1
    assert 7 in (bid.deadline_alerts_sent or [])

    # Move the deadline closer; the 3-day threshold should now fire.
    bid.bid_deadline = datetime.utcnow() + timedelta(days=2)
    db_session.commit()
    assert sweep_deadlines(db_session, org.id)["alerts"] == 1
    assert 3 in (bid.deadline_alerts_sent or [])
