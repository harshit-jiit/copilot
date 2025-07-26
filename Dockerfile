FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*



RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml poetry.lock /app/
RUN poetry config virtualenvs.create false \
    && poetry install --no-root  --no-interaction --no-ansi

# Copy project code first (excluding entrypoint if needed)
COPY . /app/

# Then explicitly overwrite + fix entrypoint.sh
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Use entrypoint script if needed
# ENTRYPOINT ["/app/entrypoint.sh"]

# Main command
CMD ["gunicorn","--workers", "4","--worker-class", "gevent","--timeout", "120","--graceful-timeout", "60","--keep-alive", "5","--log-level", "debug","--access-logfile", "access.log","--error-logfile", "error.log",]
