FROM python:3.10.13-slim AS build

ENV POETRY_VERSION=1.7.1
WORKDIR /usr/src/app

ENV PYTHONPATH /usr/src/app

COPY pyproject.toml poetry.lock ./
RUN apt-get update --fix-missing && \
    apt-get install --no-install-recommends -y gcc libc-dev libpq-dev && \
    pip install "poetry==$POETRY_VERSION" && \
    poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

COPY . .

