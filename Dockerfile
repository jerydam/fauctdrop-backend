# Use Python 3.10 slim base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render requires this to be 10000 for free tier)
EXPOSE 10000

# Set environment variable for port
ENV PORT=10000

# Run Uvicorn server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "10000"]