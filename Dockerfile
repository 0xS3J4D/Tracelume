# Tracelume application image: API + worker + bundled UI.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml ./backend/
COPY backend/tracelume ./backend/tracelume
RUN pip install --no-cache-dir ./backend
COPY plugins ./plugins
COPY --from=ui /ui/dist /usr/local/lib/python3.12/site-packages/tracelume/static
RUN useradd -r -u 10001 tracelume && mkdir -p /data/evidence /data/workspace /import && chown -R tracelume /data
USER tracelume
ENV TRACELUME_PLUGINS_DIR=/app/plugins \
    TRACELUME_EVIDENCE_DIR=/data/evidence \
    TRACELUME_WORKSPACE_DIR=/data/workspace \
    TRACELUME_IMPORT_DIR=/import
EXPOSE 8000
CMD ["uvicorn", "tracelume.main:app", "--host", "0.0.0.0", "--port", "8000"]
