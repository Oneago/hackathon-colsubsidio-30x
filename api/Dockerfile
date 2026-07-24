# syntax=docker/dockerfile:1
# Multi-stage: builder (venv) → runtime (imagen final, no-root) → dev (hot reload).

# ── builder: instala dependencias en un venv aislado ─────────────────
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── runtime: imagen de producción, corre como usuario no-root ────────
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
# Usuario sin privilegios (la API no corre como root).
RUN useradd --create-home --uid 10001 appuser
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY . /app
# Volumen de audios propiedad del usuario de la app.
RUN mkdir -p /audio_store && chown -R appuser:appuser /app /audio_store
USER appuser
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── dev: reutiliza runtime; el código se monta desde el host (override) ─
FROM runtime AS dev
