"""
MCP (Model Context Protocol) API Endpoints

Provides MCP-compatible endpoints for tool discovery and invocation.
"""
import os
import uuid
import hashlib
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.config import get_settings
from app.models import Tool, ToolStatus, ToolCallLog
from app.schemas import MCPToolInfo, MCPToolCallRequest, MCPToolCallResponse
from app.services.tool_executor import execute_tool

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools", response_model=List[MCPToolInfo])
def list_mcp_tools(db: Session = Depends(get_db)):
    """
    List all available tools in MCP format
    
    This endpoint returns tool information in a format compatible with
    Model Context Protocol clients.
    """
    tools = db.query(Tool).filter(Tool.status == ToolStatus.VALID).all()
    
    mcp_tools = []
    for tool in tools:
        input_schema = tool.input_schema or {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        mcp_tools.append(MCPToolInfo(
            name=tool.name,
            description=tool.description or f"Tool: {tool.name}",
            inputSchema=input_schema
        ))
    
    return mcp_tools


@router.get("/tools/{tool_name}", response_model=MCPToolInfo)
def get_mcp_tool(tool_name: str, db: Session = Depends(get_db)):
    """
    Get a specific tool's MCP information
    """
    tool = db.query(Tool).filter(
        Tool.name == tool_name,
        Tool.status == ToolStatus.VALID
    ).first()
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 不存在或未启用")
    
    input_schema = tool.input_schema or {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    return MCPToolInfo(
        name=tool.name,
        description=tool.description or f"Tool: {tool.name}",
        inputSchema=input_schema
    )


@router.post("/call", response_model=MCPToolCallResponse)
def call_tool(request: MCPToolCallRequest, db: Session = Depends(get_db)):
    """
    Call a tool with given arguments
    
    This is the main endpoint for MCP clients to invoke tools.
    """
    # Find the tool
    tool = db.query(Tool).filter(
        Tool.name == request.tool_name,
        Tool.status == ToolStatus.VALID
    ).first()
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具 '{request.tool_name}' 不存在或未启用")
    
    # Execute the tool
    success, result, error, execution_time = execute_tool(tool, request.arguments)
    
    # Log the call
    log = ToolCallLog(
        tool_id=tool.id,
        tool_name=tool.name,
        caller=request.caller,
        input_params=request.arguments,
        output_result=str(result) if result else None,
        success=success,
        error_message=error,
        execution_time_ms=execution_time
    )
    db.add(log)
    
    # Update call count
    tool.call_count += 1
    
    db.commit()
    
    return MCPToolCallResponse(
        success=success,
        result=result,
        error=error,
        execution_time_ms=execution_time
    )


@router.post("/tools/{tool_name}/call", response_model=MCPToolCallResponse)
def call_tool_by_name(
    tool_name: str,
    arguments: Dict[str, Any] = {},
    caller: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Alternative endpoint to call a tool by name in URL
    """
    request = MCPToolCallRequest(
        tool_name=tool_name,
        arguments=arguments,
        caller=caller
    )
    return call_tool(request, db)


# ============== MCP Protocol Standard Endpoints ==============

@router.get("/protocol/info")
def get_protocol_info():
    """
    Get MCP server information
    """
    return {
        "name": "LangChain Tools Platform",
        "version": "1.0.0",
        "protocol_version": "1.0",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        }
    }


@router.post("/protocol/tools/list")
def list_tools_protocol(db: Session = Depends(get_db)):
    """
    MCP Protocol standard endpoint for listing tools
    
    Returns tools in the standard MCP format.
    """
    tools = db.query(Tool).filter(Tool.status == ToolStatus.VALID).all()
    
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description or f"Tool: {tool.name}",
                "inputSchema": tool.input_schema or {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            for tool in tools
        ]
    }


@router.post("/protocol/tools/call")
def call_tool_protocol(
    request: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    MCP Protocol standard endpoint for calling tools
    
    Follows the MCP specification for tool invocation.
    Expects JSON body: {"name": "tool_name", "arguments": {...}}
    """
    name = request.get("name")
    arguments = request.get("arguments", {})
    
    tool = db.query(Tool).filter(
        Tool.name == name,
        Tool.status == ToolStatus.VALID
    ).first()
    
    if not tool:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": f"Tool '{name}' not found or not enabled"
                }
            ]
        }
    
    success, result, error, execution_time = execute_tool(tool, arguments)
    
    # Log the call
    log = ToolCallLog(
        tool_id=tool.id,
        tool_name=tool.name,
        input_params=arguments,
        output_result=str(result) if result else None,
        success=success,
        error_message=error,
        execution_time_ms=execution_time
    )
    db.add(log)
    tool.call_count += 1
    db.commit()
    
    if success:
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result)
                }
            ]
        }
    else:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": error or "Unknown error"
                }
            ]
        }


# ============== File Download Endpoints ==============

# 存储文件 token 与路径的映射（生产环境建议用 Redis）
_file_tokens: Dict[str, Dict[str, Any]] = {}


@router.post("/files/register")
def register_file_for_download(
    file_path: str = Body(..., embed=True),
    expires_in: int = Body(3600, embed=True)
):
    """
    注册一个服务器本地文件，生成可供远程下载的 token
    
    Args:
        file_path: 服务器上的文件绝对路径
        expires_in: token 有效期（秒），默认 3600
        
    Returns:
        包含下载 URL 的响应
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    
    # 生成唯一 token
    token = hashlib.md5(f"{file_path}{uuid.uuid4()}".encode()).hexdigest()
    
    # 存储映射
    _file_tokens[token] = {
        "path": file_path,
        "filename": os.path.basename(file_path),
        "created_at": datetime.now(),
        "expires_in": expires_in
    }
    
    settings = get_settings()
    base_url = f"http://{settings.api_host}:{settings.api_port}"
    if settings.api_host == "0.0.0.0":
        base_url = f"http://localhost:{settings.api_port}"
    
    return {
        "success": True,
        "token": token,
        "download_url": f"{base_url}/api/mcp/files/download/{token}",
        "filename": os.path.basename(file_path),
        "expires_in": expires_in
    }


@router.get("/files/download/{token}")
def download_file(token: str):
    """
    通过 token 下载文件
    
    Args:
        token: 文件访问 token
        
    Returns:
        文件内容
    """
    if token not in _file_tokens:
        raise HTTPException(status_code=404, detail="无效或已过期的下载链接")
    
    file_info = _file_tokens[token]
    file_path = file_info["path"]
    
    # 检查是否过期
    created_at = file_info["created_at"]
    expires_in = file_info["expires_in"]
    if (datetime.now() - created_at).total_seconds() > expires_in:
        del _file_tokens[token]
        raise HTTPException(status_code=410, detail="下载链接已过期")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件已被删除")
    
    return FileResponse(
        path=file_path,
        filename=file_info["filename"],
        media_type="application/octet-stream"
    )
