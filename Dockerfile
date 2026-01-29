FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

USER root
RUN mkdir -p /app/bot_browser_data && chmod -R 777 /app/bot_browser_data
# Upgrade pip and install requirements
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium
# Copy project files
COPY . .

# Command to run the application
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-10000}