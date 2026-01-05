FROM docker.1ms.run/library/python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    # 安装LibreOffice完整套件（核心）
    libreoffice \
    # LibreOffice在无头环境（容器无桌面）运行所需的额外依赖（slim镜像缺失）
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Copy application code
COPY . .

# Expose ports
EXPOSE 8000 8501

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
