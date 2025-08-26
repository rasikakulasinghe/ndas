# Multi-stage Dockerfile for NDAS with video processing capabilities

# Stage 1: Base image with system dependencies
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y \
    # Build dependencies
    gcc \
    g++ \
    python3-dev \
    pkg-config \
    # Media processing
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libavfilter-dev \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    # Database clients
    libpq-dev \
    # Utilities
    curl \
    wget \
    unzip \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Python dependencies
FROM base as dependencies

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Stage 3: Application
FROM dependencies as application

# Copy project files
COPY . .

# Create media directories
RUN mkdir -p media/videos media/videos/thumbnails media/videos/compressed \
    media/attachments media/profile_pictures

# Set permissions
RUN chmod +x manage.py

# Create non-root user for security
RUN groupadd -r django && useradd -r -g django django \
    && chown -R django:django /app
USER django

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command (can be overridden)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
