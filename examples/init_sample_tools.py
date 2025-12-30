"""
初始化脚本 - 将示例工具添加到数据库

使用方法:
    python init_sample_tools.py
"""
import requests
import sys

API_BASE_URL = "http://localhost:7000/api"

# 示例工具定义
SAMPLE_TOOLS = [
    {
        "name": "calculator",
        "description": "安全的数学计算器，支持加减乘除、括号、幂运算",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool

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
        allowed_chars = set('0123456789+-*/().% **')
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return "错误：表达式包含非法字符"
        
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果：{result}"
    except ZeroDivisionError:
        return "错误：除数不能为零"
    except Exception as e:
        return f"计算错误：{str(e)}"
'''
    },
    {
        "name": "text_processor",
        "description": "文本处理工具，支持统计、大小写转换、反转等操作",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool

@tool
def text_processor(text: str, operation: str = "stats") -> str:
    """文本处理工具
    
    对文本进行各种处理操作。
    
    Args:
        text: 要处理的文本内容
        operation: 操作类型，可选值：stats(统计)、upper(大写)、lower(小写)、reverse(反转)、trim(去空白)
    
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
    },
    {
        "name": "json_formatter",
        "description": "JSON格式化工具，美化或压缩JSON字符串",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool
import json

@tool
def json_formatter(json_string: str, indent: int = 2) -> str:
    """JSON 格式化工具
    
    将 JSON 字符串格式化为易读的形式。
    
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
    },
    {
        "name": "datetime_tool",
        "description": "日期时间工具，获取时间、解析日期、日期计算",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool
from datetime import datetime, timedelta

@tool
def datetime_tool(operation: str = "now", value: str = "") -> str:
    """日期时间工具
    
    获取当前时间或进行日期计算。
    
    Args:
        operation: 操作类型 - now(当前时间)、date(当前日期)、timestamp(时间戳)、add_days(N天后)
        value: 附加参数，如add_days时的天数
    
    Returns:
        处理结果
    """
    now = datetime.now()
    weekdays = ['一','二','三','四','五','六','日']
    
    if operation == "now":
        return now.strftime("%Y-%m-%d %H:%M:%S")
    elif operation == "date":
        return now.strftime("%Y-%m-%d")
    elif operation == "timestamp":
        return str(int(now.timestamp()))
    elif operation == "add_days":
        try:
            days = int(value)
            future = now + timedelta(days=days)
            return f"{days}天后是: {future.strftime('%Y-%m-%d')} (星期{weekdays[future.weekday()]})"
        except:
            return "请提供有效的天数"
    else:
        return f"不支持的操作: {operation}"
'''
    },
    {
        "name": "encoder",
        "description": "编码解码工具，支持Base64、URL编码、MD5、SHA256",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool
import base64
import hashlib
import urllib.parse

@tool
def encoder(text: str, method: str = "base64_encode") -> str:
    """字符串编码/解码工具
    
    对字符串进行各种编码和解码操作。
    
    Args:
        text: 要处理的文本
        method: 编码方法 - base64_encode、base64_decode、url_encode、url_decode、md5、sha256
    
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
    },
    {
        "name": "random_generator",
        "description": "随机数据生成器，生成UUID、密码、随机数等",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import tool
import random
import string
import uuid as uuid_module

@tool
def random_generator(gen_type: str = "uuid", length: int = 16) -> str:
    """随机数据生成器
    
    生成各种随机数据。
    
    Args:
        gen_type: 生成类型 - uuid、password、number、hex
        length: 生成长度（对于password/number/hex有效），默认16
    
    Returns:
        生成的随机数据
    """
    if gen_type == "uuid":
        return str(uuid_module.uuid4())
    elif gen_type == "password":
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(chars) for _ in range(length))
    elif gen_type == "number":
        return ''.join(random.choice(string.digits) for _ in range(length))
    elif gen_type == "hex":
        return ''.join(random.choice('0123456789abcdef') for _ in range(length))
    else:
        return f"不支持的类型: {gen_type}"
'''
    },
    {
        "name": "network_tool",
        "description": "网络工具，DNS查询、端口检测（BaseTool类示例）",
        "uploader": "系统示例",
        "source_code": '''from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import socket

class NetworkToolInput(BaseModel):
    """网络工具输入参数"""
    operation: str = Field(description="操作类型: dns_lookup, port_check")
    target: str = Field(description="目标地址或域名")
    port: int = Field(default=80, description="端口号（仅port_check使用）")

class NetworkTool(BaseTool):
    """网络工具"""
    
    name: str = "network_tool"
    description: str = "网络工具，支持DNS查询、端口检测等操作"
    args_schema: Type[BaseModel] = NetworkToolInput
    
    def _run(self, operation: str, target: str, port: int = 80) -> str:
        """执行网络操作"""
        try:
            if operation == "dns_lookup":
                ip = socket.gethostbyname(target)
                return f"域名 {target} 解析结果: {ip}"
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
    },
]


def init_tools():
    """初始化示例工具到数据库"""
    print("=" * 50)
    print("🔧 初始化示例工具")
    print("=" * 50)
    
    # 检查 API 服务是否运行
    try:
        response = requests.get(f"{API_BASE_URL}/tools/statistics", timeout=5)
        response.raise_for_status()
        print("✅ API 服务连接成功")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务，请确保已启动: python run.py api")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        sys.exit(1)
    
    # 添加工具
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for tool in SAMPLE_TOOLS:
        print(f"\n📦 处理工具: {tool['name']}")
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/tools/",
                json=tool,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "valid":
                    print(f"   ✅ 添加成功 (状态: valid)")
                    success_count += 1
                else:
                    print(f"   ⚠️ 添加成功但验证失败 (状态: {result.get('status')})")
                    if result.get("validation_message"):
                        print(f"   📝 {result['validation_message'][:100]}...")
                    success_count += 1
            elif response.status_code == 400:
                error = response.json().get("detail", "")
                if "已存在" in error:
                    print(f"   ⏭️ 跳过 (工具已存在)")
                    skip_count += 1
                else:
                    print(f"   ❌ 添加失败: {error}")
                    fail_count += 1
            else:
                print(f"   ❌ 添加失败: HTTP {response.status_code}")
                fail_count += 1
                
        except Exception as e:
            print(f"   ❌ 添加失败: {str(e)}")
            fail_count += 1
    
    # 打印统计
    print("\n" + "=" * 50)
    print("📊 初始化完成")
    print(f"   ✅ 成功: {success_count}")
    print(f"   ⏭️ 跳过: {skip_count}")
    print(f"   ❌ 失败: {fail_count}")
    print("=" * 50)
    
    if success_count > 0:
        print("\n🎉 可以访问 http://localhost:8501 查看工具列表")


if __name__ == "__main__":
    init_tools()
