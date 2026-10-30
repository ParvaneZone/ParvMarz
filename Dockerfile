# syntax=docker/dockerfile:1

# ---- frontend: depends only on package.json / package-lock.json until the build step ----
FROM node:22-alpine AS frontend
ARG NPM_REGISTRY=
WORKDIR /src/app/dashboard
COPY app/dashboard/package.json app/dashboard/package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm \
    npm config set fetch-retries 8 && npm config set fetch-timeout 300000 \
 && npm config set fetch-retry-maxtimeout 300000 \
 && if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
 && if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY app/dashboard/ ./
RUN npm run build

# ---- reqs: extract dependency list so the pip layer only changes when dependencies change ----
FROM python:3.12-slim AS reqs
WORKDIR /r
COPY pyproject.toml ./
RUN python -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'));print('\n'.join(d['build-system']['requires']+d['project']['dependencies']))" > requirements.txt

# ---- final image ----
FROM python:3.12-slim
ARG PIP_INDEX_URL=
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10
WORKDIR /app
COPY --from=reqs /r/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ -z "$PIP_INDEX_URL" ]; then unset PIP_INDEX_URL; fi; \
    pip install -r /tmp/requirements.txt
COPY docker-entrypoint.sh ./
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh && mkdir -p /app/data
COPY --from=frontend /src/app/dashboard/dist ./app/dashboard/dist
COPY pyproject.toml alembic.ini ./
COPY app ./app
# only the built dashboard ships: no frontend sources/configs inside the image
RUN rm -rf app/dashboard/src app/dashboard/package.json app/dashboard/package-lock.json app/dashboard/tsconfig.json app/dashboard/vite.config.ts app/dashboard/index.html
COPY cli ./cli
RUN pip install --no-cache-dir --no-deps --no-build-isolation .
EXPOSE 8000 8001
CMD ["./docker-entrypoint.sh"]
