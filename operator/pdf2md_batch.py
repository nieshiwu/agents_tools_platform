"""PDF 转 Markdown 工具 - 支持单文件和多文件输入

将 PDF 文件转换为 Markdown 格式。
主要使用 pymupdf4llm 进行高质量转换，该库能够很好地保留文档结构、表格和图片。
"""
import os
import tempfile
import uuid
import requests
from typing import Optional, List, Dict

from langchain_core.tools import tool

# MCP 服务地址（用于注册文件下载）
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:7000/api/mcp")

# 支持的 PDF 文件扩展名
PDF_EXTENSIONS = ('.pdf',)


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


def _validate_pdf_file(path: str) -> Optional[str]:
    """验证并返回有效的 PDF 文件路径"""
    if os.path.isfile(path) and path.lower().endswith(PDF_EXTENSIONS):
        return os.path.abspath(path)
    return None


def _convert_with_pymupdf4llm(pdf_path: str, output_path: str) -> tuple:
    """使用 pymupdf4llm 转换（推荐，支持布局分析和表格提取）"""
    try:
        import pymupdf4llm
        import pathlib
        
        # 转换 PDF 为 Markdown
        md_text = pymupdf4llm.to_markdown(pdf_path)
        
        # 写入文件
        pathlib.Path(output_path).write_bytes(md_text.encode())
        
        if os.path.exists(output_path):
            return True, None
        else:
            return False, "转换后未生成 .md 文件"
            
    except ImportError:
        return False, "未安装 pymupdf4llm，请执行: pip install pymupdf4llm"
    except Exception as e:
        return False, f"pymupdf4llm 转换异常: {str(e)}"


def _convert_single_pdf(
    pdf_path: str,
    output_path: Optional[str] = None,
) -> dict:
    """转换单个 PDF 文件为 Markdown（内部函数）"""
    
    if not os.path.isfile(pdf_path):
        return {
            "success": False,
            "source_file": pdf_path,
            "md_path": None,
            "download_url": None,
            "message": f"错误：文件不存在 - {pdf_path}"
        }
    
    ext = os.path.splitext(pdf_path)[1].lower()
    if ext not in PDF_EXTENSIONS:
        return {
            "success": False,
            "source_file": pdf_path,
            "md_path": None,
            "download_url": None,
            "message": f"错误：不支持的文件格式 '{ext}'，仅支持 .pdf"
        }
    
    # 确定输出路径
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"{base_name}_{uuid.uuid4().hex[:8]}.md"
        )
    
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 执行转换 (目前只支持 pymupdf4llm，因为效果最好)
    success, error = _convert_with_pymupdf4llm(pdf_path, output_path)
    
    if not success:
        return {
            "success": False,
            "source_file": pdf_path,
            "md_path": None,
            "download_url": None,
            "message": f"转换失败: {error}",
            "converter_used": "pymupdf4llm"
        }
    
    download_url = register_file_download(output_path)
    
    result = {
        "success": True,
        "source_file": pdf_path,
        "md_path": output_path,
        "download_url": download_url,
        "message": f"转换成功：{os.path.basename(pdf_path)} -> {os.path.basename(output_path)}",
        "converter_used": "pymupdf4llm",
        "file_size_kb": round(os.path.getsize(output_path) / 1024, 2)
    }
    
    return result


@tool
def pdf_to_markdown(
    input_path: str,
    output_dir: Optional[str] = None,
) -> dict:
    """将 PDF 文件转换为 Markdown 格式。
    
    支持单个或多个文件输入。使用 pymupdf4llm 引擎，能够保留良好的文档结构、表格和图片位置。

    Args:
        input_path: 输入文件路径，支持：
            - 单个文件："/path/to/file.pdf"
            - 多个文件（逗号分隔）："/path/file1.pdf, /path/file2.pdf"
        output_dir: 输出目录，若不指定则使用临时目录。

    Returns:
        包含转换结果的字典。
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
    
    # 解析输入路径（支持逗号分隔）
    input_paths = [p.strip() for p in input_path.split(',') if p.strip()]
    
    # 验证并收集所有 PDF 文件
    all_pdf_files = []
    invalid_paths = []
    for path in input_paths:
        valid_path = _validate_pdf_file(path)
        if valid_path:
            all_pdf_files.append(valid_path)
        else:
            invalid_paths.append(path)
    
    all_pdf_files = sorted(set(all_pdf_files))
    
    if not all_pdf_files:
        error_msg = f"错误：未找到有效的 PDF 文件（输入：{input_path}）"
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
        output_dir = os.path.join(tempfile.gettempdir(), f"pdf2md_{uuid.uuid4().hex[:8]}")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 处理所有文件
    results = []
    processed = 0
    failed = 0
    
    for pdf_file in all_pdf_files:
        base_name = os.path.splitext(os.path.basename(pdf_file))[0]
        output_path = os.path.join(output_dir, f"{base_name}.md")
        
        # 避免文件名冲突
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{base_name}_{counter}.md")
            counter += 1
        
        result = _convert_single_pdf(
            pdf_path=pdf_file,
            output_path=output_path,
        )
        
        results.append(result)
        
        if result["success"]:
            processed += 1
        else:
            failed += 1
    
    # 构建返回结果
    success = failed == 0 and processed > 0
    
    # 构建文件映射列表
    file_mappings = []
    for r in results:
        if r["success"]:
            file_mappings.append({
                "source": r["source_file"],
                "output": r["md_path"],
                "download_url": r["download_url"],
            })
    
    response = {
        "success": success,
        "total_files": len(all_pdf_files),
        "processed": processed,
        "failed": failed,
        "results": results,
        "file_mappings": file_mappings,
        "output_dir": output_dir,
        "message": f"转换完成：共 {len(all_pdf_files)} 个文件，成功 {processed} 个，失败 {failed} 个"
    }
    
    # 单文件时返回简化结果
    if len(all_pdf_files) == 1:
        single = results[0]
        response.update({
            "md_path": single.get("md_path"),
            "download_url": single.get("download_url"),
            "file_size_kb": single.get("file_size_kb"),
            "message": single.get("message"),
        })
    
    return response


if __name__ == "__main__":
    # 创建测试 PDF 文件
    try:
        import fitz  # PyMuPDF
        
        test_dir = os.path.join(tempfile.gettempdir(), "pdf2md_test")
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
            
        test_file = os.path.join(test_dir, "test.pdf")
        
        doc = fitz.open()
        page = doc.new_page()
        
        # 添加文本
        page.insert_text((50, 50), "Test PDF Document", fontsize=20)
        page.insert_text((50, 100), "This is a test document for PDF to Markdown conversion.", fontsize=12)
        
        # 添加表格线
        page.draw_rect((50, 150, 300, 250))
        page.draw_line((50, 200), (300, 200))
        page.draw_line((175, 150), (175, 250))
        
        # 添加表格内容
        page.insert_text((60, 180), "Header 1", fontsize=12)
        page.insert_text((185, 180), "Header 2", fontsize=12)
        page.insert_text((60, 230), "Cell 1", fontsize=12)
        page.insert_text((185, 230), "Cell 2", fontsize=12)
        
        doc.save(test_file)
        doc.close()
        
        print(f"\n=== 测试单文件: {test_file} ===")
        result = pdf_to_markdown.invoke({"input_path": test_file})
        print(f"成功: {result['success']}")
        print(f"消息: {result['message']}")
        print(f"下载链接: {result.get('download_url')}")
        print(f"输出文件: {result.get('md_path')}")
        
        # 验证输出
        if result['success'] and result.get('md_path'):
            with open(result['md_path'], 'r', encoding='utf-8') as f:
                print("\n=== Markdown 内容预览 ===")
                print(f.read()[:500])
        
    except ImportError:
        print("请先安装 pymupdf: pip install pymupdf")
