"""
MCP (Model Context Protocol) API Endpoints

Provides MCP-compatible endpoints for tool discovery and invocation.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
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
