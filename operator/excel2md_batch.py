"""Excel 转 Markdown 工具 - 支持单文件和多文件输入"""

import os
import tempfile
import uuid
import requests
from typing import Optional, List

from langchain_core.tools import tool

# MCP 服务地址（用于注册文件下载）
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:7000/api/mcp")

# 支持的 Excel 文件扩展名
EXCEL_EXTENSIONS = ('.xlsx', '.xls', '.xlsm', '.xlsb')


def register_file_download(file_path: str, expires_in: int = 3600) -> Optional[str]:
    """向 MCP 服务注册文件，获取下载 URL"""
    try:
        resp = requests.post(
            f"{MCP_API_BASE}/files/register",
            json={"file_path": file_path, "expires_in": expires_in},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("download_url")
    except Exception:
        pass
    return None


def _validate_excel_file(path: str) -> Optional[str]:
    """验证并返回有效的 Excel 文件路径
    
    Args:
        path: 文件路径
        
    Returns:
        有效的绝对路径，如果文件无效则返回 None
    """
    if os.path.isfile(path) and path.lower().endswith(EXCEL_EXTENSIONS):
        return os.path.abspath(path)
    return None


def _convert_single_excel(
    excel_path: str,
    sheet: str = "Sheet1",
    max_rows: int = 200,
    max_cols: int = 20,
    include_index: bool = False,
    output_path: Optional[str] = None,
) -> dict:
    """转换单个 Excel 文件为 Markdown（内部函数）"""
    try:
        import pandas as pd
    except Exception as exc:
        return {
            "success": False,
            "source_file": excel_path,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：缺少 pandas 依赖（{exc}）"
        }

    if not os.path.isfile(excel_path):
        return {
            "success": False,
            "source_file": excel_path,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：文件不存在 - {excel_path}"
        }

    sheet_name: str | int = sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet_name = int(sheet)

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except Exception as exc:
        return {
            "success": False,
            "source_file": excel_path,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：读取 Excel 失败 - {exc}"
        }

    notes: list[str] = []
    original_rows, original_cols = len(df), df.shape[1]
    
    if len(df) > max_rows:
        df = df.head(max_rows)
        notes.append(f"已截取前 {max_rows} 行（原 {original_rows} 行）")

    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
        notes.append(f"已截取前 {max_cols} 列（原 {original_cols} 列）")

    try:
        markdown = df.to_markdown(index=include_index)
    except Exception as exc:
        return {
            "success": False,
            "source_file": excel_path,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：转换失败 - {exc}"
        }

    if notes:
        markdown = markdown + "\n\n" + "；".join(notes)

    # 保存文件
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(
            tempfile.gettempdir(), 
            f"{base_name}_{uuid.uuid4().hex[:8]}.md"
        )
    
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(output_path, "w", encoding="utf-8") as md_file:
            md_file.write(markdown)
        file_path = output_path
        download_url = register_file_download(output_path)
    except Exception as exc:
        return {
            "success": False,
            "source_file": excel_path,
            "markdown": markdown,
            "file_path": None,
            "download_url": None,
            "message": f"错误：写入文件失败 - {exc}"
        }

    return {
        "success": True,
        "source_file": excel_path,
        "markdown": markdown,
        "file_path": file_path,
        "download_url": download_url,
        "message": f"转换成功，{len(df)} 行 × {df.shape[1]} 列",
        "rows": len(df),
        "cols": df.shape[1]
    }


@tool
def excel_to_markdown(
    input_path: str,
    sheet: str = "Sheet1",
    max_rows: int = 200,
    max_cols: int = 20,
    include_index: bool = False,
    output_dir: Optional[str] = None,
) -> dict:
    """将 Excel 文件转换为 Markdown 表格。
    
    上传单个或多个 Excel 文件，输出对应的 Markdown 文件（一对一）。

    Args:
        input_path: 输入文件路径，支持：
            - 单个文件："/path/to/file.xlsx"
            - 多个文件（逗号分隔）："/path/file1.xlsx, /path/file2.xlsx"
        sheet: 工作表名称或索引（默认 "Sheet1"，可用 "0" 表示第一个）。
        max_rows: 每个文件输出的最大行数（默认 200）。
        max_cols: 每个文件输出的最大列数（默认 20）。
        include_index: 是否包含行索引（默认 False）。
        output_dir: 输出目录，若不指定则使用临时目录。

    Returns:
        包含转换结果的字典：
        - success: 是否成功
        - total_files: 处理的文件总数
        - processed: 成功数
        - failed: 失败数
        - results: 每个文件的转换结果（含 source_file, file_path, download_url）
        - file_mappings: 文件对应关系列表
        - message: 状态信息
        
        单文件时额外返回：markdown, file_path, download_url
    """
    if not input_path or not input_path.strip():
        return {
            "success": False,
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "results": [],
            "message": "错误：请提供有效的输入路径"
        }
    
    if max_rows <= 0 or max_cols <= 0:
        return {
            "success": False,
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "results": [],
            "message": "错误：max_rows 与 max_cols 需为正整数"
        }
    
    # 解析输入路径（支持逗号分隔）
    input_paths = [p.strip() for p in input_path.split(',') if p.strip()]
    
    # 验证并收集所有 Excel 文件（只处理明确指定的文件）
    all_excel_files = []
    invalid_paths = []
    for path in input_paths:
        valid_path = _validate_excel_file(path)
        if valid_path:
            all_excel_files.append(valid_path)
        else:
            invalid_paths.append(path)
    
    all_excel_files = sorted(set(all_excel_files))
    
    if not all_excel_files:
        error_msg = f"错误：未找到有效的 Excel 文件（输入：{input_path}）"
        if invalid_paths:
            error_msg += f"\n无效路径: {', '.join(invalid_paths)}"
        return {
            "success": False,
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "results": [],
            "message": error_msg
        }
    
    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.join(tempfile.gettempdir(), f"excel2md_{uuid.uuid4().hex[:8]}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 处理所有文件
    results = []
    merged_content = []
    processed = 0
    failed = 0
    
    for excel_file in all_excel_files:
        base_name = os.path.splitext(os.path.basename(excel_file))[0]
        output_path = os.path.join(output_dir, f"{base_name}.md")
        
        # 避免文件名冲突
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{base_name}_{counter}.md")
            counter += 1
        
        result = _convert_single_excel(
            excel_path=excel_file,
            sheet=sheet,
            max_rows=max_rows,
            max_cols=max_cols,
            include_index=include_index,
            output_path=output_path,
        )
        
        results.append(result)
        
        if result["success"]:
            processed += 1
        else:
            failed += 1
    
    # 构建返回结果
    success = failed == 0 and processed > 0
    
    # 构建文件映射列表（每个Excel对应一个Markdown）
    file_mappings = []
    for r in results:
        if r["success"]:
            file_mappings.append({
                "source": r["source_file"],
                "output": r["file_path"],
                "download_url": r["download_url"],
            })
    
    response = {
        "success": success,
        "total_files": len(all_excel_files),
        "processed": processed,
        "failed": failed,
        "results": results,
        "file_mappings": file_mappings,  # 新增：清晰的文件对应关系
        "output_dir": output_dir,
        "message": f"转换完成：共 {len(all_excel_files)} 个文件，成功 {processed} 个，失败 {failed} 个"
    }
    
    # 单文件时返回简化结果
    if len(all_excel_files) == 1:
        single = results[0]
        response.update({
            "markdown": single.get("markdown"),
            "file_path": single.get("file_path"),
            "download_url": single.get("download_url"),
            "message": single.get("message"),
        })
    
    return response


# 保留旧函数名作为别名，向后兼容
# excel_to_markdown_table = excel_to_markdown


if __name__ == "__main__":
    import pandas as pd
    
    # 创建测试目录和文件
    test_dir = os.path.join(tempfile.gettempdir(), "excel2md_test")
    os.makedirs(test_dir, exist_ok=True)
    
    for i in range(3):
        test_excel = os.path.join(test_dir, f"test_{i+1}.xlsx")
        test_df = pd.DataFrame({
            "姓名": ["张三", "李四", "王五"],
            "年龄": [25 + i, 30 + i, 28 + i],
            "部门": ["技术部", "市场部", "财务部"],
        })
        test_df.to_excel(test_excel, index=False)
    
    print("=== 测试单文件 ===")
    result = excel_to_markdown.invoke({
        "input_path": os.path.join(test_dir, "test_1.xlsx"),
    })
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")
    print(f"文件路径: {result.get('file_path')}")
    print(f"下载链接: {result.get('download_url')}")
    
    print("\n=== 测试多文件（逗号分隔）===")
    result = excel_to_markdown.invoke({
        "input_path": f"{os.path.join(test_dir, 'test_1.xlsx')}, {os.path.join(test_dir, 'test_2.xlsx')}",
    })
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")
    print(f"处理文件数: {result['processed']}")
    print("文件对应关系:")
    for mapping in result.get('file_mappings', []):
        print(f"  {os.path.basename(mapping['source'])} -> {os.path.basename(mapping['output'])}")
        print(f"    下载链接: {mapping['download_url']}")
    
    print("\n=== 测试无效路径（文件夹路径，应该报错）===")
    result = excel_to_markdown.invoke({
        "input_path": test_dir,  # 传入文件夹路径，不是文件
    })
    print(f"成功: {result['success']}")
    print(f"消息: {result['message']}")