import subprocess
import os

def run_python_script(script_path, args=None, python_executable=None):
    """
    自动执行Python脚本的函数
    
    参数:
        script_path (str): 目标Python脚本的路径（相对路径或绝对路径）
        args (list, optional): 传递给脚本的命令行参数，例如 ["--name", "test", "123"]
        python_executable (str, optional): Python解释器路径，默认使用当前环境的python
    
    返回:
        dict: 包含执行结果的结构化字典：
            - success: bool，是否执行成功（返回码为0）
            - return_code: int，脚本返回码
            - stdout: str，脚本标准输出
            - stderr: str，脚本标准错误
            - error: str，函数执行过程中出现的异常信息（无则为空）
    """
    # 初始化返回结果
    result = {
        "success": False,
        "return_code": -1,
        "stdout": "",
        "stderr": "",
        "error": ""
    }
    
    try:
        # 处理默认Python解释器（Linux/macOS可根据情况改为"python3"）
        if python_executable is None:
            python_executable = "python"
        
        # 转换为绝对路径，避免路径歧义
        script_abs_path = os.path.abspath(script_path)
        
        # 前置检查：脚本文件是否存在
        if not os.path.exists(script_abs_path):
            result["error"] = f"脚本文件不存在：{script_abs_path}"
            return result
        
        # 前置检查：是否为有效文件
        if not os.path.isfile(script_abs_path):
            result["error"] = f"指定路径不是文件：{script_abs_path}"
            return result
        
        # 构建执行命令
        cmd = [python_executable, script_abs_path]
        # 添加命令行参数（如果有）
        if args and isinstance(args, list):
            cmd.extend(args)
        
        # 执行脚本并捕获输出
        process = subprocess.run(
            cmd,
            capture_output=True,  # 捕获stdout/stderr
            text=True,           # 输出为字符串（而非字节）
            check=False          # 不主动抛出非0返回码异常，自行处理
        )
        
        # 填充执行结果
        result["return_code"] = process.returncode
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["success"] = (process.returncode == 0)
        
    except Exception as e:
        # 捕获执行过程中的所有异常（如权限不足、解释器不存在等）
        result["error"] = f"执行异常：{str(e)}"
    
    return result

# ------------------- 测试示例 -------------------
if __name__ == "__main__":
    # 示例1：执行当前目录下的test.py（无参数）
    test_result = run_python_script("test.py")
    print("=== 执行结果 ===")
    print(f"执行成功：{test_result['success']}")
    print(f"返回码：{test_result['return_code']}")
    print(f"标准输出：\n{test_result['stdout']}")
    print(f"错误输出：\n{test_result['stderr']}")
    if test_result["error"]:
        print(f"异常信息：{test_result['error']}")

    # 示例2：执行脚本并传递参数
    # result_with_args = run_python_script("test.py", args=["--input", "data.txt", "--num", "10"])
    
    # 示例3：指定Python3解释器（Linux/macOS）
    # result_with_python3 = run_python_script("test.py", python_executable="/usr/bin/python3")