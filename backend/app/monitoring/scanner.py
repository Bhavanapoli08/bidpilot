"""
Monitoring orchestration.

Pure(ish) functions that take a DB session — callable from the Celery beat task,
the manual "scan now" API endpoint, and tests alike.

Pipeline per source:
  connector.fetch() -> source filters -> dedup by (source, external_id)
  -> quick_match vs company profile -> persist DiscoveredTender
  -> alert if match >= HIGH_MATCH_THRESHOLD
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import (
    CompanyProfile,
    DiscoveredStatus,
    DiscoveredTender,
    NotificationType,
    TenderSource,
)
from app.monitoring.connectors import ConnectorError, get_connector
from app.monitoring.matcher import passes_source_filters, quick_match
from app.notifications.service import create_notification
from app.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

HIGH_MATCH_THRESHOLD = 0.7


def _source_to_dict(source: TenderSource) -> Dict[str, Any]:
    return {
        "id": str(source.id),
        "source_type": source.source_type,
        "url": source.url,
        "config": source.config or {},
        "keywords": source.keywords or [],
        "sectors": source.sectors or [],
        "states": source.states or [],
        "min_value": float(source.min_value) if source.min_value is not None else None,
        "max_value": float(source.max_value) if source.max_value is not None else None,
    }


def _company_dict(profile: Optional[CompanyProfile]) -> Dict[str, Any]:
    if not profile:
        return {}
    return {
        "sectors": profile.sectors or [],
        "operating_states": profile.operating_states or [],
        "annual_turnover": float(profile.annual_turnover) if profile.annual_turnover else 0,
    }


def scan_source(db: Session, source: TenderSource, company: Optional[CompanyProfile]) -> Dict[str, int]:
    """Scan one source. Returns counts: {new, alerts}. Records errors on the source."""
    src_dict = _source_to_dict(source)
    company_dict = _company_dict(company)
    new_count = 0
    alert_count = 0

    try:
        items = get_connector(src_dict).fetch()
    except ConnectorError as e:
        logger.warning("Source %s scan failed: %s", source.id, e)
        source.last_error = str(e)[:500]
        source.last_checked_at = datetime.utcnow()
        db.commit()
        return {"new": 0, "alerts": 0}

    for item in items:
        if not passes_source_filters(item, src_dict):
            continue

        external_id = str(item.get("external_id") or "")
        if not external_id:
            continue

        # Dedup within the source.
        exists = (
            db.query(DiscoveredTender.id)
            .filter(
                DiscoveredTender.source_id == source.id,
                DiscoveredTender.external_id == external_id,
            )
            .first()
        )
        if exists:
            continue

        score, reasons = quick_match(item, company_dict)

        discovered = DiscoveredTender(
            organization_id=source.organization_id,
            source_id=source.id,
            external_id=external_id,
            title=str(item.get("title"))[:1024],
            description=item.get("description"),
            tender_value=item.get("tender_value"),
            bid_deadline=item.get("bid_deadline"),
            sector=item.get("sector"),
            location=item.get("location"),
            url=item.get("url"),
            match_score=score,
            match_reasons=reasons,
            status=DiscoveredStatus.NEW,
        )
        db.add(discovered)
        db.flush()  # assign id for the alert link
        new_count += 1

        if score >= HIGH_MATCH_THRESHOLD:
            value_str = f"₹{discovered.tender_value:,.0f}" if discovered.tender_value else "value N/A"
            created = create_notification(
                db,
                organization_id=source.organization_id,
                type=NotificationType.NEW_HIGH_MATCH,
                title=f"New {int(score * 100)}% match: {discovered.title[:120]}",
                body=f"{value_str} · {discovered.sector or 'sector N/A'} · {discovered.location or 'location N/A'}",
                link=f"{settings.FRONTEND_URL}/dashboard/monitoring",
                discovered_tender_id=discovered.id,
                dedup_key=f"high_match:{discovered.id}",
                email=True,
                commit=False,
            )
            if created:
                alert_count += 1

    source.last_checked_at = datetime.utcnow()
    source.last_error = None
    db.commit()
    return {"new": new_count, "alerts": alert_count}


def scan_organization(db: Session, organization_id) -> Dict[str, int]:
    """Scan all active sources for one org."""
    sources = (
        db.query(TenderSource)
        .filter(
            TenderSource.organization_id == organization_id,
            TenderSource.is_active.is_(True),
        )
        .all()
    )
    company = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.organization_id == organization_id)
        .first()
    )
    totals = {"sources": 0, "new": 0, "alerts": 0}
    for source in sources:
        result = scan_source(db, source, company)
        totals["sources"] += 1
        totals["new"] += result["new"]
        totals["alerts"] += result["alerts"]
    return totals
