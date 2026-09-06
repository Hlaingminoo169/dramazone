# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies into a separate layer for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Create non-root user for security.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source — .dockerignore ensures .env is excluded.
COPY app/ ./app/
COPY main.py .

# Ownership for non-root user.
RUN chown -R appuser:appgroup /app
USER appuser

# PORT is injected by the hosting platform (FastAPI Cloud, VPS, etc.)
# Default is 8000 for local Docker runs.
ENV PORT=8000

EXPOSE ${PORT}

# Use sh -c so $PORT is evaluated at runtime, not build time.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
