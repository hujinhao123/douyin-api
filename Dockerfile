# <PRIVATE_ACCOUNT_NUMBER_b90765981cdba8db> local API.
#
# The base image ships Chromium + all its shared libraries, which this service
# needs at runtime: signing and requests both go through a real page.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DOUYIN_API_DATA=/data \
    DOUYIN_HOST=0.0.0.0 \
    DOUYIN_PORT=8787 \
    DOUYIN_ALLOW_LAN=true \
    DOUYIN_HEADLESS=true

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY pyproject.toml README.md ./

ENV PYTHONPATH=/app/src

# Session state and the persistent browser profile live on a volume so a
# container restart does not force a new QR scan.
VOLUME ["/data"]

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "douyin_api.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8787"]
