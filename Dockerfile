FROM python:3.12-slim

WORKDIR /denaro

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DENARO_HOME=/denaro
ENV PYTHONPATH=/denaro

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "from core.observability import Observable; import requests; r=requests.get('http://localhost:8909/health'); assert r.status_code==200, 'unhealthy'"

CMD ["python", "-u", "consolidation_bot.py"]
