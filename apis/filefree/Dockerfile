# Wave K3: FileFree's Dockerfile now expects to be built from the REPO ROOT
# so it can COPY the shared `packages/python/data-engine` package and the
# canonical `packages/data/src` reference data into the image. Production
# (Render) does not use this Dockerfile — it uses `runtime: python` with a
# repo-root checkout (see render.yaml). This Dockerfile is for local Docker
# experimentation and should be invoked from the repo root:
#
#   docker build -f apis/filefree/Dockerfile -t filefree-api .

FROM python:3.11.9-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy the shared data-engine source first so the editable install in
# requirements.txt can resolve it via ../../packages/python/data-engine.
COPY packages/python/data-engine /build/packages/python/data-engine

COPY apis/filefree/requirements.txt /build/apis/filefree/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /build/apis/filefree/requirements.txt

FROM python:3.11.9-slim
WORKDIR /app
ENV TZ=UTC
RUN adduser --disabled-password --no-create-home appuser
COPY --from=builder /install /usr/local

# FileFree application code lives at /app (so `app.main:app` resolves).
COPY apis/filefree /app

# Canonical reference data + the editable data-engine source so the loader
# can find them at runtime. PAPERWORK_DATA_DIR overrides the auto-walk.
COPY packages/data/src /app/packages/data/src
COPY packages/python/data-engine /app/packages/python/data-engine
ENV PAPERWORK_DATA_DIR=/app/packages/data/src

RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1
CMD ["sh", "-c", "exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
