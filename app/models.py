"""
SQLAlchemy Database Models
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
import enum


class ToolType(str, enum.Enum):
    """Tool type enumeration"""
    FUNCTION = "function"  # @tool decorated function
    CLASS = "class"  # BaseTool subclass


class ToolStatus(str, enum.Enum):
    """Tool status enumeration"""
    PENDING = "pending"  # Pending validation
    VALID = "valid"  # Validated successfully
    INVALID = "invalid"  # Validation failed
    DISABLED = "disabled"  # Manually disabled


class Tool(Base):
    """Tool model for storing uploaded tools"""
    __tablename__ = "tools"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Tool metadata
    tool_type = Column(Enum(ToolType), nullable=False)
    status = Column(Enum(ToolStatus), default=ToolStatus.PENDING)
    
    # Source code
    source_code = Column(Text, nullable=False)
    
    # Validation info
    validation_message = Column(Text, nullable=True)
    
    # Tool schema (for MCP)
    input_schema = Column(JSONB, nullable=True)
    
    # Uploader info (simple username for internal use)
    uploader = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Usage statistics
    call_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<Tool {self.name}>"


class ToolCallLog(Base):
    """Log for tool calls"""
    __tablename__ = "tool_call_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, index=True, nullable=False)
    tool_name = Column(String(255), nullable=False)
    
    # Call info
    caller = Column(String(100), nullable=True)
    input_params = Column(JSONB, nullable=True)
    output_result = Column(Text, nullable=True)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    called_at = Column(DateTime, default=datetime.utcnow)
    execution_time_ms = Column(Integer, nullable=True)
