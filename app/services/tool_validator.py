"""
Tool Validator Service

Validates uploaded Python code to check if it's a valid LangChain tool.
Supports:
1. Functions decorated with @tool
2. Classes inheriting from BaseTool
"""
import ast
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from app.models import ToolType


@dataclass
class ValidationResult:
    """Result of tool validation"""
    is_valid: bool
    tool_type: Optional[ToolType] = None
    tool_name: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.suggestions is None:
            self.suggestions = []


LANGCHAIN_TOOL_SPEC = """
=== LangChain 工具规范 ===

【方式一】使用 @tool 装饰器定义函数工具:

```python
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    \"\"\"搜索引擎工具，根据查询词返回搜索结果。
    
    Args:
        query: 搜索关键词
    
    Returns:
        搜索结果字符串
    \"\"\"
    # 实现代码
    return f"搜索结果: {query}"
```

要求:
1. 必须导入 `from langchain_core.tools import tool`
2. 函数必须有 @tool 装饰器
3. 函数必须有类型注解
4. 函数必须有 docstring 描述功能


【方式二】继承 BaseTool 类:

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional

class SearchInput(BaseModel):
    \"\"\"搜索工具的输入参数\"\"\"
    query: str = Field(description="搜索关键词")

class SearchTool(BaseTool):
    \"\"\"搜索引擎工具\"\"\"
    name: str = "search"
    description: str = "搜索引擎工具，根据查询词返回搜索结果"
    args_schema: Type[BaseModel] = SearchInput
    
    def _run(self, query: str) -> str:
        \"\"\"执行搜索\"\"\"
        return f"搜索结果: {query}"
    
    async def _arun(self, query: str) -> str:
        \"\"\"异步执行搜索（可选）\"\"\"
        return self._run(query)
```

要求:
1. 必须导入 `from langchain_core.tools import BaseTool`
2. 类必须继承 BaseTool
3. 必须定义 name 和 description 属性
4. 必须实现 _run 方法
5. 建议定义 args_schema 指定输入参数模式
"""


class ToolValidator:
    """Validator for LangChain tools"""
    
    def __init__(self):
        self.spec = LANGCHAIN_TOOL_SPEC
    
    def validate(self, source_code: str) -> ValidationResult:
        """
        Validate source code and check if it's a valid LangChain tool
        
        Args:
            source_code: Python source code string
            
        Returns:
            ValidationResult with validation details
        """
        # First, check for syntax errors
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"语法错误: 第{e.lineno}行 - {e.msg}"],
                suggestions=["请检查代码语法是否正确"]
            )
        
        # Try to detect tool type
        has_tool_decorator = self._check_tool_decorator(tree, source_code)
        has_basetool_class = self._check_basetool_class(tree, source_code)
        
        if has_tool_decorator:
            return self._validate_tool_function(tree, source_code)
        elif has_basetool_class:
            return self._validate_basetool_class(tree, source_code)
        else:
            return ValidationResult(
                is_valid=False,
                errors=[
                    "未检测到有效的 LangChain 工具",
                    "代码中没有 @tool 装饰的函数",
                    "代码中没有继承 BaseTool 的类"
                ],
                suggestions=[
                    "请参考以下规范编写工具代码:",
                    self.spec
                ]
            )
    
    def _check_tool_decorator(self, tree: ast.AST, source_code: str) -> bool:
        """Check if there's a @tool decorated function"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == 'tool':
                        return True
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == 'tool':
                            return True
        return False
    
    def _check_basetool_class(self, tree: ast.AST, source_code: str) -> bool:
        """Check if there's a class inheriting from BaseTool"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'BaseTool':
                        return True
                    if isinstance(base, ast.Attribute) and base.attr == 'BaseTool':
                        return True
        return False
    
    def _validate_tool_function(self, tree: ast.AST, source_code: str) -> ValidationResult:
        """Validate a @tool decorated function"""
        errors = []
        suggestions = []
        tool_name = None
        description = None
        input_schema = {}
        
        # Check for proper import
        has_tool_import = self._check_import(tree, 'tool', ['langchain_core.tools', 'langchain.tools'])
        if not has_tool_import:
            errors.append("缺少必要的导入: from langchain_core.tools import tool")
            suggestions.append("请在文件开头添加: from langchain_core.tools import tool")
        
        # Find the decorated function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                is_tool_func = False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == 'tool':
                        is_tool_func = True
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name) and decorator.func.id == 'tool':
                            is_tool_func = True
                
                if is_tool_func:
                    tool_name = node.name
                    
                    # Check docstring
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        errors.append(f"函数 '{tool_name}' 缺少 docstring")
                        suggestions.append("请为函数添加描述性的 docstring")
                    else:
                        description = docstring.split('\n')[0]  # First line as description
                    
                    # Check type annotations
                    if not node.returns:
                        errors.append(f"函数 '{tool_name}' 缺少返回值类型注解")
                        suggestions.append("请添加返回值类型注解，例如: def func(...) -> str:")
                    
                    # Extract input schema from arguments
                    input_schema = self._extract_function_schema(node)
                    
                    if not node.args.args or (len(node.args.args) == 1 and node.args.args[0].arg == 'self'):
                        suggestions.append("函数没有参数，考虑是否需要添加输入参数")
                    else:
                        for arg in node.args.args:
                            if arg.arg != 'self' and not arg.annotation:
                                errors.append(f"参数 '{arg.arg}' 缺少类型注解")
                    
                    break
        
        is_valid = len(errors) == 0 and tool_name is not None
        
        if not is_valid and not errors:
            errors.append("未找到有效的 @tool 装饰的函数")
        
        return ValidationResult(
            is_valid=is_valid,
            tool_type=ToolType.FUNCTION if is_valid else None,
            tool_name=tool_name,
            description=description,
            input_schema=input_schema if input_schema else None,
            errors=errors,
            suggestions=suggestions if suggestions else None
        )
    
    def _validate_basetool_class(self, tree: ast.AST, source_code: str) -> ValidationResult:
        """Validate a BaseTool subclass"""
        errors = []
        suggestions = []
        tool_name = None
        description = None
        input_schema = {}
        
        # Check for proper import
        has_basetool_import = self._check_import(tree, 'BaseTool', ['langchain_core.tools', 'langchain.tools'])
        if not has_basetool_import:
            errors.append("缺少必要的导入: from langchain_core.tools import BaseTool")
            suggestions.append("请在文件开头添加: from langchain_core.tools import BaseTool")
        
        # Find the BaseTool subclass
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                is_basetool = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'BaseTool':
                        is_basetool = True
                    if isinstance(base, ast.Attribute) and base.attr == 'BaseTool':
                        is_basetool = True
                
                if is_basetool:
                    class_name = node.name
                    has_name = False
                    has_description = False
                    has_run = False
                    
                    for item in node.body:
                        # Check for name attribute
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            if item.target.id == 'name':
                                has_name = True
                                if item.value and isinstance(item.value, ast.Constant):
                                    tool_name = item.value.value
                            if item.target.id == 'description':
                                has_description = True
                                if item.value and isinstance(item.value, ast.Constant):
                                    description = item.value.value
                        
                        # Check for simple assignment
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    if target.id == 'name':
                                        has_name = True
                                        if isinstance(item.value, ast.Constant):
                                            tool_name = item.value.value
                                    if target.id == 'description':
                                        has_description = True
                                        if isinstance(item.value, ast.Constant):
                                            description = item.value.value
                        
                        # Check for _run method
                        if isinstance(item, ast.FunctionDef) and item.name == '_run':
                            has_run = True
                            input_schema = self._extract_function_schema(item)
                    
                    if not has_name:
                        errors.append(f"类 '{class_name}' 缺少 'name' 属性")
                        suggestions.append("请添加: name: str = \"tool_name\"")
                    
                    if not has_description:
                        errors.append(f"类 '{class_name}' 缺少 'description' 属性")
                        suggestions.append("请添加: description: str = \"工具描述\"")
                    
                    if not has_run:
                        errors.append(f"类 '{class_name}' 缺少 '_run' 方法")
                        suggestions.append("请实现 _run 方法")
                    
                    if not tool_name:
                        tool_name = class_name.lower()
                    
                    break
        
        is_valid = len(errors) == 0 and tool_name is not None
        
        if not is_valid and not errors:
            errors.append("未找到有效的 BaseTool 子类")
        
        return ValidationResult(
            is_valid=is_valid,
            tool_type=ToolType.CLASS if is_valid else None,
            tool_name=tool_name,
            description=description,
            input_schema=input_schema if input_schema else None,
            errors=errors,
            suggestions=suggestions if suggestions else None
        )
    
    def _check_import(self, tree: ast.AST, name: str, modules: List[str]) -> bool:
        """Check if a specific name is imported from allowed modules"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in modules:
                    for alias in node.names:
                        if alias.name == name or alias.name == '*':
                            return True
        return False
    
    def _extract_function_schema(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract JSON schema from function arguments"""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for arg in node.args.args:
            if arg.arg == 'self':
                continue
            
            arg_name = arg.arg
            arg_type = "string"  # default type
            
            if arg.annotation:
                type_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                arg_type = self._python_type_to_json_type(type_str)
            
            schema["properties"][arg_name] = {
                "type": arg_type,
                "description": f"Parameter: {arg_name}"
            }
            
            # Check if argument has default value
            defaults_offset = len(node.args.args) - len(node.args.defaults)
            arg_index = node.args.args.index(arg)
            
            if arg_index < defaults_offset:
                schema["required"].append(arg_name)
        
        return schema
    
    def _python_type_to_json_type(self, type_str: str) -> str:
        """Convert Python type annotation to JSON schema type"""
        type_mapping = {
            'str': 'string',
            'int': 'integer',
            'float': 'number',
            'bool': 'boolean',
            'list': 'array',
            'List': 'array',
            'dict': 'object',
            'Dict': 'object',
            'None': 'null',
        }
        
        for py_type, json_type in type_mapping.items():
            if py_type in type_str:
                return json_type
        
        return 'string'
    
    def get_spec(self) -> str:
        """Get the LangChain tool specification"""
        return self.spec


# Global validator instance
validator = ToolValidator()


def validate_tool(source_code: str) -> ValidationResult:
    """Convenience function to validate a tool"""
    return validator.validate(source_code)


def get_tool_spec() -> str:
    """Get the tool specification"""
    return validator.get_spec()
