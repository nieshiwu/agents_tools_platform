"""Agent 调用 word_to_pdf 工具进行 Word 转 PDF。

支持：
- 单文件转换：上传一个 Word 文档，生成一个 PDF
- 多文件转换：上传多个 Word 文档，生成多个 PDF（一对一）

流程：
1. 本地文件上传到服务器
2. 调用 MCP 工具，传入服务器路径
3. 获取转换结果和下载链接

Run:
    python -m tests.agent_word2pdf_batch_mcp

环境变量：
    DEMO_MODE: single（单文件）或 multi（多文件），默认 single
    MCP_API_BASE: MCP 服务地址
    DASHSCOPE_API_KEY: LLM API Key
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool

# 尝试导入 python-docx 用于创建示例文件
try:
    from docx import Document
    from docx.shared import Inches, Pt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


load_dotenv()
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://192.168.0.197:8000/api")
# MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:7000/api")
MODEL_NAME = os.getenv("AGENT_MODEL", "openai:deepseek-v3")
API_KEY = os.getenv("DASHSCOPE_API_KEY")


class MCPClient:
    """Thin MCP protocol client for tool discovery and invocation."""

    def __init__(self, base_url: str = MCP_API_BASE):
        self.base_url = base_url.rstrip("/")

    def list_tools(self) -> List[Dict[str, Any]]:
        resp = requests.post(f"{self.base_url}/mcp/protocol/tools/list", timeout=10)
        resp.raise_for_status()
        return resp.json().get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        payload = {"name": name, "arguments": arguments}
        resp = requests.post(
            f"{self.base_url}/mcp/protocol/tools/call",
            json=payload,
            timeout=600,  # PDF转换可能需要较长时间
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("isError"):
            content = data.get("content", [])
            error_text = "".join(c.get("text", "") for c in content)
            raise RuntimeError(f"MCP tool error: {error_text}")

        content = data.get("content", [])
        return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def mcp_tool_to_langchain(mcp_client: MCPClient, tool_info: Dict[str, Any]) -> StructuredTool:
    """Convert MCP tool metadata to a LangChain StructuredTool."""
    name = tool_info["name"]
    description = tool_info.get("description", f"Tool: {name}")
    input_schema = tool_info.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    args_desc: List[str] = []
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "")
        req = "(required)" if param_name in required else "(optional)"
        args_desc.append(f"- {param_name} ({param_type}) {req}: {param_desc}")

    if args_desc:
        description = description + "\nParameters:\n" + "\n".join(args_desc)

    def _call_mcp_tool(
        input_path: str,
        converter: str = "auto",
    ) -> str:
        """调用 MCP 工具进行 Word 转 PDF。
        
        Args:
            input_path: 服务器上的文件路径，支持：
                - 单个文件: "/app/temp_uploads/xxx.docx"
                - 多个文件（逗号分隔）: "/app/temp_uploads/a.docx, /app/temp_uploads/b.doc"
            converter: 转换器选择（auto/libreoffice/comtypes/python）
        """
        arguments: Dict[str, Any] = {
            "input_path": input_path,
            "converter": converter,
        }
        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )


def _prepare_sample_doc_files(tmp_dir: Path, count: int = 3) -> List[Path]:
    """创建多个示例 Word 文件"""
    if not DOCX_AVAILABLE:
        raise RuntimeError("需要安装 python-docx: pip install python-docx")
    
    files = []
    for i in range(count):
        doc = Document()
        
        # 添加标题
        doc.add_heading(f'示例文档 {i+1}', 0)
        
        # 添加段落
        doc.add_paragraph(f'这是第 {i+1} 个测试 Word 文档。')
        doc.add_paragraph('本文档用于测试 Word 转 PDF 功能。')
        
        # 添加列表
        doc.add_heading('功能特点', level=1)
        doc.add_paragraph('支持单文件转换', style='List Bullet')
        doc.add_paragraph('支持多文件批量转换', style='List Bullet')
        doc.add_paragraph('自动选择最佳转换器', style='List Bullet')
        
        # 添加表格
        doc.add_heading('数据表格', level=1)
        table = doc.add_table(rows=4, cols=3)
        table.style = 'Table Grid'
        
        # 表头
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '序号'
        hdr_cells[1].text = '名称'
        hdr_cells[2].text = '数值'
        
        # 数据行
        for j in range(1, 4):
            row_cells = table.rows[j].cells
            row_cells[0].text = str(j)
            row_cells[1].text = f'项目{j}'
            row_cells[2].text = str(100 + i * 10 + j)
        
        doc_path = tmp_dir / f"demo_{i+1}.docx"
        doc.save(doc_path)
        files.append(doc_path)
    
    return files


def _prepare_sample_doc(tmp_dir: Path) -> Path:
    """创建单个示例 Word 文件（向后兼容）"""
    return _prepare_sample_doc_files(tmp_dir, count=1)[0]


def _upload_file_to_server(file_path: Path) -> str:
    """上传文件到 MCP 服务器，返回服务器上的文件路径"""
    # 根据文件扩展名确定 MIME 类型
    ext = file_path.suffix.lower()
    if ext == '.docx':
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        mime_type = "application/msword"
    
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, mime_type)}
        resp = requests.post(f"{MCP_API_BASE}/mcp/files/upload", files=files, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"文件上传失败: {data.get('message')}")
        return data["file_path"]


def _upload_files_to_server(file_paths: List[Path]) -> List[str]:
    """批量上传文件到服务器，返回服务器路径列表"""
    server_paths = []
    for file_path in file_paths:
        server_path = _upload_file_to_server(file_path)
        server_paths.append(server_path)
        print(f"  已上传: {file_path.name} -> {server_path}")
    return server_paths


def main() -> None:
    """主函数：演示单文件和多文件转换"""
    model = init_chat_model(model=MODEL_NAME, api_key=API_KEY)
    mcp_client = MCPClient(MCP_API_BASE)

    tools_meta = mcp_client.list_tools()
    # 查找 word_to_pdf 工具
    target = next((t for t in tools_meta if t.get("name") == "word_to_pdf_batch"), None)
    if not target:
        raise RuntimeError("word_to_pdf 工具未在 MCP 服务器上找到，请先上传/启用该工具。")

    word_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[word_tool],
        system_prompt="""You are a helpful assistant for Word to PDF conversion.

The tool accepts:
- input_path: Server file path(s). Single file or comma-separated multiple files.
- converter: Converter to use (auto/libreoffice/comtypes/python)

The tool returns JSON with:
- success: whether conversion succeeded
- total_files: number of files processed  
- processed: successful count
- failed: failed count
- file_mappings: list of {source, output, download_url} for each file
- converter_used: which converter was used
- message: status message

For single file, also returns: pdf_path, download_url, page_count, file_size_kb

Always report the download_url(s) to the user so they can download the converted PDF files.""",
    )

    # 选择演示模式: single（单文件）或 multi（多文件）
    demo_mode = os.getenv("DEMO_MODE", "multi")
    
    tmp_dir = Path(tempfile.mkdtemp())
    
    if demo_mode == "multi":
        # 多文件模式
        print("=== 多文件转换模式 ===")
        
        # 方式1：使用指定目录下的文件
        local_doc_dir = Path(r"D:\workspace\tools_platform\file\33")
        if local_doc_dir.exists():
            local_files = list(local_doc_dir.glob("*.docx")) + list(local_doc_dir.glob("*.doc"))
        else:
            # 方式2：创建测试文件
            print("创建测试 Word 文件...")
            local_files = _prepare_sample_doc_files(tmp_dir, count=3)
        
        print(f"待处理文件: {len(local_files)} 个")
        print("正在上传文件到服务器...")
        server_paths = _upload_files_to_server(local_files)
        server_paths_str = ", ".join(server_paths)
        
        user_msg = (
            f"请把这些 Word 文件转成 PDF: {server_paths_str}\n"
            "每个 Word 文件生成一个对应的 PDF 文件。\n"
            "请告诉我每个文件的转换结果和下载链接。"
        )
    else:
        # 单文件模式（默认）
        print("=== 单文件转换模式 ===")
        
        # 尝试使用本地文件
        local_doc_path = Path(r"D:\test\sample.docx")
        if not local_doc_path.exists():
            print("创建测试 Word 文件...")
            local_doc_path = _prepare_sample_doc(tmp_dir)
        
        print(f"正在上传文件到服务器: {local_doc_path}")
        server_doc_path = _upload_file_to_server(local_doc_path)
        print(f"文件已上传，服务器路径: {server_doc_path}")
        
        user_msg = (
            f"请把这个 Word 文档转成 PDF: {server_doc_path}\n"
            "请告诉我转换结果，包括 PDF 文件的下载链接。"
        )

    print("\n=== User Request ===")
    print(user_msg)
    print()

    response = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})

    print("\n=== Agent trace ===")
    for idx, msg in enumerate(response.get("messages", []), start=1):
        role = type(msg).__name__
        content = getattr(msg, "content", msg)
        # 截断过长内容
        if isinstance(content, str) and len(content) > 800:
            content = content[:800] + "..."
        print(f"[{idx}] {role} -> {content}")


if __name__ == "__main__":
    main()
