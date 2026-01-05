"""Minimal agent that calls the ppt_to_pdf tool via MCP.

Run:
    python -m tests.agent_ppt2pdf_mcp

Prerequisites:
    - Backend running (e.g., `python run.py all` or uvicorn entrypoint).
    - Tool `ppt_to_pdf` uploaded/valid on the MCP server.
    - python-pptx installed (used by this script to create a sample PPT).
    - Environment variable DASHSCOPE_API_KEY set (or adjust init_chat_model accordingly).
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

# 尝试导入 python-pptx，如果不可用则使用备选方案
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RgbColor
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False


load_dotenv()
# MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:7000/api")
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://192.168.0.197:8000/api")
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
            timeout=600,  # PDF转换可能需要更长时间，增加到10分钟
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
        ppt_path: str,
        output_path: str | None = None,
        converter: str = "auto",
    ) -> str:
        """Call MCP tool with explicit parameters."""

        arguments: Dict[str, Any] = {
            "ppt_path": ppt_path,
            "converter": converter,
        }
        if output_path:
            arguments["output_path"] = output_path

        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )

def _upload_file_to_server(file_path: Path) -> str:
    """上传文件到 MCP 服务器，返回服务器上的文件路径"""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        resp = requests.post(f"{MCP_API_BASE}/mcp/files/upload", files=files, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"文件上传失败: {data.get('message')}")
        return data["file_path"]


def main() -> None:
    model = init_chat_model(model=MODEL_NAME, api_key=API_KEY)
    mcp_client = MCPClient(MCP_API_BASE)

    tools_meta = mcp_client.list_tools()
    target = next((t for t in tools_meta if t.get("name") == "ppt_to_pdf"), None)
    if not target:
        raise RuntimeError("ppt_to_pdf not found on MCP server; please upload/enable it first.")

    ppt_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[ppt_tool],
        system_prompt="""You are a helpful assistant. When the user provides a PPT/PPTX path, convert it to PDF by calling the tool.
The tool returns a JSON with:
- success: whether conversion succeeded
- pdf_path: the generated PDF file path
- download_url: URL to download the PDF file (can be shared with others)
- message: status message
- converter_used: which converter was used (libreoffice/comtypes/python)
- slides_count: number of slides (when using python converter)

Always report the download_url to the user so they can access the converted PDF file.""",
    )

    local_ppt_path = Path(r"D:\公司内部\FDE\上下文工程综述\11.pptx")
    
    # 上传文件到服务器
    print(f"正在上传文件到服务器: {local_ppt_path}")
    server_ppt_path = _upload_file_to_server(local_ppt_path)
    print(f"文件已上传，服务器路径: {server_ppt_path}")

    user_msg = (
        f"请把这个 PPT 转成 PDF: {server_ppt_path}\n"
        "请告诉我转换结果，包括 PDF 文件的下载链接。"
    )

    print("=== User Request ===")
    print(user_msg)
    print()

    response = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})

    print("\n=== Agent trace ===")
    for idx, msg in enumerate(response.get("messages", []), start=1):
        role = type(msg).__name__
        content = getattr(msg, "content", msg)
        # 截断过长内容
        if isinstance(content, str) and len(content) > 500:
            content = content[:500] + "..."
        print(f"[{idx}] {role} -> {content}")

    final_msg = response.get("messages", [])[-1]
    print("\n=== Final reply ===")
    print(getattr(final_msg, "content", final_msg))


if __name__ == "__main__":
    main()
