FROM python:3.12-slim

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy video module and application code
COPY . video/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

# Default command runs API service; overridden by Cloud Run Job entrypoint
CMD ["sh", "-c", "uvicorn video.api.main:app --host 0.0.0.0 --port ${PORT}"]
