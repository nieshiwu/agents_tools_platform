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
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:8000/api")
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
    ) -> str:
        """Call MCP tool with explicit parameters (avoids empty-arg failures)."""

        arguments: Dict[str, Any] = {
            "excel_path": excel_path,
            "sheet": sheet,
            "max_rows": max_rows,
            "max_cols": max_cols,
            "include_index": include_index,
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
    df = pd.DataFrame({"city": ["Beijing", "Shanghai", "Shenzhen"], "score": [90, 95, 93]})
    excel_path = tmp_dir / "demo.xlsx"
    df.to_excel(excel_path, index=False, sheet_name="Sheet1")
    return excel_path


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
        system_prompt="You are a helpful assistant. When the user provides an Excel path, convert it to markdown by calling the tool.",
    )

    tmp_dir = Path(tempfile.mkdtemp())
    # excel_path = _prepare_sample_excel(tmp_dir)
    excel_path = "C:\\Users\\niesh\\Desktop\\111.xlsx"

    user_msg = (
        "请把这个 Excel 转成 Markdown 表格，只保留前 5 行。"  # instruction in Chinese
        f" 文件路径: {excel_path}，工作表: Sheet1。，请只返回 Markdown 内容，并保存在C:\\Users\\niesh\\Desktop\\output.md。"
        
    
    )

    response = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})

    print("\n=== Agent trace ===")
    for idx, msg in enumerate(response.get("messages", []), start=1):
        print(f"[{idx}] {type(msg).__name__} -> {getattr(msg, 'content', msg)}")

    final_msg = response.get("messages", [])[-1]
    print("\n=== Final reply ===")
    print(getattr(final_msg, "content", final_msg))


if __name__ == "__main__":
    main()
