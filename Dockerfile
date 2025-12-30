FROM docker.1ms.run/library/python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Copy application code
COPY . .

# Expose ports
EXPOSE 7000 8501

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]
