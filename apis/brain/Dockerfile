FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Build with dockerContext: apis/brain (see render.yaml brain-api).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Venture docs (docs/*.md) are not in this context; seed ingestion skips missing paths.
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
