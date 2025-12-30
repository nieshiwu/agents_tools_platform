"""
Tools API Endpoints

Handles tool CRUD operations and validation.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Tool, ToolStatus, ToolCallLog
from app.schemas import (
    ToolCreate, ToolUpdate, ToolResponse, ToolListResponse,
    ValidationResult as ValidationResultSchema, ToolStatistics
)
from app.services.tool_validator import validate_tool, get_tool_spec
from app.services.tool_executor import reload_tool

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=List[ToolListResponse])
def list_tools(
    status: Optional[ToolStatus] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all tools with optional filtering
    """
    query = db.query(Tool)
    
    if status:
        query = query.filter(Tool.status == status)
    
    if search:
        query = query.filter(
            (Tool.name.ilike(f"%{search}%")) |
            (Tool.description.ilike(f"%{search}%"))
        )
    
    tools = query.order_by(Tool.created_at.desc()).offset(skip).limit(limit).all()
    return tools


@router.get("/statistics", response_model=ToolStatistics)
def get_statistics(db: Session = Depends(get_db)):
    """
    Get tool statistics
    """
    total = db.query(Tool).count()
    valid = db.query(Tool).filter(Tool.status == ToolStatus.VALID).count()
    invalid = db.query(Tool).filter(Tool.status == ToolStatus.INVALID).count()
    pending = db.query(Tool).filter(Tool.status == ToolStatus.PENDING).count()
    total_calls = db.query(func.sum(Tool.call_count)).scalar() or 0
    
    return ToolStatistics(
        total_tools=total,
        valid_tools=valid,
        invalid_tools=invalid,
        pending_tools=pending,
        total_calls=total_calls
    )


@router.get("/spec", response_model=dict)
def get_specification():
    """
    Get LangChain tool specification
    """
    return {"specification": get_tool_spec()}


@router.post("/validate", response_model=ValidationResultSchema)
def validate_code(source_code: str):
    """
    Validate source code without saving
    """
    result = validate_tool(source_code)
    return ValidationResultSchema(
        is_valid=result.is_valid,
        tool_type=result.tool_type,
        tool_name=result.tool_name,
        description=result.description,
        input_schema=result.input_schema,
        errors=result.errors or [],
        suggestions=result.suggestions or [],
        missing_packages=result.missing_packages or [],
        installed_packages=result.installed_packages or [],
        conflict_packages=result.conflict_packages or []
    )


@router.post("/", response_model=ToolResponse)
def create_tool(tool_data: ToolCreate, db: Session = Depends(get_db)):
    """
    Create a new tool
    
    The source code will be automatically validated.
    """
    # Check if tool name already exists
    existing = db.query(Tool).filter(Tool.name == tool_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"工具名称 '{tool_data.name}' 已存在")
    
    # Validate the source code
    validation = validate_tool(tool_data.source_code)
    
    # Create tool record
    tool = Tool(
        name=tool_data.name,
        description=tool_data.description or validation.description,
        source_code=tool_data.source_code,
        tool_type=validation.tool_type if validation.is_valid else None,
        status=ToolStatus.VALID if validation.is_valid else ToolStatus.INVALID,
        validation_message="\n".join(validation.errors) if validation.errors else None,
        input_schema=validation.input_schema,
        uploader=tool_data.uploader
    )
    
    # If validation failed, add suggestions to the message
    if not validation.is_valid and validation.suggestions:
        tool.validation_message = (
            (tool.validation_message or "") + 
            "\n\n建议:\n" + 
            "\n".join(validation.suggestions)
        )
    
    db.add(tool)
    db.commit()
    db.refresh(tool)
    
    return tool


@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    """
    Get a tool by ID
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
def update_tool(tool_id: int, tool_data: ToolUpdate, db: Session = Depends(get_db)):
    """
    Update a tool
    
    If source code is updated, it will be re-validated.
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    
    # Check name uniqueness if changing
    if tool_data.name and tool_data.name != tool.name:
        existing = db.query(Tool).filter(Tool.name == tool_data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"工具名称 '{tool_data.name}' 已存在")
        tool.name = tool_data.name
    
    if tool_data.description is not None:
        tool.description = tool_data.description
    
    # If source code is updated, re-validate
    if tool_data.source_code:
        tool.source_code = tool_data.source_code
        validation = validate_tool(tool_data.source_code)
        
        tool.tool_type = validation.tool_type if validation.is_valid else tool.tool_type
        tool.status = ToolStatus.VALID if validation.is_valid else ToolStatus.INVALID
        tool.validation_message = "\n".join(validation.errors) if validation.errors else None
        tool.input_schema = validation.input_schema
        
        if not validation.is_valid and validation.suggestions:
            tool.validation_message = (
                (tool.validation_message or "") + 
                "\n\n建议:\n" + 
                "\n".join(validation.suggestions)
            )
        
        # Reload tool in executor
        if validation.is_valid:
            reload_tool(tool)
    
    db.commit()
    db.refresh(tool)
    
    return tool


@router.delete("/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    """
    Delete a tool
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    
    db.delete(tool)
    db.commit()
    
    return {"message": "工具已删除", "id": tool_id}


@router.post("/{tool_id}/revalidate", response_model=ToolResponse)
def revalidate_tool(tool_id: int, db: Session = Depends(get_db)):
    """
    Re-validate a tool's source code
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    
    validation = validate_tool(tool.source_code)
    
    tool.tool_type = validation.tool_type if validation.is_valid else tool.tool_type
    tool.status = ToolStatus.VALID if validation.is_valid else ToolStatus.INVALID
    tool.validation_message = "\n".join(validation.errors) if validation.errors else None
    tool.input_schema = validation.input_schema
    
    if not validation.is_valid and validation.suggestions:
        tool.validation_message = (
            (tool.validation_message or "") + 
            "\n\n建议:\n" + 
            "\n".join(validation.suggestions)
        )
    
    db.commit()
    db.refresh(tool)
    
    return tool


@router.post("/{tool_id}/toggle-status", response_model=ToolResponse)
def toggle_tool_status(tool_id: int, db: Session = Depends(get_db)):
    """
    Toggle tool between enabled and disabled status
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    
    if tool.status == ToolStatus.DISABLED:
        # Re-validate when enabling
        validation = validate_tool(tool.source_code)
        tool.status = ToolStatus.VALID if validation.is_valid else ToolStatus.INVALID
    elif tool.status == ToolStatus.VALID:
        tool.status = ToolStatus.DISABLED
    else:
        raise HTTPException(status_code=400, detail="只有有效或禁用的工具可以切换状态")
    
    db.commit()
    db.refresh(tool)
    
    return tool
