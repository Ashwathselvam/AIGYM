FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files first
COPY requirements-*.txt ./

# Install dependencies from specific requirements file
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy application code
COPY . .

# Default command (will be overridden by docker-compose)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"] 