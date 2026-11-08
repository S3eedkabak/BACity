FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV CRAWLER_STATE_PATH=/data/state.db
VOLUME ["/data"]
CMD ["python", "-m", "crawler.worker"]
