"""
Tender data extractor.

Pulls structured fields (value, deadline, eligibility, docs, penalties)
out of an indexed tender using targeted RAG queries + GPT-4.
Each field comes back with source pages for auditability.
"""
import json
import logging
from typing import Dict, Any
from app.rag.citation_handler import citation_handler
from app.rag.llm_client import ai_client

logger = logging.getLogger(__name__)


class TenderExtractor:
    """Extracts structured tender data via field-specific RAG queries."""

    # field_name -> retrieval query
    FIELD_QUERIES = {
        "tender_value": "What is the total contract value, tender value, or estimated cost?",
        "bid_deadline": "What is the bid submission deadline or closing date and time?",
        "financial_criteria": "What are the financial eligibility requirements: minimum turnover, net worth?",
        "experience_criteria": "How many years of experience or how many past projects are required?",
        "certifications": "What certifications are mandatory (ISO, OHSAS, etc.)?",
        "required_documents": "What documents must be submitted with the bid?",
        "penalty_clauses": "What are the penalty clauses, EMD, and performance bond requirements?",
        "sector": "What sector or category does this tender belong to?",
        "location": "Where is the work to be performed? Which state or city?",
        "scope": "What is the scope of work or the services required?",
    }

    def __init__(self):
        self.client = ai_client

    def extract_field(self, tender_id: str, org_id: str, field: str, query: str) -> Dict[str, Any]:
        """Extract a single field with structured JSON output + sources."""
        retrieval = citation_handler.retrieve(tender_id, query, org_id, top_k=3)

        if not retrieval["sources"]:
            return {"value": None, "confidence": 0.0, "source_pages": []}

        system_prompt = (
            f"Extract the '{field}' from the tender context. "
            "Return strict JSON: "
            '{"value": <extracted value or null>, "confidence": 0.0-1.0, '
            '"source_pages": [page numbers], "raw_text": "supporting quote"}. '
            "For dates use ISO 8601. For money return a number in the same unit as written, "
            "and include a 'unit' field (e.g. 'lakhs', 'crores', 'INR'). "
            "For lists return an array."
        )

        response_text = self.client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{retrieval['context']}\n\nField: {field}"},
            ],
            temperature=0.1,
            json_object=True,
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse extraction for field {field}")
            return {"value": None, "confidence": 0.0, "source_pages": []}

    def extract_all(self, tender_id: str, org_id: str) -> Dict[str, Any]:
        """Extract every configured field. Returns dict keyed by field name."""
        extracted = {}
        for field, query in self.FIELD_QUERIES.items():
            try:
                extracted[field] = self.extract_field(tender_id, org_id, field, query)
                logger.info(f"Extracted {field} for tender {tender_id}")
            except Exception as e:
                logger.error(f"Extraction failed for {field}: {e}")
                extracted[field] = {"value": None, "confidence": 0.0, "source_pages": []}
        return extracted

    def generate_summary(self, tender_id: str, org_id: str, extracted: Dict[str, Any]) -> str:
        """Generate a concise human-readable summary from extracted fields."""
        facts = json.dumps({k: v.get("value") for k, v in extracted.items()}, default=str)

        return self.client.generate(
            messages=[
                {
                    "role": "system",
                    "content": "Write a 3-4 sentence executive summary of this tender for a "
                               "construction company deciding whether to bid. Be factual and concise.",
                },
                {"role": "user", "content": f"Tender facts: {facts}"},
            ],
            temperature=0.3,
        )


tender_extractor = TenderExtractor()
