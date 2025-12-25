"""
Tool Executor Service

Dynamically loads and executes LangChain tools from source code.
"""
import sys
import time
import traceback
from typing import Any, Dict, Optional, Tuple
from io import StringIO
import importlib.util
import tempfile
import os

from app.models import Tool, ToolType


class ToolExecutor:
    """Executor for running LangChain tools"""
    
    def __init__(self):
        self._loaded_tools: Dict[str, Any] = {}
    
    def load_tool(self, tool: Tool) -> Tuple[bool, Optional[str]]:
        """
        Load a tool from its source code
        
        Args:
            tool: Tool model instance
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Create a temporary module
            spec = importlib.util.spec_from_loader(
                f"tool_{tool.id}_{tool.name}",
                loader=None,
                origin="dynamic"
            )
            module = importlib.util.module_from_spec(spec)
            
            # Execute the source code in the module's namespace
            exec(tool.source_code, module.__dict__)
            
            # Find the tool object
            tool_obj = None
            
            if tool.tool_type == ToolType.FUNCTION:
                # Look for @tool decorated function
                for name, obj in module.__dict__.items():
                    if hasattr(obj, 'name') and hasattr(obj, 'run'):
                        # This is likely a StructuredTool created by @tool decorator
                        tool_obj = obj
                        break
            else:
                # Look for BaseTool subclass
                from langchain_core.tools import BaseTool
                for name, obj in module.__dict__.items():
                    if isinstance(obj, type) and issubclass(obj, BaseTool) and obj is not BaseTool:
                        # Instantiate the class
                        tool_obj = obj()
                        break
            
            if tool_obj is None:
                return False, "无法在代码中找到有效的工具对象"
            
            self._loaded_tools[tool.name] = tool_obj
            return True, None
            
        except Exception as e:
            return False, f"加载工具失败: {str(e)}\n{traceback.format_exc()}"
    
    def execute(
        self,
        tool: Tool,
        arguments: Dict[str, Any]
    ) -> Tuple[bool, Any, Optional[str], int]:
        """
        Execute a tool with given arguments
        
        Args:
            tool: Tool model instance
            arguments: Input arguments for the tool
            
        Returns:
            Tuple of (success, result, error_message, execution_time_ms)
        """
        start_time = time.time()
        
        try:
            # Load tool if not already loaded
            if tool.name not in self._loaded_tools:
                success, error = self.load_tool(tool)
                if not success:
                    execution_time = int((time.time() - start_time) * 1000)
                    return False, None, error, execution_time
            
            tool_obj = self._loaded_tools[tool.name]
            
            # Execute the tool
            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            
            try:
                # 处理参数格式 - 确保正确传递给 LangChain tool
                # LangChain tool.invoke() 期望直接的参数字典，如 {"city": "北京"}
                # 但有时可能收到嵌套格式如 {"kwargs": {"city": "北京"}}
                if "kwargs" in arguments and isinstance(arguments.get("kwargs"), dict):
                    actual_args = arguments["kwargs"]
                else:
                    actual_args = arguments
                
                result = tool_obj.invoke(actual_args)
            finally:
                output = sys.stdout.getvalue()
                sys.stdout = old_stdout
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Combine result with any printed output
            if output:
                result = f"{result}\n\n[stdout]:\n{output}"
            
            return True, result, None, execution_time
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"执行工具失败: {str(e)}\n{traceback.format_exc()}"
            return False, None, error_msg, execution_time
    
    def unload_tool(self, tool_name: str) -> None:
        """Unload a tool from memory"""
        if tool_name in self._loaded_tools:
            del self._loaded_tools[tool_name]
    
    def reload_tool(self, tool: Tool) -> Tuple[bool, Optional[str]]:
        """Reload a tool (unload and load again)"""
        self.unload_tool(tool.name)
        return self.load_tool(tool)
    
    def get_loaded_tools(self) -> list:
        """Get list of loaded tool names"""
        return list(self._loaded_tools.keys())


# Global executor instance
executor = ToolExecutor()


def execute_tool(tool: Tool, arguments: Dict[str, Any]) -> Tuple[bool, Any, Optional[str], int]:
    """Convenience function to execute a tool"""
    return executor.execute(tool, arguments)


def reload_tool(tool: Tool) -> Tuple[bool, Optional[str]]:
    """Convenience function to reload a tool"""
    return executor.reload_tool(tool)
