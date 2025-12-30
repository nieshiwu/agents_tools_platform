"""
Streamlit Web Interface for Tools Platform
"""
import streamlit as st
import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000/api"

# Page config
st.set_page_config(
    page_title="LangChain 工具平台",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .tool-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
    }
    .status-valid {
        color: #28a745;
        font-weight: bold;
    }
    .status-invalid {
        color: #dc3545;
        font-weight: bold;
    }
    .status-pending {
        color: #ffc107;
        font-weight: bold;
    }
    .status-disabled {
        color: #6c757d;
        font-weight: bold;
    }
    .code-block {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 15px;
        border-radius: 5px;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)


def get_status_badge(status: str) -> str:
    """Get status badge HTML"""
    colors = {
        "valid": "🟢",
        "invalid": "🔴",
        "pending": "🟡",
        "disabled": "⚫"
    }
    return colors.get(status, "⚪")


def api_request(method: str, endpoint: str, **kwargs):
    """Make API request"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ 无法连接到后端服务，请确保 API 服务正在运行")
        return None
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", str(e))
        st.error(f"❌ API 错误: {error_detail}")
        return None
    except Exception as e:
        st.error(f"❌ 请求错误: {str(e)}")
        return None


# Sidebar
with st.sidebar:
    st.title("🛠️ LangChain 工具平台")
    st.markdown("---")
    
    page = st.radio(
        "导航",
        ["📋 工具列表", "➕ 上传工具", "🔍 测试工具", "📚 规范文档", "📊 统计信息"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Statistics summary
    stats = api_request("GET", "/tools/statistics")
    if stats:
        st.metric("总工具数", stats["total_tools"])
        col1, col2 = st.columns(2)
        with col1:
            st.metric("有效", stats["valid_tools"])
        with col2:
            st.metric("调用次数", stats["total_calls"])
    
    st.markdown("---")
    st.markdown("### MCP 服务")
    st.code("http://localhost:8000/api/mcp", language=None)


# Main content
if page == "📋 工具列表":
    st.header("📋 工具列表")
    
    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 搜索工具", placeholder="输入工具名称或描述...")
    with col2:
        status_filter = st.selectbox("状态筛选", ["全部", "valid", "invalid", "pending", "disabled"])
    with col3:
        st.write("")  # Spacing
        refresh = st.button("🔄 刷新")
    
    # Build query params
    params = {}
    if search:
        params["search"] = search
    if status_filter != "全部":
        params["status"] = status_filter
    
    # Fetch tools
    tools = api_request("GET", "/tools/", params=params)
    
    if tools:
        if len(tools) == 0:
            st.info("暂无工具，点击左侧「上传工具」添加新工具")
        else:
            for tool in tools:
                with st.expander(f"{get_status_badge(tool['status'])} **{tool['name']}** - {tool.get('description', '无描述')[:50]}...", expanded=False):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**描述:** {tool.get('description', '无描述')}")
                        st.write(f"**类型:** {tool['tool_type']}")
                        st.write(f"**上传者:** {tool.get('uploader', '匿名')}")
                        st.write(f"**创建时间:** {tool['created_at'][:19]}")
                    
                    with col2:
                        st.write(f"**状态:** {tool['status']}")
                        st.write(f"**调用次数:** {tool['call_count']}")
                    
                    with col3:
                        if st.button("查看详情", key=f"view_{tool['id']}"):
                            st.session_state.selected_tool_id = tool['id']
                            st.rerun()
                        if st.button("删除", key=f"delete_{tool['id']}"):
                            result = api_request("DELETE", f"/tools/{tool['id']}")
                            if result:
                                st.success("工具已删除")
                                st.rerun()
    
    # Tool detail view
    if 'selected_tool_id' in st.session_state:
        tool_detail = api_request("GET", f"/tools/{st.session_state.selected_tool_id}")
        if tool_detail:
            st.markdown("---")
            st.subheader(f"📝 工具详情: {tool_detail['name']}")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.write(f"**状态:** {get_status_badge(tool_detail['status'])} {tool_detail['status']}")
                st.write(f"**类型:** {tool_detail['tool_type']}")
                st.write(f"**描述:** {tool_detail.get('description', '无描述')}")
                
                if tool_detail.get('validation_message'):
                    st.warning(f"**验证信息:**\n{tool_detail['validation_message']}")
                
                if tool_detail.get('input_schema'):
                    st.write("**输入参数Schema:**")
                    st.json(tool_detail['input_schema'])
            
            with col2:
                st.write("**源代码:**")
                st.code(tool_detail['source_code'], language="python")
            
            if st.button("关闭详情"):
                del st.session_state.selected_tool_id
                st.rerun()


elif page == "➕ 上传工具":
    st.header("➕ 上传工具")
    
    st.info("上传您的 LangChain 工具代码，系统会自动验证是否符合规范。")
    
    with st.form("upload_form"):
        tool_name = st.text_input("工具名称 *", placeholder="my_tool")
        tool_description = st.text_area("工具描述", placeholder="这个工具用于...")
        uploader = st.text_input("上传者", placeholder="您的名字（可选）")
        
        st.write("**源代码** *")
        source_code = st.text_area(
            "source_code",
            height=400,
            placeholder='''from langchain_core.tools import tool

@tool
def my_tool(query: str) -> str:
    """工具描述
    
    Args:
        query: 输入参数
    
    Returns:
        处理结果
    """
    return f"处理结果: {query}"''',
            label_visibility="collapsed"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            validate_only = st.form_submit_button("🔍 仅验证")
        with col2:
            submit = st.form_submit_button("📤 上传工具", type="primary")
    
    if validate_only and source_code:
        with st.spinner("验证中..."):
            result = api_request("POST", "/tools/validate", params={"source_code": source_code})
            if result:
                if result["is_valid"]:
                    st.success(f"✅ 验证通过！工具类型: {result['tool_type']}")
                    if result.get("input_schema"):
                        st.write("**检测到的输入参数:**")
                        st.json(result["input_schema"])
                else:
                    st.error("❌ 验证失败")
                    if result.get("errors"):
                        st.write("**错误:**")
                        for error in result["errors"]:
                            st.write(f"- {error}")
                    if result.get("suggestions"):
                        st.write("**建议:**")
                        for suggestion in result["suggestions"]:
                            st.write(f"- {suggestion}")
    
    if submit:
        if not tool_name or not source_code:
            st.error("请填写工具名称和源代码")
        else:
            with st.spinner("上传中..."):
                data = {
                    "name": tool_name,
                    "description": tool_description if tool_description else None,
                    "source_code": source_code,
                    "uploader": uploader if uploader else None
                }
                result = api_request("POST", "/tools/", json=data)
                if result:
                    if result["status"] == "valid":
                        st.success(f"✅ 工具 '{tool_name}' 上传成功！")
                        st.balloons()
                    else:
                        st.warning(f"⚠️ 工具已保存，但验证未通过")
                        if result.get("validation_message"):
                            st.write("**验证信息:**")
                            st.write(result["validation_message"])


elif page == "🔍 测试工具":
    st.header("🔍 测试工具")
    
    # Get valid tools
    tools = api_request("GET", "/tools/", params={"status": "valid"})
    
    if tools and len(tools) > 0:
        tool_names = [t["name"] for t in tools]
        selected_tool = st.selectbox("选择工具", tool_names)
        
        # Get tool details
        tool = next((t for t in tools if t["name"] == selected_tool), None)
        if tool:
            tool_detail = api_request("GET", f"/tools/{tool['id']}")
            if tool_detail:
                st.write(f"**描述:** {tool_detail.get('description', '无描述')}")
                
                # Build input form based on schema
                input_schema = tool_detail.get("input_schema", {})
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])
                
                st.write("**输入参数:**")
                arguments = {}
                
                with st.form("test_form"):
                    for prop_name, prop_info in properties.items():
                        prop_type = prop_info.get("type", "string")
                        prop_desc = prop_info.get("description", prop_name)
                        is_required = prop_name in required
                        
                        label = f"{prop_name} {'*' if is_required else ''}"
                        
                        if prop_type == "string":
                            arguments[prop_name] = st.text_input(label, help=prop_desc)
                        elif prop_type == "integer":
                            arguments[prop_name] = st.number_input(label, step=1, help=prop_desc)
                        elif prop_type == "number":
                            arguments[prop_name] = st.number_input(label, help=prop_desc)
                        elif prop_type == "boolean":
                            arguments[prop_name] = st.checkbox(label, help=prop_desc)
                        else:
                            arguments[prop_name] = st.text_input(label, help=prop_desc)
                    
                    caller = st.text_input("调用者（可选）", placeholder="您的名字")
                    submit = st.form_submit_button("🚀 执行工具", type="primary")
                
                if submit:
                    # Filter out empty values
                    filtered_args = {k: v for k, v in arguments.items() if v}
                    
                    with st.spinner("执行中..."):
                        result = api_request(
                            "POST",
                            "/mcp/call",
                            json={
                                "tool_name": selected_tool,
                                "arguments": filtered_args,
                                "caller": caller if caller else None
                            }
                        )
                        
                        if result:
                            if result["success"]:
                                st.success(f"✅ 执行成功 (耗时: {result.get('execution_time_ms', 0)}ms)")
                                st.write("**结果:**")
                                st.code(result["result"], language=None)
                            else:
                                st.error("❌ 执行失败")
                                st.write(f"**错误:** {result.get('error', '未知错误')}")
    else:
        st.info("暂无可用工具，请先上传并验证工具")


elif page == "📚 规范文档":
    st.header("📚 LangChain 工具规范")
    
    spec = api_request("GET", "/tools/spec")
    if spec:
        st.markdown(spec["specification"])
    
    st.markdown("---")
    st.subheader("示例代码")
    
    tab1, tab2 = st.tabs(["@tool 装饰器", "BaseTool 类"])
    
    with tab1:
        st.code('''from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
    
    Returns:
        计算结果
    """
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"
''', language="python")
    
    with tab2:
        st.code('''from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class WeatherInput(BaseModel):
    """天气查询输入参数"""
    city: str = Field(description="城市名称")

class WeatherTool(BaseTool):
    """天气查询工具"""
    name: str = "weather"
    description: str = "查询指定城市的天气信息"
    args_schema: Type[BaseModel] = WeatherInput
    
    def _run(self, city: str) -> str:
        """执行天气查询"""
        # 这里应该调用真实的天气API
        return f"{city}的天气: 晴天，温度25°C"
    
    async def _arun(self, city: str) -> str:
        """异步执行"""
        return self._run(city)
''', language="python")


elif page == "📊 统计信息":
    st.header("📊 统计信息")
    
    stats = api_request("GET", "/tools/statistics")
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📦 总工具数", stats["total_tools"])
        with col2:
            st.metric("✅ 有效工具", stats["valid_tools"])
        with col3:
            st.metric("❌ 无效工具", stats["invalid_tools"])
        with col4:
            st.metric("📞 总调用次数", stats["total_calls"])
        
        st.markdown("---")
        
        # Tool usage chart
        tools = api_request("GET", "/tools/")
        if tools and len(tools) > 0:
            st.subheader("工具调用排行")
            
            # Sort by call count
            sorted_tools = sorted(tools, key=lambda x: x["call_count"], reverse=True)[:10]
            
            if any(t["call_count"] > 0 for t in sorted_tools):
                import pandas as pd
                df = pd.DataFrame([
                    {"工具名称": t["name"], "调用次数": t["call_count"]}
                    for t in sorted_tools
                ])
                st.bar_chart(df.set_index("工具名称"))
            else:
                st.info("暂无调用数据")
            
            st.markdown("---")
            st.subheader("工具状态分布")
            
            status_counts = {}
            for t in tools:
                status = t["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            if status_counts:
                import pandas as pd
                df = pd.DataFrame([
                    {"状态": k, "数量": v}
                    for k, v in status_counts.items()
                ])
                st.bar_chart(df.set_index("状态"))


# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "LangChain Tools Platform v1.0.0 | "
    "<a href='/docs' target='_blank'>API 文档</a>"
    "</div>",
    unsafe_allow_html=True
)
