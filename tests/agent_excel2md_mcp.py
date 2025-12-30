"""Minimal agent that calls the excel_to_markdown_table tool via MCP.

Run:
    python -m tests.agent_excel2md_mcp

Prerequisites:
    - Backend running (e.g., `python run.py all` or uvicorn entrypoint).
    - Tool `excel_to_markdown_table` uploaded/valid on the MCP server.
    - pandas/tabulate installed (used by the tool and this script to create a sample Excel).
    - Environment variable DASHSCOPE_API_KEY set (or adjust init_chat_model accordingly).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool


load_dotenv()
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://192.168.0.197:7000/api")
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
            timeout=60,
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
        excel_path: str,
        sheet: str = "Sheet1",
        max_rows: int = 200,
        max_cols: int = 20,
        include_index: bool = False,
        output_path: str | None = None,
        save_to_file: bool = True,
    ) -> str:
        """Call MCP tool with explicit parameters (avoids empty-arg failures)."""

        arguments: Dict[str, Any] = {
            "excel_path": excel_path,
            "sheet": sheet,
            "max_rows": max_rows,
            "max_cols": max_cols,
            "include_index": include_index,
            "save_to_file": save_to_file,
        }
        if output_path:
            arguments["output_path"] = output_path

        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )


def _prepare_sample_excel(tmp_dir: Path) -> Path:
    df = pd.DataFrame({
        "城市": ["北京", "上海", "深圳", "广州", "杭州"],
        "人口(万)": [2154, 2487, 1756, 1530, 1220],
        "GDP(亿)": [41610, 47218, 32387, 28231, 18109],
        "增长率(%)": [5.2, 4.8, 6.1, 5.5, 7.2]
    })
    excel_path = tmp_dir / "demo.xlsx"
    df.to_excel(excel_path, index=False, sheet_name="Sheet1")
    return excel_path


def _upload_file_to_server(file_path: Path) -> str:
    """上传文件到 MCP 服务器，返回服务器上的文件路径"""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
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
    target = next((t for t in tools_meta if t.get("name") == "excel_to_markdown_table"), None)
    if not target:
        raise RuntimeError("excel_to_markdown_table not found on MCP server; please upload/enable it first.")

    excel_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[excel_tool],
        system_prompt="""You are a helpful assistant. When the user provides an Excel path, convert it to markdown by calling the tool.
The tool returns a JSON with:
- success: whether conversion succeeded
- markdown: the markdown table content  
- file_path: saved file path
- download_url: URL to download the file (can be shared with others)
- message: status message
- rows/cols: data dimensions

Always report the download_url to the user so they can access the file.""",
    )

    tmp_dir = Path(tempfile.mkdtemp())
    local_excel_path = _prepare_sample_excel(tmp_dir)
    
    # 上传文件到服务器
    print(f"正在上传文件到服务器: {local_excel_path}")
    server_excel_path = _upload_file_to_server(local_excel_path)
    print(f"文件已上传，服务器路径: {server_excel_path}")

    user_msg = (
        f"请把这个 Excel 转成 Markdown 表格: {server_excel_path}\n"
        "工作表名: Sheet1\n"
        "请告诉我转换结果，包括文件的下载链接。"
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


    # import requests
    # response = requests.get(download_url)
    # with open("local_chart.png", "wb") as f:
    #     f.write(response.content)