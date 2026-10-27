FROM node:22-alpine AS frontend
ARG NPM_REGISTRY=
WORKDIR /src/app/dashboard
COPY app/dashboard/package.json ./
RUN npm config set fetch-retries 8 && npm config set fetch-timeout 300000 \
 && npm config set fetch-retry-maxtimeout 300000 \
 && if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
 && npm install --no-audit --no-fund
COPY app/dashboard/ ./
RUN npm run build

FROM python:3.12-slim
ARG PIP_INDEX_URL=
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
WORKDIR /app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY cli ./cli
COPY tests ./tests
RUN if [ -z "$PIP_INDEX_URL" ]; then unset PIP_INDEX_URL; fi; pip install --no-cache-dir .
COPY --from=frontend /src/app/dashboard/dist ./app/dashboard/dist
COPY docker-entrypoint.sh ./
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh && mkdir -p /app/data
EXPOSE 8000
CMD ["./docker-entrypoint.sh"]
