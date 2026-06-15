"""
Qdrant vector store wrapper. Handles collection setup, upsert, and
multi-tenant filtered search (every query scoped by org_id).
"""
import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.config import settings

logger = logging.getLogger(__name__)

def _vector_size() -> int:
    if settings.EMBEDDING_VECTOR_SIZE:
        return settings.EMBEDDING_VECTOR_SIZE
    if (settings.AI_PROVIDER or "").lower() == "gemini" or settings.GEMINI_API_KEY:
        return 3072
    return 1536


class VectorStore:
    """Qdrant client wrapper for tender document embeddings."""

    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection = settings.QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the collection if it doesn't already exist."""
        try:
            collections = self.client.get_collections().collections
            names = [c.name for c in collections]
            if self.collection not in names:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=_vector_size(),
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection}")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Upsert embedded chunks. Each chunk must have:
        vector, chunk_id, org_id, tender_id, page, text
        """
        points = []
        for idx, chunk in enumerate(chunks):
            # Use a deterministic positive integer ID
            point_id = abs(hash(f"{chunk['tender_id']}_{chunk['chunk_id']}")) % (10 ** 15)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=chunk["vector"],
                    payload={
                        "org_id": str(chunk["org_id"]),
                        "tender_id": str(chunk["tender_id"]),
                        "chunk_id": chunk["chunk_id"],
                        "page": chunk.get("page", 1),
                        "text": chunk["text"][:2000],  # cap payload size
                    },
                )
            )

        self.client.upsert(collection_name=self.collection, points=points)
        logger.info(f"Upserted {len(points)} points to Qdrant")

    def search(
        self,
        query_vector: List[float],
        org_id: str,
        tender_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search within a single tender, scoped to the org for isolation.
        Returns list of {text, page, chunk_id, score}.
        """
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="org_id", match=MatchValue(value=str(org_id))),
                    FieldCondition(key="tender_id", match=MatchValue(value=str(tender_id))),
                ]
            ),
            limit=top_k,
        )

        return [
            {
                "text": hit.payload["text"],
                "page": hit.payload.get("page", 1),
                "chunk_id": hit.payload.get("chunk_id"),
                "score": hit.score,
            }
            for hit in results
        ]

    def delete_tender(self, org_id: str, tender_id: str):
        """Remove all vectors for a tender (e.g. on tender deletion)."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[
                    FieldCondition(key="org_id", match=MatchValue(value=str(org_id))),
                    FieldCondition(key="tender_id", match=MatchValue(value=str(tender_id))),
                ]
            ),
        )
        logger.info(f"Deleted vectors for tender {tender_id}")


vector_store = VectorStore()
