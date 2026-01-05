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
    
    def _register_file_download(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        注册文件以生成下载 URL
        
        Args:
            file_path: 服务器上的文件路径
            expires_in: 过期时间（秒）
            
        Returns:
            下载 URL 或 None
        """
        import hashlib
        import uuid
        from datetime import datetime
        from app.config import get_settings
        
        # 直接在内存中注册，避免 HTTP 请求自己
        # 导入 mcp 模块中的 _file_tokens
        try:
            from app.api.mcp import _file_tokens
            
            if not os.path.exists(file_path):
                print(f"[DEBUG] File not exists: {file_path}")
                return None
            
            token = hashlib.md5(f"{file_path}{uuid.uuid4()}".encode()).hexdigest()
            
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
            
            download_url = f"{base_url}/api/mcp/files/download/{token}"
            print(f"[DEBUG] Registered file download: {file_path} -> {download_url}")
            return download_url
        except Exception as e:
            print(f"[DEBUG] Failed to register file download: {e}")
            return None
    
    def _process_result_download_urls(self, result: Any) -> Any:
        """
        处理工具返回结果，为文件路径生成下载 URL
        
        检测结果中的文件路径字段，自动注册并填充 download_url
        支持单个结果和批量结果（results 数组）
        """
        if not isinstance(result, dict):
            return result
        
        # 检测常见的文件路径字段
        file_path_keys = ['image_path', 'pdf_path', 'file_path', 'output_path']
        
        # 处理顶层文件路径
        for key in file_path_keys:
            if key in result and result[key]:
                file_path = result[key]
                if isinstance(file_path, str) and os.path.exists(file_path):
                    # 如果 download_url 为 None，尝试注册
                    if result.get('download_url') is None:
                        result['download_url'] = self._register_file_download(file_path)
                    break
        
        # 处理批量结果中的嵌套文件路径（results 数组）
        if 'results' in result and isinstance(result['results'], list):
            for item in result['results']:
                if isinstance(item, dict):
                    for key in file_path_keys:
                        if key in item and item[key]:
                            file_path = item[key]
                            if isinstance(file_path, str) and os.path.exists(file_path):
                                if item.get('download_url') is None:
                                    item['download_url'] = self._register_file_download(file_path)
                                break
        
        # 处理 file_mappings 数组
        if 'file_mappings' in result and isinstance(result['file_mappings'], list):
            for mapping in result['file_mappings']:
                if isinstance(mapping, dict):
                    output_path = mapping.get('output')
                    if output_path and isinstance(output_path, str) and os.path.exists(output_path):
                        if mapping.get('download_url') is None:
                            mapping['download_url'] = self._register_file_download(output_path)
        
        return result
    
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
            captured_stdout = StringIO()
            sys.stdout = captured_stdout
            output = ""
            
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
                # 安全获取捕获的输出
                try:
                    if hasattr(captured_stdout, 'getvalue'):
                        output = captured_stdout.getvalue()
                except Exception:
                    pass
                sys.stdout = old_stdout
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # 处理结果中的文件下载 URL
            # print(f"[DEBUG] Before processing: {type(result)} - {result}")
            result = self._process_result_download_urls(result)
            # print(f"[DEBUG] After processing: {result}")
            
            # Combine result with any printed output
            if output:
                if isinstance(result, dict):
                    result['_stdout'] = output
                else:
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
