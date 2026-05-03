FROM python:3.11-slim

# Set working directory
WORKDIR /app
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Build context is the monorepo root (see render.yaml). Install Python deps +
# paperwork-auth (Clerk JWT) from packages/auth-clerk + the shared mcp-server
# workspace package (Wave K2 -- packages/python/mcp-server).
COPY apis/axiomfolio/requirements.txt .
COPY packages/auth-clerk/src/python /tmp/paperwork-auth
COPY packages/python/mcp-server /tmp/mcp-server
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "/tmp/paperwork-auth[fastapi]" \
    && pip install --no-cache-dir /tmp/mcp-server

# Application code: WORKDIR /app + COPY app/ ./app/ yields /app/app/ for `app.api.main:app`.
COPY apis/axiomfolio/app/ ./app/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
# Two uvicorn workers on Standard (2 GiB). Heavy synchronous work was moved out of
# the web process in commit 291f2e0 (build_dashboard moved to Celery). API peak RAM
# observed at ~255 MiB / 2 GiB, so two workers easily fit and double request capacity.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-keep-alive", "30"]
