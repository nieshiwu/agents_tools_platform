"""
测试脚本：让 LangChain Agent 通过 MCP 协议调用工具查天气

流程：
1. 从 MCP 平台发现可用工具 (POST /api/mcp/protocol/tools/list)
2. 将 MCP 工具转换为 LangChain Tool
3. 创建 Agent 并让其自主决定调用哪个工具
4. Agent 通过 MCP 协议端点调用工具 (POST /api/mcp/protocol/tools/call)

用法：
    .venv\\Scripts\\activate
    python tests/test_mcp.py
"""
import os
import sys
import requests
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import StructuredTool
# from langgraph.prebuilt import create_react_agent

# ============================================================================
# 配置
# ============================================================================
load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
# MCP_API_BASE = os.getenv("MCP_API_BASE", "http://localhost:7000/api")
MCP_API_BASE = os.getenv("MCP_API_BASE", "http://192.168.0.197:8000/api")

model = init_chat_model(
    model="openai:deepseek-v3",
    api_key=DASHSCOPE_API_KEY
)


# ============================================================================
# MCP 客户端：发现工具 & 调用工具
# ============================================================================
class MCPClient:
    """MCP 协议客户端，用于发现和调用远程工具"""

    def __init__(self, base_url: str = MCP_API_BASE):
        self.base_url = base_url

    def list_tools(self) -> List[Dict[str, Any]]:
        """通过 MCP 协议发现可用工具"""
        resp = requests.post(f"{self.base_url}/mcp/protocol/tools/list", timeout=10)
        resp.raise_for_status()
        return resp.json().get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """通过 MCP 协议调用工具"""
        payload = {"name": name, "arguments": arguments}
        resp = requests.post(
            f"{self.base_url}/mcp/protocol/tools/call",
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        # 解析 MCP 协议响应
        if data.get("isError"):
            content = data.get("content", [])
            error_text = "".join(c.get("text", "") for c in content)
            raise RuntimeError(f"MCP tool error: {error_text}")

        content = data.get("content", [])
        return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


# ============================================================================
# 将 MCP 工具转换为 LangChain Tool
# ============================================================================
def mcp_tool_to_langchain(mcp_client: MCPClient, tool_info: Dict[str, Any]) -> StructuredTool:
    """将 MCP 工具定义转换为 LangChain StructuredTool"""
    name = tool_info["name"]
    description = tool_info.get("description", f"Tool: {name}")
    input_schema = tool_info.get("inputSchema", {})

    # 从 inputSchema 提取参数信息
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])

    # 构建参数描述
    args_desc = []
    for param_name, param_info in properties.items():
        param_type = param_info.get("type", "string")
        param_desc = param_info.get("description", "")
        req = "(required)" if param_name in required else "(optional)"
        args_desc.append(f"  - {param_name} ({param_type}) {req}: {param_desc}")

    full_description = description
    if args_desc:
        full_description += "\n\nParameters:\n" + "\n".join(args_desc)

    def _call_mcp_tool(tool_input: str = "", **kwargs) -> str:
        """调用 MCP 工具的包装函数"""
        # 处理各种可能的输入格式
        if kwargs:
            # 如果有嵌套的 kwargs，展开它
            if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
                arguments = kwargs["kwargs"]
            else:
                arguments = kwargs
        elif tool_input:
            # 如果只有单个字符串输入，尝试作为第一个参数
            first_param = list(properties.keys())[0] if properties else "input"
            arguments = {first_param: tool_input}
        else:
            arguments = {}
        
        return mcp_client.call_tool(name, arguments)

    return StructuredTool.from_function(
        func=_call_mcp_tool,
        name=name,
        description=full_description,
    )


def load_tools_from_mcp(mcp_client: MCPClient) -> List[StructuredTool]:
    """从 MCP 平台加载所有可用工具"""
    mcp_tools = mcp_client.list_tools()
    print(f"发现 {len(mcp_tools)} 个 MCP 工具:")
    for t in mcp_tools:
        print(f"  - {t['name']}: {t.get('description', '')[:50]}...")
        print(f"    inputSchema: {t.get('inputSchema', {})}")

    return [mcp_tool_to_langchain(mcp_client, t) for t in mcp_tools]


# ============================================================================
# 示例 1：创建 Agent 并通过 MCP 调用工具查天气
# ============================================================================
def example_1_agent_with_mcp_tools():
    """
    示例1：创建 Agent，从 MCP 平台加载工具，查询天气

    关键：
    1. 通过 MCP 协议发现工具（模拟 agent 的工具发现阶段）
    2. 将 MCP 工具转换为 LangChain Tool
    3. Agent 自动决定使用哪个工具
    4. 工具调用通过 MCP 协议端点执行
    """
    print("\n" + "="*70)
    print("示例 1：Agent 通过 MCP 协议调用工具查天气")
    print("="*70)

    # 创建 MCP 客户端
    mcp_client = MCPClient(MCP_API_BASE)

    # 从 MCP 平台加载工具
    print("\n[Step 1] 从 MCP 平台发现工具...")
    try:
        tools = load_tools_from_mcp(mcp_client)
    except Exception as e:
        print(f"❌ 无法连接 MCP 平台: {e}")
        print(f"   请确保后端服务在 {MCP_API_BASE} 运行")
        return

    if not tools:
        print("❌ MCP 平台没有可用工具，请先上传工具")
        return

    # 创建 Agent
    print("\n[Step 2] 创建 LangChain Agent...")
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt="你是一个智能助理,深度分析用户的需求,通过调用工具来完成用户的请求，并总结最终输出。",
    )
    print(f"Agent 创建成功！已加载 {len(tools)} 个工具")

    # 测试：询问天气（Agent 会自动选择合适的工具）
    # print("\n[Step 3] 测试：询问北京天气...")
    print("-" * 50)

    try:
        response = agent.invoke({
            "messages": [{"role": "user", "content": "帮我随机生成一个密码？"}]
        })
        
        # 打印完整的消息流程
        print("\n📋 Agent 交互详情:")
        print("=" * 60)
        # print(response['messages'])
        for i, msg in enumerate(response['messages']):
            msg_type = type(msg).__name__
            print(f"\n[{i+1}] {msg_type}")
            print("-" * 40)
            
            if msg_type == "HumanMessage":
                print(f"👤 User: {msg.content}")
            
            elif msg_type == "AIMessage":
                if msg.content:
                    print(f"🤖 AI: {msg.content}")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"🔧 Tool Calls:")
                    for tc in msg.tool_calls:
                        print(f"   - name: {tc.get('name')}")
                        print(f"     args: {tc.get('args')}")
            
            elif msg_type == "ToolMessage":
                print(f"🛠️ Tool Response:")
                print(f"   tool: {getattr(msg, 'name', 'unknown')}")
                print(f"   content: {msg.content}")
            
            else:
                print(f"   content: {getattr(msg, 'content', str(msg))}")
        
        print("\n" + "=" * 60)
        print(f"\n✅ 最终回复：{response['messages'][-1].content}")
        
    except Exception as e:
        print(f"❌ Agent 调用失败: {e}")

    print("\n" + "-" * 50)
    print("关键点：")
    print("  - Agent 通过 MCP 协议发现可用工具")
    print("  - Agent 自动判断需要使用天气工具")
    print("  - 工具调用通过 /api/mcp/protocol/tools/call 执行")
    print("  - Agent 获取结果后生成自然语言回答")


# ============================================================================
# 主函数
# ============================================================================
if __name__ == "__main__":
    print("="*70)
    print("LangChain Agent + MCP 工具调用测试")
    print("="*70)
    print(f"MCP 平台地址: {MCP_API_BASE}")

    example_1_agent_with_mcp_tools()

