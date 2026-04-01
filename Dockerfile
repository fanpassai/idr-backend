FROM python:3.11-slim

# Force Python stdout/stderr to flush immediately — required for Railway logs
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies for BeautifulSoup/requests
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY . .

# Expose port
EXPOSE 8080

# Start gunicorn
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60
