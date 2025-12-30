"""Excel 转 Markdown 工具"""

import os
import requests
from typing import Optional

from langchain_core.tools import tool

# MCP 服务地址（用于注册文件下载）
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:8000/api/mcp")


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


@tool
def excel_to_markdown_table(
    excel_path: str,
    sheet: str = "Sheet1",
    max_rows: int = 200,
    max_cols: int = 20,
    include_index: bool = False,
    output_path: Optional[str] = None,
    save_to_file: bool = True,
) -> dict:
    """将指定 Excel 工作表转换为 Markdown 表格。

    Args:
        excel_path: Excel 文件路径，支持本地文件。
        sheet: 工作表名称，或工作表索引（以字符串形式传递数字，例如 "0"）。
        max_rows: 输出前多少行，避免过大结果，默认 200。
        max_cols: 输出前多少列，避免过大结果，默认 20。
        include_index: 是否在 Markdown 中包含行索引。
        output_path: 可选的输出文件路径，若提供则会写入文件。
        save_to_file: 是否保存到文件（默认 True），保存后可获取 download_url。

    Returns:
        包含转换结果的字典：
        - success: 是否成功
        - markdown: Markdown 表格内容
        - file_path: 保存的文件路径（如果 save_to_file=True）
        - download_url: 文件下载链接（如果 save_to_file=True）
        - message: 状态信息
        - rows: 实际输出的行数
        - cols: 实际输出的列数
    """
    try:
        import pandas as pd
    except Exception as exc:
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：缺少 pandas 依赖，无法处理 Excel 文件（{exc}）"
        }

    if not excel_path:
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": "错误：请提供有效的 Excel 文件路径"
        }

    if not os.path.isfile(excel_path):
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：文件不存在或不可访问 - {excel_path}"
        }

    sheet_name: str | int = sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet_name = int(sheet)

    if max_rows <= 0 or max_cols <= 0:
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": "错误：max_rows 与 max_cols 需为正整数"
        }

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except FileNotFoundError:
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：找不到文件 - {excel_path}"
        }
    except ValueError as exc:
        return {
            "success": False,
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：读取工作表失败 - {exc}"
        }
    except Exception as exc:
        return {
            "success": False,
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
            "markdown": None,
            "file_path": None,
            "download_url": None,
            "message": f"错误：转换为 Markdown 失败 - {exc}"
        }

    if notes:
        markdown = markdown + "\n\n" + "；".join(notes)

    # 处理文件保存
    file_path = None
    download_url = None
    
    if save_to_file or output_path:
        if output_path is None:
            import tempfile
            import uuid
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
                "markdown": markdown,
                "file_path": None,
                "download_url": None,
                "message": f"错误：写入输出文件失败 - {exc}"
            }

    return {
        "success": True,
        "markdown": markdown,
        "file_path": file_path,
        "download_url": download_url,
        "message": f"转换成功，输出 {len(df)} 行 × {df.shape[1]} 列",
        "rows": len(df),
        "cols": df.shape[1]
    }


if __name__ == "__main__":
    # 测试示例
    import tempfile
    import pandas as pd
    
    # 创建测试 Excel 文件
    test_excel = os.path.join(tempfile.gettempdir(), "test_excel.xlsx")
    test_df = pd.DataFrame({
        "姓名": ["张三", "李四", "王五"],
        "年龄": [25, 30, 28],
        "部门": ["技术部", "市场部", "财务部"],
        "工资": [15000, 12000, 13000]
    })
    test_df.to_excel(test_excel, index=False)
    
    # 测试转换
    result = excel_to_markdown_table.invoke({
        "excel_path": test_excel,
        "sheet": "Sheet1"
    })
    
    print(result)
    if result["success"]:
        print("\n=== Markdown 内容 ===")
        print(result["markdown"])
        print(f"\n文件路径: {result['file_path']}")
        print(f"下载链接: {result['download_url']}")