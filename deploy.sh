#!/bin/bash
# Tools Platform 部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

echo "🚀 开始部署 Tools Platform..."

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"

# 创建必要目录
mkdir -p tools_storage
echo -e "${GREEN}✓ 创建存储目录${NC}"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ 未找到 .env 文件，创建默认配置...${NC}"
    cat > .env << 'EOF'
# 数据库配置
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tools_platform

# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# 其他配置 (可选)
# OPENAI_API_KEY=your_key
# DASHSCOPE_API_KEY=your_key
EOF
    echo -e "${GREEN}✓ 已创建默认 .env 文件，请根据需要修改${NC}"
fi

# 选择部署模式
echo ""
echo "请选择部署模式:"
echo "  1) 完整部署 (包含 PostgreSQL 容器)"
echo "  2) 仅应用 (连接外部 PostgreSQL)"
read -p "请输入选择 [1/2]: " mode

if [ "$mode" = "2" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
    echo -e "${YELLOW}⚠ 请确保已配置正确的 DATABASE_URL 环境变量${NC}"
else
    COMPOSE_FILE="docker-compose.yml"
fi

# 停止旧容器
echo "停止旧容器..."
docker-compose -f $COMPOSE_FILE down 2>/dev/null || true

# 构建并启动
echo "构建镜像..."
docker-compose -f $COMPOSE_FILE build

echo "启动服务..."
docker-compose -f $COMPOSE_FILE up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 初始化数据库
echo "初始化数据库..."
docker exec tools_platform_api python -c "
from app.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('数据库表创建/更新完成！')
" || echo "数据库初始化跳过（可能已存在）"

# 显示状态
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "服务地址:"
echo "  - API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - Web 界面: http://localhost:8501"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose -f $COMPOSE_FILE logs -f"
echo "  停止服务: docker-compose -f $COMPOSE_FILE down"
echo "  重启服务: docker-compose -f $COMPOSE_FILE restart"
echo ""

# 显示容器状态
docker-compose -f $COMPOSE_FILE ps
