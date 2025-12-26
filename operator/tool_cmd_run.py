"""
cmd_run 工具模块

提供 Python 脚本执行能力，适合作为平台通用工具。
"""
import os
import subprocess
from langchain_core.tools import tool

@tool
def run_python_script_tool(script_path: str, args: list = None, python_executable: str = None) -> dict:
    """
    执行指定 Python 脚本
    
    Args:
        script_path (str): 目标 Python 脚本路径
        args (list, optional): 传递给脚本的命令行参数
        python_executable (str, optional): Python 解释器路径，默认当前环境
    Returns:
        dict: 执行结果
    """
    result = {
        "success": False,
        "return_code": -1,
        "stdout": "",
        "stderr": "",
        "error": ""
    }
    try:
        if python_executable is None:
            python_executable = "python"
        script_abs_path = os.path.abspath(script_path)
        if not os.path.exists(script_abs_path):
            result["error"] = f"脚本文件不存在：{script_abs_path}"
            return result
        if not os.path.isfile(script_abs_path):
            result["error"] = f"指定路径不是文件：{script_abs_path}"
            return result
        cmd = [python_executable, script_abs_path]
        if args and isinstance(args, list):
            cmd.extend(args)
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        result["return_code"] = process.returncode
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["success"] = (process.returncode == 0)
    except Exception as e:
        result["error"] = f"执行异常：{str(e)}"
    return result
