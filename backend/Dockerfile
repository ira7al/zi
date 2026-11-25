FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version | head -1 && ffprobe -version | head -1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
COPY connectors ./connectors
COPY entrypoint.sh ./entrypoint.sh
# /app/data holds the SQLite DB and generated audio (mount a volume here). The entrypoint starts as root only to
# fix volume ownership, then runs uvicorn as the unprivileged user (uid 10001).
RUN useradd --create-home --uid 10001 app && mkdir -p /app/data && chmod +x entrypoint.sh && chown -R app:app /app
ENV DB_PATH=/app/data/zi.db WORK_DIR=/app/data/work
VOLUME /app/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/api/health'%os.environ.get('PORT','8000'),timeout=4)"
ENTRYPOINT ["/app/entrypoint.sh"]
