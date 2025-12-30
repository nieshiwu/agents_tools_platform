"""
DOC/DOCX 转 PDF 工具

将 Word 文档转换为 PDF 格式。
依赖：docx2pdf (Windows 需要安装 Microsoft Word)
安装：pip install docx2pdf
"""
import os
import base64
import requests
from typing import Optional
from langchain_core.tools import tool

# MCP 服务地址（用于注册文件下载）
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:7000/api/mcp")


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
def doc_to_pdf(
    doc_path: str,
    output_path: Optional[str] = None,
    return_base64: bool = False
) -> dict:
    """将 DOC/DOCX 文件转换为 PDF 格式

    Args:
        doc_path: Word 文档的完整路径，支持 .doc 和 .docx 格式
        output_path: PDF 输出路径，默认与源文件同目录同名
        return_base64: 是否返回 PDF 的 Base64 编码内容，默认 False

    Returns:
        包含转换结果的字典：
        - success: 是否成功
        - pdf_path: 生成的 PDF 文件路径（服务器本地）
        - download_url: 远程可访问的下载链接
        - message: 结果消息
        - base64_content: (可选) PDF 的 Base64 编码内容
    """
    try:
        # 检查源文件是否存在
        if not os.path.exists(doc_path):
            return {
                "success": False,
                "pdf_path": None,
                "download_url": None,
                "message": f"错误：文件不存在 - {doc_path}"
            }

        # 检查文件扩展名
        ext = os.path.splitext(doc_path)[1].lower()
        if ext not in ['.doc', '.docx']:
            return {
                "success": False,
                "pdf_path": None,
                "download_url": None,
                "message": f"错误：不支持的文件格式 '{ext}'，仅支持 .doc 和 .docx"
            }

        # 确定输出路径
        if output_path is None:
            output_path = os.path.splitext(doc_path)[0] + '.pdf'

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 执行转换
        from docx2pdf import convert
        convert(doc_path, output_path)

        # 检查转换结果
        if not os.path.exists(output_path):
            return {
                "success": False,
                "pdf_path": None,
                "download_url": None,
                "message": "错误：转换失败，未生成 PDF 文件"
            }

        # 注册文件获取下载 URL
        download_url = register_file_download(output_path)

        result = {
            "success": True,
            "pdf_path": output_path,
            "download_url": download_url,
            "message": f"转换成功：{doc_path} -> {output_path}",
            "file_size_kb": round(os.path.getsize(output_path) / 1024, 2)
        }

        # 如果需要返回 Base64 内容
        if return_base64:
            with open(output_path, 'rb') as f:
                pdf_bytes = f.read()
            result["base64_content"] = base64.b64encode(pdf_bytes).decode('utf-8')

        return result

    except ImportError:
        return {
            "success": False,
            "pdf_path": None,
            "download_url": None,
            "message": "错误：请先安装 docx2pdf 库 (pip install docx2pdf)，Windows 还需安装 Microsoft Word"
        }
    except Exception as e:
        return {
            "success": False,
            "pdf_path": None,
            "download_url": None,
            "message": f"错误：转换过程中出现异常 - {str(e)}"
        }


@tool
def batch_doc_to_pdf(
    doc_paths: list,
    output_dir: Optional[str] = None
) -> dict:
    """批量将多个 DOC/DOCX 文件转换为 PDF 格式

    Args:
        doc_paths: Word 文档路径列表
        output_dir: PDF 输出目录，默认与各源文件同目录

    Returns:
        包含批量转换结果的字典：
        - success: 是否全部成功
        - total: 总文件数
        - converted: 成功转换数
        - failed: 失败数
        - results: 各文件转换详情列表（含 download_url）
    """
    results = []
    converted = 0
    failed = 0

    for doc_path in doc_paths:
        # 确定输出路径
        if output_dir:
            filename = os.path.splitext(os.path.basename(doc_path))[0] + '.pdf'
            output_path = os.path.join(output_dir, filename)
        else:
            output_path = None

        # 调用单文件转换
        result = doc_to_pdf.invoke({
            "doc_path": doc_path,
            "output_path": output_path,
            "return_base64": False
        })

        results.append({
            "source": doc_path,
            "result": result
        })

        if result["success"]:
            converted += 1
        else:
            failed += 1

    return {
        "success": failed == 0,
        "total": len(doc_paths),
        "converted": converted,
        "failed": failed,
        "results": results
    }


# 测试代码
if __name__ == "__main__":
    # 单文件测试
    test_doc = r"D:\test\sample.docx"
    if os.path.exists(test_doc):
        result = doc_to_pdf.invoke({"doc_path": test_doc})
        print(result)
    else:
        print(f"测试文件不存在: {test_doc}")
        print("工具已加载成功，可上传到平台使用")
