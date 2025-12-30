"""
Minimal agent that calls the cmd_run tool via MCP.

Run:
    python -m tests.agent_cmd_run_agent_mcp

Prerequisites:
    - Backend running (e.g., `python run.py all` or uvicorn entrypoint).
    - Tool `cmd_run` uploaded/valid on the MCP server.
    - Environment variable DASHSCOPE_API_KEY set (or adjust init_chat_model accordingly).
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv
import requests
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool

load_dotenv()
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:8000/api")
MODEL_NAME = os.getenv("AGENT_MODEL", "openai:deepseek-v3")
API_KEY = os.getenv("DASHSCOPE_API_KEY")

class MCPClient:
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
    def _call_mcp_tool(script_path: str, script_arg1: str = "", script_arg2: str = "", python_executable: str = "") -> str:
        # langgraph/StructuredTool 对参数名 "args" 会注入 v__args，故使用 script_argX 规避
        arguments: Dict[str, Any] = {"script_path": script_path}
        script_args: list[str] = []
        if script_arg1:
            script_args.append(script_arg1)
        if script_arg2:
            script_args.append(script_arg2)
        if script_args:
            arguments["args"] = script_args
        if python_executable:
            arguments["python_executable"] = python_executable
        return mcp_client.call_tool(name, arguments)
    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=description,
    )

def _prepare_sample_py(tmp_dir: Path) -> Path:
    py_path = tmp_dir / "demo_test.py"
    py_path.write_text("""print('hello from agent test script')\nimport sys\nprint('args:', sys.argv[1:])\n""")
    return py_path

def main() -> None:
    model = init_chat_model(model=MODEL_NAME, api_key=API_KEY)
    mcp_client = MCPClient(MCP_API_BASE)
    tools_meta = mcp_client.list_tools()
    target = next((t for t in tools_meta if t.get("name") == "run_python_script_tool"), None)
    if not target:
        raise RuntimeError("cmd_run not found on MCP server; please upload/enable it first.")
    cmd_run_tool = mcp_tool_to_langchain(mcp_client, target)
    agent = create_agent(
        model=model,
        tools=[cmd_run_tool],
        system_prompt="你是一个代码执行助手。用户给出 Python 脚本路径和参数时，请调用 cmd_run 工具执行并返回结果。",
    )
    tmp_dir = Path(tempfile.mkdtemp())
    py_path = _prepare_sample_py(tmp_dir)
    user_msg = (
        f"请用 Python 解释器执行此脚本: {py_path}，参数为 --foo bar。请返回标准输出和错误输出。"
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
