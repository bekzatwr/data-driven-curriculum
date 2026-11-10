ARG APP_TARGET=backend
FROM node:22-bookworm-slim AS frontend-build
ARG FRONTEND_DIR=web
ARG VITE_API_BASE_URL=
WORKDIR /build
COPY ${FRONTEND_DIR}/package.json ${FRONTEND_DIR}/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ${FRONTEND_DIR}/ ./
RUN VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run build

FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 READ_ONLY_DEMO=true DATABASE_PATH=/app/data/curriculum.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home appuser
COPY backend ./backend
COPY planner ./planner
COPY deploy/run_server.py ./deploy/run_server.py
COPY deploy/seed_demo_report.py ./deploy/seed_demo_report.py
COPY analytics ./analytics
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/health', timeout=4)"
CMD ["python", "deploy/run_server.py"]

FROM backend AS fullstack
COPY --from=frontend-build --chown=appuser:appuser /build/dist /app/web
ENV WEB_DIST_DIR=/app/web
RUN test -f /app/web/index.html

# Default builds remain backend-only while Damir's source is not published.
FROM ${APP_TARGET} AS final
