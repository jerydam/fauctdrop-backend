FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Force Playwright to look for browsers in a specific location
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/local/bin/ms-playwright

WORKDIR /app

# Create session data folder with correct permissions
USER root
RUN mkdir -p /app/bot_browser_data && chmod -R 777 /app/bot_browser_data

# Install system dependencies manually (Fixed for Debian Slim)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libxfixes3 \
    libx11-6 \
    libxext6 \
    fonts-liberation \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Now install playwright and chromium
RUN pip install playwright
RUN playwright install chromium
# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Use a shell string for the CMD to ensure PORT environment variable is expanded correctly
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT}