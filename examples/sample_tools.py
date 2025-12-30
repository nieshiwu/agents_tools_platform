"""
示例工具集 - 用于平台展示

这些工具可以直接复制到平台上传使用
"""

# ============================================
# 工具1: 计算器
# ============================================
CALCULATOR_TOOL = '''from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """安全的数学计算器
    
    计算数学表达式的值，支持加减乘除、括号、幂运算等。
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4" 或 "(10 - 5) ** 2"
    
    Returns:
        计算结果
    """
    try:
        # 只允许安全的字符
        allowed_chars = set('0123456789+-*/().% **')
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return "错误：表达式包含非法字符"
        
        # 禁止危险的内置函数
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果：{result}"
    except ZeroDivisionError:
        return "错误：除数不能为零"
    except Exception as e:
        return f"计算错误：{str(e)}"
'''

# ============================================
# 工具2: 文本处理器
# ============================================
TEXT_PROCESSOR_TOOL = '''from langchain_core.tools import tool

@tool
def text_processor(text: str, operation: str = "stats") -> str:
    """文本处理工具
    
    对文本进行各种处理操作。
    
    Args:
        text: 要处理的文本内容
        operation: 操作类型，可选值：
            - stats: 统计信息（字符数、单词数、行数）
            - upper: 转换为大写
            - lower: 转换为小写
            - reverse: 反转文本
            - trim: 去除首尾空白
    
    Returns:
        处理后的结果
    """
    operations = {
        "stats": lambda t: f"字符数: {len(t)}, 单词数: {len(t.split())}, 行数: {len(t.splitlines())}",
        "upper": lambda t: t.upper(),
        "lower": lambda t: t.lower(),
        "reverse": lambda t: t[::-1],
        "trim": lambda t: t.strip()
    }
    
    if operation not in operations:
        return f"不支持的操作: {operation}，可选值: {list(operations.keys())}"
    
    return operations[operation](text)
'''

# ============================================
# 工具3: JSON 格式化器
# ============================================
JSON_FORMATTER_TOOL = '''from langchain_core.tools import tool
import json

@tool
def json_formatter(json_string: str, indent: int = 2) -> str:
    """JSON 格式化工具
    
    将 JSON 字符串格式化为易读的形式，或压缩 JSON。
    
    Args:
        json_string: 要格式化的 JSON 字符串
        indent: 缩进空格数，设为0则压缩JSON，默认为2
    
    Returns:
        格式化后的 JSON 字符串
    """
    try:
        data = json.loads(json_string)
        if indent == 0:
            return json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return json.dumps(data, indent=indent, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"JSON 解析错误：{str(e)}"
'''

# ============================================
# 工具4: 时间工具
# ============================================
DATETIME_TOOL = '''from langchain_core.tools import tool
from datetime import datetime, timedelta

@tool
def datetime_tool(operation: str = "now", value: str = "") -> str:
    """日期时间工具
    
    获取当前时间或进行日期计算。
    
    Args:
        operation: 操作类型，可选值：
            - now: 获取当前时间
            - date: 获取当前日期
            - timestamp: 获取当前时间戳
            - parse: 解析日期字符串（需要在value中提供）
            - add_days: 计算N天后的日期（需要在value中提供天数）
        value: 附加参数，根据operation不同而不同
    
    Returns:
        处理结果
    """
    now = datetime.now()
    
    if operation == "now":
        return now.strftime("%Y-%m-%d %H:%M:%S")
    elif operation == "date":
        return now.strftime("%Y-%m-%d")
    elif operation == "timestamp":
        return str(int(now.timestamp()))
    elif operation == "parse":
        try:
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(value, fmt)
                    return f"解析结果: {dt.strftime('%Y-%m-%d %H:%M:%S')} (星期{['一','二','三','四','五','六','日'][dt.weekday()]})"
                except:
                    continue
            return "无法解析日期格式"
        except Exception as e:
            return f"解析错误: {str(e)}"
    elif operation == "add_days":
        try:
            days = int(value)
            future = now + timedelta(days=days)
            return f"{days}天后是: {future.strftime('%Y-%m-%d')} (星期{['一','二','三','四','五','六','日'][future.weekday()]})"
        except:
            return "请提供有效的天数"
    else:
        return f"不支持的操作: {operation}"
'''

# ============================================
# 工具5: 字符串编码工具
# ============================================
ENCODER_TOOL = '''from langchain_core.tools import tool
import base64
import hashlib
import urllib.parse

@tool
def encoder(text: str, method: str = "base64_encode") -> str:
    """字符串编码/解码工具
    
    对字符串进行各种编码和解码操作。
    
    Args:
        text: 要处理的文本
        method: 编码方法，可选值：
            - base64_encode: Base64编码
            - base64_decode: Base64解码
            - url_encode: URL编码
            - url_decode: URL解码
            - md5: 计算MD5哈希
            - sha256: 计算SHA256哈希
    
    Returns:
        编码/解码后的结果
    """
    try:
        if method == "base64_encode":
            return base64.b64encode(text.encode('utf-8')).decode('utf-8')
        elif method == "base64_decode":
            return base64.b64decode(text.encode('utf-8')).decode('utf-8')
        elif method == "url_encode":
            return urllib.parse.quote(text)
        elif method == "url_decode":
            return urllib.parse.unquote(text)
        elif method == "md5":
            return hashlib.md5(text.encode('utf-8')).hexdigest()
        elif method == "sha256":
            return hashlib.sha256(text.encode('utf-8')).hexdigest()
        else:
            return f"不支持的方法: {method}"
    except Exception as e:
        return f"处理错误: {str(e)}"
'''

# ============================================
# 工具6: 随机生成器
# ============================================
RANDOM_GENERATOR_TOOL = '''from langchain_core.tools import tool
import random
import string

@tool
def random_generator(gen_type: str = "uuid", length: int = 16) -> str:
    """随机数据生成器
    
    生成各种随机数据。
    
    Args:
        gen_type: 生成类型，可选值：
            - uuid: 生成UUID
            - password: 生成随机密码
            - number: 生成随机数字
            - hex: 生成随机十六进制字符串
            - choice: 从列表中随机选择（length参数作为范围上限）
        length: 生成长度（对于password/number/hex有效），默认16
    
    Returns:
        生成的随机数据
    """
    import uuid as uuid_module
    
    if gen_type == "uuid":
        return str(uuid_module.uuid4())
    elif gen_type == "password":
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))
    elif gen_type == "number":
        return ''.join(random.choice(string.digits) for _ in range(length))
    elif gen_type == "hex":
        return ''.join(random.choice('0123456789abcdef') for _ in range(length))
    elif gen_type == "choice":
        return str(random.randint(1, length))
    else:
        return f"不支持的类型: {gen_type}"
'''

# ============================================
# 工具7: IP/网络工具 (BaseTool 类示例)
# ============================================
NETWORK_TOOL = '''from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import socket

class NetworkToolInput(BaseModel):
    """网络工具输入参数"""
    operation: str = Field(description="操作类型: dns_lookup, ip_info, port_check")
    target: str = Field(description="目标地址或域名")
    port: int = Field(default=80, description="端口号（仅port_check使用）")

class NetworkTool(BaseTool):
    """网络工具 - 提供DNS查询、IP信息等功能"""
    
    name: str = "network_tool"
    description: str = "网络工具，支持DNS查询、IP信息查看、端口检测等操作"
    args_schema: Type[BaseModel] = NetworkToolInput
    
    def _run(self, operation: str, target: str, port: int = 80) -> str:
        """执行网络操作"""
        try:
            if operation == "dns_lookup":
                ip = socket.gethostbyname(target)
                return f"域名 {target} 解析结果: {ip}"
            
            elif operation == "ip_info":
                try:
                    hostname = socket.gethostbyaddr(target)
                    return f"IP {target} 的主机名: {hostname[0]}"
                except:
                    return f"无法获取 IP {target} 的主机名信息"
            
            elif operation == "port_check":
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((target, port))
                sock.close()
                if result == 0:
                    return f"端口 {target}:{port} 开放"
                else:
                    return f"端口 {target}:{port} 关闭或不可达"
            
            else:
                return f"不支持的操作: {operation}"
        
        except socket.gaierror:
            return f"无法解析域名: {target}"
        except Exception as e:
            return f"操作失败: {str(e)}"
'''


# 工具列表，方便导入
EXAMPLE_TOOLS = [
    {
        "name": "calculator",
        "description": "安全的数学计算器，支持加减乘除、括号、幂运算",
        "source_code": CALCULATOR_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "text_processor",
        "description": "文本处理工具，支持统计、大小写转换、反转等操作",
        "source_code": TEXT_PROCESSOR_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "json_formatter",
        "description": "JSON格式化工具，美化或压缩JSON字符串",
        "source_code": JSON_FORMATTER_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "datetime_tool",
        "description": "日期时间工具，获取时间、解析日期、日期计算",
        "source_code": DATETIME_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "encoder",
        "description": "编码解码工具，支持Base64、URL编码、MD5、SHA256",
        "source_code": ENCODER_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "random_generator",
        "description": "随机数据生成器，生成UUID、密码、随机数等",
        "source_code": RANDOM_GENERATOR_TOOL,
        "uploader": "系统示例"
    },
    {
        "name": "network_tool",
        "description": "网络工具，DNS查询、端口检测（BaseTool类示例）",
        "source_code": NETWORK_TOOL,
        "uploader": "系统示例"
    },
]


if __name__ == "__main__":
    # 打印所有示例工具
    for tool in EXAMPLE_TOOLS:
        print(f"\n{'='*50}")
        print(f"工具名称: {tool['name']}")
        print(f"描述: {tool['description']}")
        print(f"{'='*50}")
        print(tool['source_code'])
