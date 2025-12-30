"""
Tools Platform Configuration
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/tools_platform"
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_public_url: Optional[str] = None  # 公开访问地址，如 http://192.168.0.197:8000
    
    # MCP Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    
    # Streamlit
    streamlit_port: int = 8501
    
    # Tool storage path
    tools_storage_path: str = "./tools_storage"
    
    # LLM / API Keys (optional)
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    deepseek_model_name: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 .env 中未定义的额外字段


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings"""
    return Settings()
