FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LOG_DIR=/app/log \
    LOG_LEVEL=INFO

RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY config/ /app/config/

RUN pip install --no-cache-dir .

RUN mkdir -p /app/log && \
    useradd -m tradeuser && \
    chown -R tradeuser:tradeuser /app
USER tradeuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["crypto-bot"]
