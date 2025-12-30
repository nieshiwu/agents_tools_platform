"""Minimal agent that calls the md_table_to_line_chart tool via MCP.

Run:
    python -m tests.agent_md2chart_mcp

Prerequisites:
    - Backend running (e.g., `python run.py all` or uvicorn entrypoint).
    - Tool `md_table_to_line_chart` uploaded/valid on the MCP server.
    - matplotlib/pandas installed (used by the tool).
    - Environment variable DASHSCOPE_API_KEY set (or adjust init_chat_model accordingly).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        x_labels: List[str],
        y_data: dict,
        title: Optional[str] = None,
        x_label: str = "X轴",
        y_label: str = "Y轴",
        output_path: Optional[str] = None,
        return_base64: bool = False,
    ) -> str:
        """Call MCP tool with explicit parameters for md_data_to_line_chart."""
        arguments: Dict[str, Any] = {
            "x_labels": x_labels,
            "y_data": y_data,
            "x_label": x_label,
            "y_label": y_label,
            "return_base64": return_base64,
        }
        if title:
            arguments["title"] = title
        if output_path:
            arguments["output_path"] = output_path

        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )


# 测试用的示例数据
SAMPLE_X_LABELS = ["1月", "2月", "3月", "4月", "5月", "6月"]
SAMPLE_Y_DATA = {
    "销售额": [100, 150, 200, 180, 220, 250],
    "利润": [20, 35, 50, 40, 60, 75],
    "成本": [80, 115, 150, 140, 160, 175]
}

SAMPLE_X_LABELS_2 = ["Q1", "Q2", "Q3", "Q4"]
SAMPLE_Y_DATA_2 = {
    "营收(万元)": [500, 620, 580, 750],
    "净利润(万元)": [80, 95, 88, 120]
}

SAMPLE_X_LABELS_2 = ["Q1", "Q2", "Q3", "Q4"]
SAMPLE_Y_DATA_2 = {
    "营收(万元)": [500, 620, 580, 750],
    "净利润(万元)": [80, 95, 88, 120]
}


def main() -> None:
    model = init_chat_model(model=MODEL_NAME, api_key=API_KEY)
    mcp_client = MCPClient(MCP_API_BASE)

    # 获取工具列表
    tools_meta = mcp_client.list_tools()
    print(f"可用工具数量: {len(tools_meta)}")
    for t in tools_meta:
        print(f"  - {t.get('name')}: {t.get('description', '')[:50]}...")

    # 查找 md_data_to_line_chart 工具
    target = next((t for t in tools_meta if t.get("name") == "md_data_to_line_chart"), None)
    if not target:
        raise RuntimeError("md_data_to_line_chart not found on MCP server; please upload/enable it first.")

    chart_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[chart_tool],
        system_prompt="""你是一个数据可视化助手。
当用户提供数据时，使用 md_data_to_line_chart 工具将其转换为折线图。
工具需要两个必填参数：
- x_labels: X轴标签列表，如 ["1月", "2月", "3月"]
- y_data: Y轴数据字典，键为系列名，值为数值列表，如 {"销售额": [100, 150, 200]}
可选参数包括 title（标题）、x_label（X轴名称）、y_label（Y轴名称）、output_path（输出路径）。
返回图表的生成结果，包括文件路径和下载链接（如果有）。
""",
    )

    # 测试场景 1：基础数据转图表
    print("\n" + "=" * 60)
    print("测试场景 1：将月度销售数据转为折线图")
    print("=" * 60)

    user_msg_1 = f"""请将以下数据转换为折线图，标题设为"2024年上半年销售趋势"：

X轴标签: {SAMPLE_X_LABELS}
Y轴数据: {SAMPLE_Y_DATA}

X轴名称设为"月份"，Y轴名称设为"金额(万元)"。
请告诉我图表生成的结果，包括文件路径和下载链接。
"""

    response = agent.invoke({"messages": [{"role": "user", "content": user_msg_1}]})

    print("\n=== Agent trace ===")
    for idx, msg in enumerate(response.get("messages", []), start=1):
        content = getattr(msg, 'content', msg)
        msg_type = type(msg).__name__ 
        # 截断过长的内容
        if isinstance(content, str) and len(content) > 500:
            content = content[:500] + "..."
        print(f"[{idx}] {msg_type} -> {content}")

    final_msg = response.get("messages", [])[-1]
    print("\n=== Final reply ===")
    print(getattr(final_msg, "content", final_msg))

    # 测试场景 2：指定输出路径
    print("\n" + "=" * 60)
    print("测试场景 2：季度数据可视化并指定输出路径")
    print("=" * 60)

    output_path = "C:\\Users\\niesh\\Desktop\\quarterly_chart.png"
    user_msg_2 = f"""请将以下季度数据生成折线图，保存到 {output_path}：

X轴标签: {SAMPLE_X_LABELS_2}
Y轴数据: {SAMPLE_Y_DATA_2}

图表标题设为"2024年季度财务数据"，X轴名称为"季度"，Y轴名称为"金额(万元)"。
"""

    response2 = agent.invoke({"messages": [{"role": "user", "content": user_msg_2}]})

    print("\n=== Agent trace ===")
    for idx, msg in enumerate(response2.get("messages", []), start=1):
        content = getattr(msg, 'content', msg)
        msg_type = type(msg).__name__
        if isinstance(content, str) and len(content) > 500:
            content = content[:500] + "..."
        print(f"[{idx}] {msg_type} -> {content}")

    final_msg2 = response2.get("messages", [])[-1]
    print("\n=== Final reply ===")
    print(getattr(final_msg2, "content", final_msg2))


if __name__ == "__main__":
    import sys

    main()
