"""
Pluggable tender-source connectors.

A connector turns an external feed into a normalised list of opportunity dicts:

    {
      "external_id": str,        # stable id within the source (for dedup)
      "title": str,
      "description": str | None,
      "tender_value": float | None,
      "bid_deadline": datetime | None,
      "sector": str | None,
      "location": str | None,
      "url": str | None,
    }

Three connectors ship today:

  * RSS        — parses an RSS/Atom feed. Many eProcurement portals (and
                 aggregators like BidAssist/TenderTiger) expose one. LIVE-capable.
  * HTTP_JSON  — GETs a JSON endpoint and maps fields via JSONPath-ish keys in
                 the source `config`. LIVE-capable.
  * SAMPLE     — emits synthetic tenders so the full pipeline (dedup → match →
                 alert → import → score) is exercisable without portal access.

NOTE: Government portals each have their own auth, pagination, and field shapes.
The RSS/HTTP_JSON connectors handle the common cases; portal-specific quirks
(CPPP captcha, GeM OAuth, etc.) need a dedicated subclass + credentials. The
surrounding machinery — scheduling, dedup, matching, alerting — is complete and
production-ready regardless of connector.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class ConnectorError(Exception):
    """Raised when a source cannot be fetched or parsed."""


def _parse_value(text: Optional[str]) -> Optional[float]:
    """Best-effort extraction of a rupee/number amount from free text."""
    if not text:
        return None
    # Strip currency words and grouping, keep digits + decimal.
    m = re.search(r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(cr|crore|lakh|lac|l|k)?", text.lower())
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    unit = m.group(2)
    if unit in ("cr", "crore"):
        num *= 10_000_000
    elif unit in ("lakh", "lac", "l"):
        num *= 100_000
    elif unit == "k":
        num *= 1_000
    return num


def _parse_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    text = text.strip()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=None)  # store naive UTC, matching the rest of the schema
        except ValueError:
            continue
    return None


def _get_by_path(obj: Any, path: str) -> Any:
    """Resolve a dotted path like 'data.deadline' against nested dicts/lists."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class BaseConnector:
    def __init__(self, source: Dict[str, Any]):
        self.source = source
        self.url = source.get("url")
        self.config = source.get("config") or {}

    def fetch(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class RSSConnector(BaseConnector):
    """Parse an RSS 2.0 / Atom feed into opportunities."""

    def fetch(self) -> List[Dict[str, Any]]:
        if not self.url:
            raise ConnectorError("RSS source has no URL")
        try:
            resp = requests.get(self.url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "BidPilot/1.0"})
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
        except (requests.RequestException, ElementTree.ParseError) as e:
            raise ConnectorError(f"RSS fetch/parse failed: {e}") from e

        items: List[Dict[str, Any]] = []
        # RSS 2.0: channel/item ; Atom: feed/entry
        nodes = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        for node in nodes:
            def text(tag: str) -> Optional[str]:
                el = node.find(tag) or node.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
                return el.text if el is not None else None

            title = text("title") or "Untitled tender"
            description = text("description") or text("summary")
            link = text("link")
            if link is None:
                link_el = node.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.get("href") if link_el is not None else None
            guid = text("guid") or link or title
            pub = text("pubDate") or text("published") or text("updated")

            items.append({
                "external_id": guid,
                "title": title.strip(),
                "description": (description or "").strip() or None,
                "tender_value": _parse_value(f"{title} {description or ''}"),
                "bid_deadline": _parse_date(pub),
                "sector": self.config.get("sector"),
                "location": self.config.get("location"),
                "url": link,
            })
        return items


class HTTPJsonConnector(BaseConnector):
    """GET a JSON endpoint; map fields via `config` paths.

    config = {
      "items_path": "data.tenders",   # path to the list (omit if root is a list)
      "fields": {                      # opportunity-key -> source path within an item
        "external_id": "id", "title": "name", "tender_value": "value",
        "bid_deadline": "closing_date", "sector": "category",
        "location": "state", "url": "detail_url", "description": "summary"
      },
      "headers": {"Authorization": "Bearer ..."}
    }
    """

    def fetch(self) -> List[Dict[str, Any]]:
        if not self.url:
            raise ConnectorError("HTTP_JSON source has no URL")
        try:
            resp = requests.get(
                self.url, timeout=REQUEST_TIMEOUT,
                headers=self.config.get("headers") or {"User-Agent": "BidPilot/1.0"},
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError) as e:
            raise ConnectorError(f"HTTP_JSON fetch failed: {e}") from e

        items_path = self.config.get("items_path")
        raw_items = _get_by_path(payload, items_path) if items_path else payload
        if not isinstance(raw_items, list):
            raise ConnectorError("HTTP_JSON items path did not resolve to a list")

        fields = self.config.get("fields") or {}
        results: List[Dict[str, Any]] = []
        for raw in raw_items:
            def f(key: str) -> Any:
                path = fields.get(key)
                return _get_by_path(raw, path) if path else None

            title = f("title") or "Untitled tender"
            value = f("tender_value")
            deadline = f("bid_deadline")
            results.append({
                "external_id": str(f("external_id") or title),
                "title": str(title).strip(),
                "description": f("description"),
                "tender_value": _parse_value(str(value)) if value is not None else None,
                "bid_deadline": _parse_date(str(deadline)) if deadline else None,
                "sector": f("sector"),
                "location": f("location"),
                "url": f("url"),
            })
        return results


class SampleConnector(BaseConnector):
    """Deterministic synthetic feed for demos / local dev. No network."""

    _CATALOG = [
        ("AI software development for citizen services portal", "IT Services", "Maharashtra", 7_500_000, 15),
        ("Cloud migration and managed hosting", "IT Services", "Karnataka", 21_000_000, 20),
        ("Data analytics platform for municipal water board", "IT Services", "Telangana", 4_000_000, 9),
        ("Construction of district office complex", "Construction", "Gujarat", 95_000_000, 30),
        ("Supply and installation of CCTV surveillance", "Security", "Delhi", 12_500_000, 12),
        ("Annual maintenance of e-governance applications", "IT Services", "Maharashtra", 3_200_000, 6),
    ]

    def fetch(self) -> List[Dict[str, Any]]:
        # Seed offset lets the source spread deadlines deterministically.
        base = datetime.utcnow()
        seed = abs(hash(str(self.source.get("id", "sample")))) % 5
        items: List[Dict[str, Any]] = []
        for i, (title, sector, state, value, days) in enumerate(self._CATALOG):
            items.append({
                "external_id": f"SAMPLE-{seed}-{i}",
                "title": title,
                "description": f"Government tender for {title.lower()} in {state}.",
                "tender_value": float(value),
                "bid_deadline": base + timedelta(days=days),
                "sector": sector,
                "location": state,
                "url": f"https://example.gov.in/tenders/SAMPLE-{seed}-{i}",
            })
        return items


_CONNECTORS = {
    "rss": RSSConnector,
    "http_json": HTTPJsonConnector,
    "sample": SampleConnector,
}


def get_connector(source: Dict[str, Any]) -> BaseConnector:
    cls = _CONNECTORS.get(source.get("source_type", "sample"))
    if not cls:
        raise ConnectorError(f"Unknown source_type: {source.get('source_type')}")
    return cls(source)
