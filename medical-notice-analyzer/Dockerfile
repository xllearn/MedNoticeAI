FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends antiword fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests
COPY prompts ./prompts
COPY scripts ./scripts
COPY dify-db-backups ./dify-db-backups
COPY dify-chatflow-medical-notice-report.yml ./dify-chatflow-medical-notice-report.yml
COPY dify-workflow-medical-notice-report.yml ./dify-workflow-medical-notice-report.yml
COPY workflow-v2-medical-notice-report.yml ./workflow-v2-medical-notice-report.yml
COPY README.md ./README.md
COPY NEXT_CHAT_HANDOFF.md ./NEXT_CHAT_HANDOFF.md

EXPOSE 8099
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099"]
