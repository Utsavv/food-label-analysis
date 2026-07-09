FROM python:3.11-slim

WORKDIR /srv/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY seed ./seed

RUN pip install --no-cache-dir .

EXPOSE 8000

# Migrations + demo seed run in docker-compose's command; default is just the API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
