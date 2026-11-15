# Production image for Render (or any Docker host): one container that serves
# the built React app and the FastAPI backend on the same port.
# Local development is unchanged: `make dev` or `docker compose up`.

# 1) Build the web app
FROM node:20-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2) Run the API and serve the built web app
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOMERANG_STATIC_DIR=/app/static \
    BOMERANG_DATA_DIR=/data
WORKDIR /app
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ ./
COPY --from=web /web/dist /app/static
# Render sets $PORT (default 10000). One worker on purpose: runs happen in
# background threads inside this process and SQLite is local.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
