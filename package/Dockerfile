# syntax=docker/dockerfile:1

FROM node:20-alpine AS frontend

WORKDIR /build

COPY package/frontend/package*.json ./
RUN npm ci --ignore-scripts

COPY package/frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS python-deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN python -m venv "$VIRTUAL_ENV"

COPY package/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-compile -r /tmp/requirements.txt

FROM python:3.11-slim-bookworm

ARG BUILD_DATE="unknown"
ARG VCS_REF="unknown"

LABEL org.opencontainers.image.title="Wenheng Workspace" \
      org.opencontainers.image.description="Document optimization and formatting workspace" \
      org.opencontainers.image.source="https://github.com/simplez2/wenheng-workspace" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    MALLOC_ARENA_MAX=2 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    TMPDIR=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fontconfig fonts-droid-fallback \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=python-deps /opt/venv /opt/venv

COPY package/backend/app ./backend/app
COPY package/main.py ./main.py
COPY package/docker/entrypoint.sh /usr/local/bin/wenheng-entrypoint
COPY --from=frontend /build/dist ./static
COPY LICENSE ./LICENSE

RUN chmod 755 /usr/local/bin/wenheng-entrypoint \
    && mkdir -p /data /tmp/.cache \
    && chown -R app:app /app /data

USER app

EXPOSE 9800

ENTRYPOINT ["/usr/local/bin/wenheng-entrypoint"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9800", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-keep-alive", "75", "--limit-concurrency", "200"]
