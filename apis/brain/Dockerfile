FROM python:3.11.9-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY apis/brain/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11.9-slim
WORKDIR /app
ENV TZ=UTC
RUN adduser --disabled-password --no-create-home appuser
COPY --from=builder /install /usr/local

# Brain service code.
COPY apis/brain/ /app/

# Track F / H12: bundle persona .mdc files into the image so
# _load_persona_instructions doesn't need a live GitHub fetch on every cold
# start. app/services/agent.py reads /app/cursor-rules/<persona>.mdc first
# and only falls back to read_github_file when the local copy is missing.
COPY .cursor/rules/ /app/cursor-rules/

# Brain reads two pieces of monorepo data at runtime:
#   - docs/.doc-drift-baseline.json  (qa_weekly_report scheduler)
#   - apps/studio/src/data/workstreams.json  (workstreams_loader / dispatcher)
#   - apps/studio/src/data/tracker-index.json  (cfo_friday_digest)
# Without these, schedulers either crash at import (parents[4] IndexError) or
# silently fall back to no-op. Bundle them in. The repo's path layout is
# preserved so REPO_ROOT-style lookups still work.
COPY docs/.doc-drift-baseline.json /app/docs/.doc-drift-baseline.json
COPY apps/studio/src/data/workstreams.json /app/apps/studio/src/data/workstreams.json
COPY apps/studio/src/data/tracker-index.json /app/apps/studio/src/data/tracker-index.json

# WS-37: Clerk ↔ Cloudflare DNS check-only job (APScheduler) shells out to this script.
COPY scripts/reconcile_clerk_dns.py /app/scripts/reconcile_clerk_dns.py

RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1
CMD ["sh", "-c", "exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
