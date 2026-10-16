FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/tmp/sway/quota.db
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.lock.txt ./backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY backend/app/ ./backend/app/
COPY --from=frontend /build/dist/ ./frontend/dist/
RUN useradd --create-home --uid 10001 sway
USER sway
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app.server:app --app-dir backend --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
