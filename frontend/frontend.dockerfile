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

CMD ["streamlit", "run", "streamlit_app.py", "--server.address 0.0.0.0", "--server.port 8501"]

# Stage 2: Set up Nginx
FROM nginx:1.25.3

# Copy the Streamlit app from the first stage
COPY --from=build /usr/src/app /usr/share/nginx/html

# Copy the Nginx configuration file
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80