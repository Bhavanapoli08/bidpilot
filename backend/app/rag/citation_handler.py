"""
Citation handler — the trust layer.

Flow: Question -> embed -> Qdrant retrieval -> context with chunk IDs
      -> GPT-4 -> answer + cited source pages.

Every answer is traceable to specific pages of the source document.
"""
import json
import logging
from typing import Dict, Any, List
from app.rag.embedder import embedder
from app.rag.llm_client import ai_client
from app.rag.vector_store import vector_store

logger = logging.getLogger(__name__)


class CitationHandler:
    """Retrieves context and generates answers with source citations."""

    def __init__(self):
        self.client = ai_client

    def retrieve(
        self,
        tender_id: str,
        query: str,
        org_id: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Embed the query and retrieve top-k chunks with their source info."""
        query_vector = embedder.embed_text(query)

        hits = vector_store.search(
            query_vector=query_vector,
            org_id=org_id,
            tender_id=tender_id,
            top_k=top_k,
        )

        # Build context block with source markers
        context_parts = []
        sources = []
        for i, hit in enumerate(hits):
            context_parts.append(f"[Source {i}] (page {hit['page']}) {hit['text']}")
            sources.append({
                "source_index": i,
                "page": hit["page"],
                "chunk_id": hit["chunk_id"],
                "score": round(hit["score"], 4),
                "preview": hit["text"][:150] + "...",
            })

        return {
            "context": "\n\n".join(context_parts),
            "sources": sources,
            "query": query,
        }

    def answer_with_citations(
        self,
        tender_id: str,
        query: str,
        org_id: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Generate an answer grounded in retrieved context, with citations."""
        retrieval = self.retrieve(tender_id, query, org_id, top_k)

        if not retrieval["sources"]:
            return {
                "answer": "No relevant information found in this tender document.",
                "citations": [],
                "confidence": 0.0,
                "source_pages": [],
            }

        system_prompt = (
            "You are a tender analysis assistant. Answer ONLY from the provided context. "
            "Cite sources inline as [Source N]. If the answer is not in the context, say "
            "'This information is not available in the tender document.' "
            "Respond in strict JSON: "
            '{"answer": "...", "sources_cited": [0, 2], "confidence": 0.0-1.0}'
        )

        user_prompt = f"Context:\n{retrieval['context']}\n\nQuestion: {query}"

        response_text = self.client.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            json_object=True,
        )

        try:
            parsed = json.loads(response_text)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "answer": response_text,
                "citations": retrieval["sources"],
                "confidence": 0.5,
                "source_pages": [s["page"] for s in retrieval["sources"]],
            }

        cited_indices = parsed.get("sources_cited", [])
        full_citations = [
            retrieval["sources"][i]
            for i in cited_indices
            if i < len(retrieval["sources"])
        ]

        return {
            "answer": parsed.get("answer", ""),
            "citations": full_citations,
            "confidence": parsed.get("confidence", 0.5),
            "source_pages": sorted(set(c["page"] for c in full_citations)),
        }


citation_handler = CitationHandler()
