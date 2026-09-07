FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    curl \
    postgresql-client \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY . .

# Copy startup script and set permissions
COPY start.sh .
RUN chmod +x start.sh && chmod +x /app/start.sh

# Create necessary directories
RUN mkdir -p data/cameras outputs models logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Run the application
CMD ["./start.sh"]
