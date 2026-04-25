"""Embedding service — generate vector embeddings via OpenAI.

D5: Hybrid retrieval requires vector similarity alongside FTS.
Uses text-embedding-3-small (~$0.00002 per 1K tokens, 1536 dimensions).

medallion: ops
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def close_client() -> None:
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_INPUT_TOKENS = 8191


async def embed_text(text: str) -> list[float] | None:
    """Generate embedding for text via OpenAI API.

    Returns None if API key not configured or call fails.
    Cost: ~$0.00002 per 1K tokens.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.debug("OPENAI_API_KEY not set, skipping embedding generation")
        return None

    truncated = text[:32000]

    try:
        client = _get_http_client()
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": truncated,
            },
        )
        response.raise_for_status()
        data = response.json()
        embedding = data["data"][0]["embedding"]
        logger.debug("Generated embedding (%d dimensions)", len(embedding))
        return embedding
    except httpx.HTTPStatusError as e:
        logger.warning("OpenAI embedding API error: %s", e.response.status_code)
        return None
    except Exception:
        logger.warning("Embedding generation failed", exc_info=True)
        return None


async def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """Generate embeddings for multiple texts.

    OpenAI supports batching up to 2048 inputs.
    Returns list of embeddings (None for any that failed).
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return [None] * len(texts)

    if not texts:
        return []

    truncated = [t[:32000] for t in texts]

    try:
        client = _get_http_client()
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": EMBEDDING_MODEL,
                "input": truncated,
            },
        )
        response.raise_for_status()
        data = response.json()

        embeddings: list[list[float] | None] = [None] * len(texts)
        for item in data["data"]:
            idx = item["index"]
            embeddings[idx] = item["embedding"]

        logger.info("Generated %d embeddings in batch", len(texts))
        return embeddings
    except Exception:
        logger.warning("Batch embedding generation failed", exc_info=True)
        return [None] * len(texts)
