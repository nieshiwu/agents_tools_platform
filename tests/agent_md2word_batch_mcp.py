"""Agent 调用 md_to_word 工具进行 Markdown 转 Word。

支持：
- 单文件转换：上传一个 Markdown，生成一个 Word
- 多文件转换：上传多个 Markdown，生成多个 Word（一对一）

流程：
1. 本地文件上传到服务器
2. 调用 MCP 工具，传入服务器路径
3. 获取转换结果和下载链接

Run:
    python -m tests.agent_md2word_batch_mcp

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
            timeout=300,
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
        """调用 MCP 工具进行 Markdown 转 Word。
        
        Args:
            input_path: 服务器上的文件路径，支持：
                - 单个文件: "/app/temp_uploads/xxx.md"
                - 多个文件（逗号分隔）: "/app/temp_uploads/a.md, /app/temp_uploads/b.md"
            converter: 转换器选择（auto/pypandoc/comtypes/python）
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


def _prepare_sample_md_files(tmp_dir: Path, count: int = 3) -> List[Path]:
    """创建多个示例 Markdown 文件"""
    files = []
    for i in range(count):
        md_content = f"""# 示例文档 {i+1}

## 简介
这是第 {i+1} 个测试 Markdown 文件。

## 内容列表
- 项目 A
- 项目 B
- 项目 C ({i+1})

### 表格数据
| ID | 名称 | 值 |
| -- | -- | -- |
| 1 | 测试 | 100 |
| 2 | 演示 | {200 + i} |

> 这是一段引用文本。
"""
        md_path = tmp_dir / f"demo_{i+1}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        files.append(md_path)
    
    return files


def _prepare_sample_md(tmp_dir: Path) -> Path:
    """创建单个示例 Markdown 文件"""
    return _prepare_sample_md_files(tmp_dir, count=1)[0]


def _upload_file_to_server(file_path: Path) -> str:
    """上传文件到 MCP 服务器，返回服务器上的文件路径"""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/markdown")}
        resp = requests.post(f"{MCP_API_BASE}/mcp/files/upload", files=files, timeout=30)
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
    # 查找 md_to_word 工具
    target = next((t for t in tools_meta if t.get("name") == "md_to_word_batch"), None)
    if not target:
        raise RuntimeError("md_to_word 工具未在 MCP 服务器上找到，请先上传/启用该工具。")

    md_tool = mcp_tool_to_langchain(mcp_client, target)

    agent = create_agent(
        model=model,
        tools=[md_tool],
        system_prompt="""You are a helpful assistant for Markdown to Word conversion.

The tool accepts:
- input_path: Server file path(s). Single file or comma-separated multiple files.
- converter: Converter to use (auto/pypandoc/comtypes/python)

The tool returns JSON with:
- success: whether conversion succeeded
- total_files: number of files processed  
- processed: successful count
- failed: failed count
- file_mappings: list of {source, output, download_url} for each file
- converter_used: which converter was used
- message: status message

For single file, also returns: word_path, download_url, file_size_kb

Always report the download_url(s) to the user so they can download the converted Word files.""",
    )

    # 选择演示模式: single（单文件）或 multi（多文件）
    demo_mode = os.getenv("DEMO_MODE", "multi")
    
    tmp_dir = Path(tempfile.mkdtemp())
    
    if demo_mode == "multi":
        # 多文件模式
        print("=== 多文件转换模式 ===")
        # print("创建测试 Markdown 文件...")
        local_files = list(Path(r"D:\workspace\tools_platform\file\33").glob("*.md"))
        
        print(f"待处理文件: {len(local_files)} 个")
        if len(local_files) == 0:
            print("错误：未找到测试文件，请检查路径。将使用自动生成的测试文件。")
            local_files = _prepare_sample_md_files(tmp_dir, count=3)
            print(f"已自动生成 {len(local_files)} 个测试文件")

        print("正在上传文件到服务器...")
        server_paths = _upload_files_to_server(local_files)
        server_paths_str = ", ".join(server_paths)
        
        user_msg = (
            f"请把这些 Markdown 文件转成 Word: {server_paths_str}\n"
            "每个 Markdown 文件生成一个对应的 Word 文件。\n"
            "请告诉我每个文件的转换结果和下载链接。"
        )
    else:
        # 单文件模式（默认）
        print("=== 单文件转换模式 ===")
        print("创建测试 Markdown 文件...")
        local_md_path = _prepare_sample_md(tmp_dir)
        
        print(f"正在上传文件到服务器: {local_md_path}")
        server_md_path = _upload_file_to_server(local_md_path)
        print(f"文件已上传，服务器路径: {server_md_path}")
        
        user_msg = (
            f"请把这个 Markdown 转成 Word 文档: {server_md_path}\n"
            "请告诉我转换结果，包括 Word 文件的下载链接。"
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
