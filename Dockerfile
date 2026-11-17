# Cloud Run production image for the MOHANO FastAPI API.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system mohano && adduser --system --ingroup mohano mohano

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir . && chown -R mohano:mohano /app

USER mohano

# Cloud Run injects PORT. Keep the image usable locally with port 8080 too.
CMD ["/bin/sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
