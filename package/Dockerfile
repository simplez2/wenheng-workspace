FROM node:20-alpine AS frontend

WORKDIR /build

COPY package/frontend/package*.json ./
RUN npm ci --ignore-scripts

COPY package/frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-droid-fallback \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

COPY package/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY package/backend ./backend
COPY package/main.py ./main.py
COPY package/docker/entrypoint.sh /usr/local/bin/wenheng-entrypoint
COPY --from=frontend /build/dist ./static
COPY LICENSE ./LICENSE

RUN chmod 755 /usr/local/bin/wenheng-entrypoint \
    && mkdir -p /data \
    && chown -R app:app /app /data

USER app

EXPOSE 9800

ENTRYPOINT ["/usr/local/bin/wenheng-entrypoint"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9800", "--proxy-headers", "--forwarded-allow-ips", "*"]
