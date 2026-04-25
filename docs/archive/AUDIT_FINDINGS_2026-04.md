# Audit findings

Living notes from API / market-data audits. **Use one consistent figure for route-module scope:** there are **40** Python modules under `app/api/routes/` (including packages such as `market/` and `portfolio/`). Do not mix that count with older informal totals (e.g. “85+” or “93”) that referred to endpoints or lines—those are not comparable.

---

## Market universe API

`GET /api/v1/market-data/indices/constituents` takes query parameter **`index`** (e.g. `SP500`, `NASDAQ100`). The database column on `IndexConstituent` is named `index_name`; the **HTTP API** uses `index`, not `index_name`.

---

## Rate limiter (sync Celery paths)

`TokenBucketLimiter.acquire_sync` is thread-safe for concurrent workers using `threading.Lock` (`self._sync_lock`), separate from the async `asyncio.Lock` used by `acquire()`.

```python
def acquire_sync(self) -> None:
    """Blocking variant for sync code paths (Celery tasks).

    Thread-safe via threading.Lock for concurrent Celery workers.
    """
    while True:
        with self._sync_lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            wait_time = (1.0 - self._tokens) / self.rate
        time.sleep(min(wait_time, 2.0))
```

Source: `app/services/market/rate_limiter.py`.
