FROM node:22-alpine AS frontend
WORKDIR /src/app/dashboard
COPY app/dashboard/package.json ./
RUN npm install
COPY app/dashboard/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY cli ./cli
COPY tests ./tests
RUN pip install --no-cache-dir .
COPY --from=frontend /src/app/dashboard/dist ./app/dashboard/dist
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["sh","-c","alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
