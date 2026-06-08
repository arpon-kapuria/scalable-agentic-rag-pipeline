FROM python:3.13-slim

WORKDIR /app

# System dependencies needed by asyncpg, greenlet, unstructured
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first — cached layer if requirements unchanged
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project — needed because imports reference
# services.api.app.*, libs.*, pipelines.* from project root
COPY . .

# Python path so 'from services.api.app...' imports resolve
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]