FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Databáze, stažená data, nahrané fotky – na serveru připojte trvalý disk do /data
ENV LF_DB_PATH=/data/leadfinder.sqlite
EXPOSE 8000
# Railway a podobné služby předávají port v proměnné PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
