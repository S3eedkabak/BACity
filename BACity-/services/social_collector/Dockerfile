FROM mcr.microsoft.com/playwright/python:v1.64.1-noble
WORKDIR /runner
RUN pip install --no-cache-dir playwright==1.64.1 httpx==0.27.2 && useradd --create-home --uid 10001 collector
RUN mkdir -p app/social
COPY services/api/app/social/acquisition/ app/social/acquisition/
RUN touch app/__init__.py app/social/__init__.py && mkdir -p /var/lib/bacity-outbox && chown -R collector:collector /runner /var/lib/bacity-outbox
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV SOCIAL_OUTBOX_PATH=/var/lib/bacity-outbox/outbox.sqlite3
CMD ["python", "-m", "app.social.acquisition.runner"]
