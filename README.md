# LangChain 工具平台

一个用于管理和共享 LangChain 工具的内部平台，支持通过 MCP (Model Context Protocol) 协议供 AI 调用。类似 ModelScope 的 MCP 广场。

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.29+-red.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)

## 功能特性

- 📤 **工具上传** - 上传 LangChain 工具代码，支持 @tool 装饰器和 BaseTool 类
- ✅ **自动验证** - 自动检查代码是否符合 LangChain 工具规范，不符合则给出修改建议
- 🔧 **工具管理** - 查看、编辑、删除、启用/禁用工具
- 🌐 **MCP 服务** - 统一的 MCP 协议接口，供 AI 助手调用工具
- 📊 **统计分析** - 查看工具使用统计和调用记录
- 🖥️ **Web 界面** - 基于 Streamlit 的友好管理界面

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI |
前端 | React + Ant Design (新) / Streamlit (旧) |
...existing code...
访问入口：
- React 前端（新）：http://localhost:1234
- Streamlit 前端（旧）：http://localhost:8501
- API 文档：http://localhost:6666/docs
- MCP 服务：http://localhost:6666/api/mcp
### 1. @tool 装饰器函数

```python
from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
    
    Returns:
        计算结果
    """
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"
```

### 2. BaseTool 子类

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class WeatherInput(BaseModel):
    """天气查询输入参数"""
    city: str = Field(description="城市名称")

class WeatherTool(BaseTool):
    """天气查询工具"""
    name: str = "weather"
    description: str = "查询指定城市的天气信息"
    args_schema: Type[BaseModel] = WeatherInput
    
    def _run(self, city: str) -> str:
        """执行天气查询"""
        return f"{city}的天气: 晴天，温度25°C"
```

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 克隆项目
cd tools_platform

# 启动所有服务
docker-compose up -d

# 访问
# - Web 界面: http://localhost:8501
# - API 文档: http://localhost:7000/docs
# - MCP 服务: http://localhost:7000/api/mcp
```

### 方式二：本地开发

#### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置数据库

确保 PostgreSQL 已安装并运行，然后创建数据库：

```sql
CREATE DATABASE tools_platform;
```

修改 `.env` 文件中的数据库连接：

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tools_platform
```

#### 3. 启动服务

**方法一：分别启动**

```bash
# 终端1：启动后端 API
uvicorn app.main:app --reload --host 0.0.0.0 --port 7000

# 终端2：启动 React 前端（推荐）
cd web-react
npm install
npm run dev

# 或启动 Streamlit 前端（旧版）
streamlit run web/app.py
```

**方法二：使用启动脚本**

```bash
python run.py
```

#### 4. 访问服务

- **React 前端** (新): http://localhost:3000
- **Streamlit 前端** (旧): http://localhost:8501
- **API 文档**: http://localhost:7000/docs
- **MCP 服务**: http://localhost:7000/api/mcp

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:7000/docs
- ReDoc: http://localhost:7000/redoc

### 主要 API 端点

#### 工具管理

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/tools/` | 获取工具列表 |
| POST | `/api/tools/` | 创建新工具 |
| GET | `/api/tools/{id}` | 获取工具详情 |
| PUT | `/api/tools/{id}` | 更新工具 |
| DELETE | `/api/tools/{id}` | 删除工具 |
| POST | `/api/tools/validate` | 验证代码 |

#### MCP 服务

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/api/mcp/tools` | 获取可用工具列表 |
| POST | `/api/mcp/call` | 调用工具 |
| GET | `/api/mcp/protocol/info` | 获取 MCP 服务信息 |
| POST | `/api/mcp/protocol/tools/list` | MCP 标准协议 - 列出工具 |
| POST | `/api/mcp/protocol/tools/call` | MCP 标准协议 - 调用工具 |

## MCP 集成

### 在 Claude Desktop 中使用

在 Claude Desktop 的配置文件中添加：

```json
{
  "mcpServers": {
    "langchain-tools": {
      "command": "curl",
      "args": ["-X", "POST", "http://localhost:7000/api/mcp/protocol/tools/list"]
    }
  }
}
```

### 在代码中调用

```python
import requests

# 列出所有工具
tools = requests.get("http://localhost:7000/api/mcp/tools").json()

# 调用工具
result = requests.post(
    "http://localhost:7000/api/mcp/call",
    json={
        "tool_name": "calculator",
        "arguments": {"expression": "2 + 3 * 4"},
        "caller": "my_app"
    }
).json()

print(result["result"])
```

## 项目结构

```
tools_platform/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── database.py          # 数据库连接
│   ├── models.py            # SQLAlchemy 模型
│   ├── schemas.py           # Pydantic 模型
│   ├── api/
│   │   ├── __init__.py
│   │   ├── tools.py         # 工具 API
│   │   └── mcp.py           # MCP 服务 API
│   └── services/
│       ├── __init__.py
│       ├── tool_validator.py # 工具验证服务
│       └── tool_executor.py  # 工具执行服务
├── web/
│   └── app.py               # Streamlit 前端
├── docs/
│   └── 用户指南.md           # 用户使用文档
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── run.py                   # 启动脚本
├── .env                     # 环境配置
└── README.md
```

## 文档

- 📖 [用户指南](docs/用户指南.md) - 详细的工具上传和使用说明
- 📚 API 文档 - 启动服务后访问 http://localhost:7000/docs
- 📋 工具规范 - Web 界面「📚 规范文档」页面

## 开发说明

### 添加新的工具类型支持

修改 `app/services/tool_validator.py` 中的验证逻辑。

### 自定义前端样式

修改 `web/app.py` 中的 CSS 样式。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| DATABASE_URL | 数据库连接字符串 | postgresql://postgres:postgres@localhost:5432/tools_platform |
| API_HOST | API 监听地址 | 0.0.0.0 |
| API_PORT | API 端口 | 7000 |
| MCP_HOST | MCP 服务地址 | 0.0.0.0 |
| MCP_PORT | MCP 服务端口 | 8001 |
| STREAMLIT_PORT | 前端端口 | 8501 |

## 常见问题

### 数据库连接失败

确保 PostgreSQL 正在运行，并且已创建 `tools_platform` 数据库：

```sql
CREATE DATABASE tools_platform;
```

### 工具验证失败

请参考 [用户指南](docs/用户指南.md) 中的工具规范部分，确保代码符合 LangChain 工具要求。

## License

MIT License
