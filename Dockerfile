FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    ORIGIN_WEB_DATA_DIR=/data \
    ORIGIN_WEB_HOST=0.0.0.0 \
    ORIGIN_WEB_PORT=8080

RUN addgroup --system --gid 10001 origin \
    && adduser --system --uid 10001 --ingroup origin --home /app origin
WORKDIR /app

COPY pyproject.toml LICENSE README.md ./
COPY origin ./origin
COPY origin_web ./origin_web
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /data /backup /restore \
    && chown origin:origin /data /backup /restore \
    && chown root:root /app && chmod 0755 /app
USER origin
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=2).read()"

CMD ["python", "-m", "origin_web", "api"]
