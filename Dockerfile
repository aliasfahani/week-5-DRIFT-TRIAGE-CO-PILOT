FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
COPY services /app/services
COPY dashboard /app/dashboard
COPY prompts /app/prompts
COPY contracts /app/contracts
COPY artifacts /app/artifacts
COPY runtime /app/runtime

RUN python -m pip install --upgrade pip && \
    python -m pip install .
