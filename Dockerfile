FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/app/data/zi.db \
    WORK_DIR=/app/data/work

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core setpriv \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version | head -1 \
    && ffprobe -version | head -1

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/*.py ./
COPY backend/connectors ./connectors
COPY backend/entrypoint.sh ./entrypoint.sh
COPY index.html music-studio.css music-studio.js music-studio.html releases.js releases.html single-file-app.html ./

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

VOLUME /app/data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','8000'),timeout=4)"

ENTRYPOINT ["/app/entrypoint.sh"]
