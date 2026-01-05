"""Agent 调用 ppt_to_pdf 工具进行 PPT 转 PDF。

支持：
- 单文件转换：上传一个 PPT，生成一个 PDF
- 多文件转换：上传多个 PPT，生成多个 PDF（一对一）

流程：
1. 本地文件上传到服务器
2. 调用 MCP 工具，传入服务器路径
3. 获取转换结果和下载链接

Run:
    python -m tests.agent_ppt2pdf_batch_mcp

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

# 尝试导入 python-pptx 用于创建示例文件
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False


load_dotenv()
# MCP_API_BASE = os.getenv("MCP_API_BASE", "http://192.168.0.197:8000/api")
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:7000/api")
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
        """调用 MCP 工具进行 PPT 转 PDF。
        
        Args:
            input_path: 服务器上的文件路径，支持：
                - 单个文件: "/app/temp_uploads/xxx.pptx"
                - 多个文件（逗号分隔）: "/app/temp_uploads/a.pptx, /app/temp_uploads/b.pptx"
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


def _prepare_sample_ppt_files(tmp_dir: Path, count: int = 3) -> List[Path]:
    """创建多个示例 PPT 文件"""
    if not PPTX_AVAILABLE:
        raise RuntimeError("需要安装 python-pptx: pip install python-pptx")
    
    files = []
    for i in range(count):
        prs = Presentation()
        
        # 添加标题页
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = f"示例演示文稿 {i+1}"
        subtitle.text = f"这是第 {i+1} 个测试 PPT 文件"
        
        # 添加内容页
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        shapes = slide.shapes
        title_shape = shapes.title
        body_shape = shapes.placeholders[1]
        title_shape.text = f"内容页面 - 文件 {i+1}"
        tf = body_shape.text_frame
        tf.text = f"第一点：这是文件 {i+1} 的内容"
        p = tf.add_paragraph()
        p.text = f"第二点：编号 {i+1}"
        p.level = 1
        
        ppt_path = tmp_dir / f"demo_{i+1}.pptx"
        prs.save(ppt_path)
        files.append(ppt_path)
    
    return files


def _prepare_sample_ppt(tmp_dir: Path) -> Path:
    """创建单个示例 PPT 文件（向后兼容）"""
    return _prepare_sample_ppt_files(tmp_dir, count=1)[0]


def _upload_file_to_server(file_path: Path) -> str:
    """上传文件到 MCP 服务器，返回服务器上的文件路径"""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
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
    # 支持新旧工具名
    target = next((t for t in tools_meta if t.get("name") in ("ppt_to_pdf_batch")), None)
    if not target:
        raise RuntimeError("ppt_to_pdf 工具未在 MCP 服务器上找到，请先上传/启用该工具。")

    ppt_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[ppt_tool],
        system_prompt="""You are a helpful assistant for PPT to PDF conversion.

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

For single file, also returns: pdf_path, download_url, slide_count, file_size_kb

Always report the download_url(s) to the user so they can download the converted PDF files.""",
    )

    # 选择演示模式: single（单文件）或 multi（多文件）
    demo_mode = os.getenv("DEMO_MODE", "single")
    
    tmp_dir = Path(tempfile.mkdtemp())
    
    if demo_mode == "multi":
        # 多文件模式
        print("=== 多文件转换模式 ===")
        
        # 方式1：使用指定目录下的文件
        local_ppt_dir = Path(r"D:\workspace\tools_platform\file\22")
        if local_ppt_dir.exists():
            local_files = list(local_ppt_dir.glob("*.pptx")) + list(local_ppt_dir.glob("*.ppt"))
        else:
            # 方式2：创建测试文件
            print("创建测试 PPT 文件...")
            local_files = _prepare_sample_ppt_files(tmp_dir, count=3)
        
        print(f"待处理文件: {len(local_files)} 个")
        print("正在上传文件到服务器...")
        server_paths = _upload_files_to_server(local_files)
        server_paths_str = ", ".join(server_paths)
        
        user_msg = (
            f"请把这些 PPT 文件转成 PDF: {server_paths_str}\n"
            "每个 PPT 文件生成一个对应的 PDF 文件。\n"
            "请告诉我每个文件的转换结果和下载链接。"
        )
    else:
        # 单文件模式（默认）
        print("=== 单文件转换模式 ===")
        
        # 尝试使用本地文件
        local_ppt_path = Path(r"C:\Users\niesh\Desktop\22\aaaa.pptx")
        if not local_ppt_path.exists():
            print("创建测试 PPT 文件...")
            local_ppt_path = _prepare_sample_ppt(tmp_dir)
        
        print(f"正在上传文件到服务器: {local_ppt_path}")
        server_ppt_path = _upload_file_to_server(local_ppt_path)
        print(f"文件已上传，服务器路径: {server_ppt_path}")
        
        user_msg = (
            f"请把这个 PPT 转成 PDF: {server_ppt_path}\n"
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
