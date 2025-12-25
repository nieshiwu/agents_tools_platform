"""Excel 转 Markdown 工具"""

import os
from typing import Optional

from langchain_core.tools import tool


@tool
def excel_to_markdown_table(
    excel_path: str,
    sheet: str = "Sheet1",
    max_rows: int = 200,
    max_cols: int = 20,
    include_index: bool = False,
    output_path: Optional[str] = None,
) -> str:
    """将指定 Excel 工作表转换为 Markdown 表格。

    Args:
        excel_path: Excel 文件路径，支持本地文件。
        sheet: 工作表名称，或工作表索引（以字符串形式传递数字，例如 "0"）。
        max_rows: 输出前多少行，避免过大结果，默认 200。
        max_cols: 输出前多少列，避免过大结果，默认 20。
        include_index: 是否在 Markdown 中包含行索引。
        output_path: 可选的输出文件路径，若提供则会写入文件。

    Returns:
        Markdown 表格字符串；如发生错误返回可读的错误提示。
    """
    try:
        import pandas as pd  # 延迟导入，便于捕获缺失依赖
    except Exception as exc:  # pragma: no cover - 仅在依赖缺失时触发
        return f"错误：缺少 pandas 依赖，无法处理 Excel 文件（{exc}）"

    if not excel_path:
        return "错误：请提供有效的 Excel 文件路径"

    if not os.path.isfile(excel_path):
        return f"错误：文件不存在或不可访问 - {excel_path}"

    sheet_name: str | int = sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet_name = int(sheet)

    if max_rows <= 0 or max_cols <= 0:
        return "错误：max_rows 与 max_cols 需为正整数"

    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except FileNotFoundError:
        return f"错误：找不到文件 - {excel_path}"
    except ValueError as exc:  # 包含工作表不存在等场景
        return f"错误：读取工作表失败 - {exc}"
    except Exception as exc:
        return f"错误：读取 Excel 失败 - {exc}"

    notes: list[str] = []
    if len(df) > max_rows:
        df = df.head(max_rows)
        notes.append(f"已截取前 {max_rows} 行")

    if df.shape[1] > max_cols:
        df = df.iloc[:, :max_cols]
        notes.append(f"已截取前 {max_cols} 列")

    try:
        markdown = df.to_markdown(index=include_index)
    except Exception as exc:
        return f"错误：转换为 Markdown 失败 - {exc}"

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as md_file:
                md_file.write(markdown)
        except Exception as exc:
            return f"错误：写入输出文件失败 - {exc}"

    if notes:
        markdown = markdown + "\n\n" + "；".join(notes)

    return markdown