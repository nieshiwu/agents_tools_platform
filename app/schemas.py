"""
Pydantic Schemas for API request/response
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.models import ToolType, ToolStatus


# Tool Schemas
class ToolCreate(BaseModel):
    """Schema for creating a new tool"""
    name: str = Field(..., min_length=1, max_length=255, description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    source_code: str = Field(..., description="Python source code of the tool")
    uploader: Optional[str] = Field(None, max_length=100, description="Uploader username")


class ToolUpdate(BaseModel):
    """Schema for updating a tool"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_code: Optional[str] = None


class ToolResponse(BaseModel):
    """Schema for tool response"""
    id: int
    name: str
    description: Optional[str]
    tool_type: ToolType
    status: ToolStatus
    source_code: str
    validation_message: Optional[str]
    input_schema: Optional[Dict[str, Any]]
    uploader: Optional[str]
    created_at: datetime
    updated_at: datetime
    call_count: int
    
    class Config:
        from_attributes = True


class ToolListResponse(BaseModel):
    """Schema for tool list response"""
    id: int
    name: str
    description: Optional[str]
    tool_type: ToolType
    status: ToolStatus
    uploader: Optional[str]
    created_at: datetime
    call_count: int
    
    class Config:
        from_attributes = True


# Validation Schemas
class ValidationResult(BaseModel):
    """Schema for validation result"""
    is_valid: bool
    tool_type: Optional[ToolType] = None
    tool_name: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    suggestions: List[str] = []


# MCP Schemas
class MCPToolInfo(BaseModel):
    """Schema for MCP tool info"""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPToolCallRequest(BaseModel):
    """Schema for MCP tool call request"""
    tool_name: str
    arguments: Dict[str, Any] = {}
    caller: Optional[str] = None


class MCPToolCallResponse(BaseModel):
    """Schema for MCP tool call response"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None


# Statistics Schemas
class ToolStatistics(BaseModel):
    """Schema for tool statistics"""
    total_tools: int
    valid_tools: int
    invalid_tools: int
    pending_tools: int
    total_calls: int


class ToolCallLogResponse(BaseModel):
    """Schema for tool call log"""
    id: int
    tool_name: str
    caller: Optional[str]
    success: bool
    error_message: Optional[str]
    called_at: datetime
    execution_time_ms: Optional[int]
    
    class Config:
        from_attributes = True
