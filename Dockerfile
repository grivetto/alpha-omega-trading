FROM python:3.12-slim

LABEL maintainer="Sergio Grivetto"
LABEL description="Denaro Kraken Grid Trading Bot v2"

WORKDIR /denaro

# Install build deps for websockets (pure Python, no C deps)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/denaro
ENV DENARO_HOME=/denaro

# Health check via internal HTTP endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8909/health'); assert r.status == 200, 'unhealthy'"

CMD ["python", "-u", "main.py"]
