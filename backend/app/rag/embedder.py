"""
Embedding generation with batching, retry, and chunking.
"""
import logging
from typing import List, Dict, Any
from app.rag.llm_client import ai_client
from app.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Generates embeddings for text chunks using the configured AI provider."""

    def __init__(self):
        self.batch_size = 100 if (settings.AI_PROVIDER or "").lower() != "gemini" else 10

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of strings with retry on rate limits."""
        if not texts:
            return []

        return ai_client.embed_batch(texts)

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Embed a list of chunk dicts. Each chunk must have a 'text' key.
        Returns the same chunks enriched with a 'vector' key.
        Processes in batches to respect API limits.
        """
        results: List[Dict[str, Any]] = []

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            texts = [c["text"] for c in batch]
            vectors = self.embed_batch(texts)

            for chunk, vector in zip(batch, vectors):
                enriched = dict(chunk)
                enriched["vector"] = vector
                results.append(enriched)

            logger.info(f"Embedded {min(i + self.batch_size, len(chunks))}/{len(chunks)} chunks")

        return results


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
    page_map: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks (~chunk_size words each).

    Args:
        text: Full document text
        chunk_size: Target words per chunk
        overlap: Words of overlap between adjacent chunks
        page_map: Optional list of {page_num, text} to track page numbers

    Returns:
        List of {chunk_id, text, page, start_word, end_word}
    """
    words = text.split()
    chunks = []
    chunk_index = 0
    start = 0

    # Build a word-position -> page lookup if page_map provided
    word_to_page = {}
    if page_map:
        word_pos = 0
        for page in page_map:
            page_words = page["text"].split()
            for _ in page_words:
                word_to_page[word_pos] = page["page_num"]
                word_pos += 1

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text_str = " ".join(chunk_words)

        page = word_to_page.get(start, 1) if word_to_page else 1

        chunks.append({
            "chunk_id": f"chunk_{chunk_index}",
            "text": chunk_text_str,
            "page": page,
            "start_word": start,
            "end_word": end,
        })

        chunk_index += 1
        start += chunk_size - overlap  # Slide window with overlap

    logger.info(f"Created {len(chunks)} chunks from {len(words)} words")
    return chunks


embedder = Embedder()
