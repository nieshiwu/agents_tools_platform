"""Minimal agent that calls the get_exchange_rate tool via MCP.

Run:
    python -m tests.agent_getrate_mcp

Prerequisites:
    - Backend running (e.g., `python run.py all` or uvicorn entrypoint).
    - Tool `get_exchange_rate` uploaded/valid on the MCP server.
    - Environment variable DASHSCOPE_API_KEY set (or adjust init_chat_model accordingly).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool


load_dotenv()
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
        currency_from: str = "USD",
        currency_to: str = "CNY",
        currency_date: str = "latest",
    ) -> str:
        """Call MCP tool with explicit parameters."""
        arguments: Dict[str, Any] = {
            "currency_from": currency_from,
            "currency_to": currency_to,
            "currency_date": currency_date,
        }
        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )


def main() -> None:
    model = init_chat_model(model=MODEL_NAME, api_key=API_KEY)
    mcp_client = MCPClient(MCP_API_BASE)

    tools_meta = mcp_client.list_tools()
    target = next((t for t in tools_meta if t.get("name") == "get_exchange_rate"), None)
    if not target:
        raise RuntimeError("get_exchange_rate not found on MCP server; please upload/enable it first.")

    rate_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[rate_tool],
        system_prompt="""你是一个有帮助的助手。当用户询问汇率时，使用工具查询汇率。
工具返回的 JSON 包含:
- success: 是否查询成功
- currency_from: 源货币
- currency_to: 目标货币  
- rate: 汇率
- date: 汇率日期
- message: 状态信息

请用中文回复用户，告诉他们查询结果。""",
    )

    user_msg = "请帮我查询一下美元兑人民币的汇率是多少？"

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
