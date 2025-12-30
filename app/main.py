"""
Tools Platform - FastAPI Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.api import tools, mcp
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🚀 Starting Tools Platform...")
    init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("👋 Shutting down Tools Platform...")


app = FastAPI(
    title="LangChain Tools Platform",
    description="""
    一个用于管理和共享 LangChain 工具的平台。
    
    ## 功能
    
    * **工具管理** - 上传、验证、编辑和删除工具
    * **MCP 服务** - 通过 MCP 协议暴露工具供 AI 调用
    * **自动验证** - 自动检查上传的代码是否符合 LangChain 工具规范
    
    ## 支持的工具类型
    
    1. `@tool` 装饰器定义的函数
    2. 继承 `BaseTool` 的类
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tools.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "LangChain Tools Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "api": {
            "tools": "/api/tools",
            "mcp": "/api/mcp"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
