"""
Connect job status store using Redis.

Replaces in-memory JOBS dict for production: connect job status must persist
across multiple uvicorn workers / replicas. Used by TastyTrade and IBKR connect flows.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


def _get_redis():
    """Lazy Redis client. Uses REDIS_URL or CELERY_BROKER_URL fallback."""
    import redis
    url = getattr(settings, "REDIS_URL", None) or getattr(
        settings, "CELERY_BROKER_URL", None
    ) or "redis://:redispassword@redis:6379/0"
    return redis.from_url(url, decode_responses=True)


_CONNECT_JOB_PREFIX = "connect_job:"
_DEFAULT_TTL_SECONDS = 600


class ConnectJobStore:
    """
    Redis-backed store for connect job status.
    Key: connect_job:{job_id}, Value: JSON dict, TTL: 600s.
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._redis = None

    def _client(self):
        if self._redis is None:
            self._redis = _get_redis()
        return self._redis

    def _key(self, job_id: str) -> str:
        return f"{_CONNECT_JOB_PREFIX}{job_id}"

    def set(self, job_id: str, data: Dict[str, Any]) -> None:
        """Store job status. Data typically: state, error?, started_at, finished_at?, broker?."""
        key = self._key(job_id)
        payload = json.dumps(data)
        try:
            self._client().setex(key, self.ttl_seconds, payload)
        except Exception:
            logger.warning("ConnectJobStore.set failed for job %s", job_id, exc_info=True)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job status. Returns None if not found or expired."""
        key = self._key(job_id)
        try:
            raw = self._client().get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            logger.warning("ConnectJobStore.get failed for job %s", job_id, exc_info=True)
        return None


connect_job_store = ConnectJobStore()
