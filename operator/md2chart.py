"""
Markdown 数据可视化工具

将 Markdown 表格数据转换为折线图。
依赖：pip install matplotlib pandas
"""
import os
import re
import base64
import requests
from io import StringIO, BytesIO
from typing import Optional, List
from langchain_core.tools import tool

# MCP 服务地址（用于注册文件下载）
MCP_API_BASE = os.environ.get("MCP_API_BASE", "http://localhost:8000/api/mcp")


def register_file_download(file_path: str, expires_in: int = 3600) -> Optional[str]:
    """向 MCP 服务注册文件，获取下载 URL"""
    try:
        url = f"{MCP_API_BASE}/files/register"
        resp = requests.post(
            url,
            json={"file_path": file_path, "expires_in": expires_in},
            timeout=10
        )
        print(f"[DEBUG] 响应状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("download_url")
    except Exception as e:
        print(f"[DEBUG] 请求异常: {e}")
    return None

@tool
def md_data_to_line_chart(
    x_labels: List[str],
    y_data: dict,
    title: Optional[str] = None,
    x_label: str = "X轴",
    y_label: str = "Y轴",
    output_path: Optional[str] = None,
    return_base64: bool = False
) -> dict:
    """直接使用数据生成折线图（非表格格式）

    Args:
        x_labels: X轴标签列表，如 ["1月", "2月", "3月"]
        y_data: Y轴数据字典，键为系列名，值为数值列表，如：
            {"销售额": [100, 150, 200], "利润": [20, 35, 50]}
        title: 图表标题
        x_label: X轴标签名称
        y_label: Y轴标签名称
        output_path: 图片输出路径
        return_base64: 是否返回 Base64 编码

    Returns:
        包含生成结果的字典
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 验证数据
        if not x_labels:
            return {
                "success": False,
                "image_path": None,
                "download_url": None,
                "message": "错误：X轴标签不能为空"
            }
        
        if not y_data:
            return {
                "success": False,
                "image_path": None,
                "download_url": None,
                "message": "错误：Y轴数据不能为空"
            }
        
        # 创建图表
        fig, ax = plt.subplots(figsize=(10, 6))
        
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', 'h']
        colors = plt.cm.tab10.colors
        
        for i, (series_name, values) in enumerate(y_data.items()):
            if len(values) != len(x_labels):
                return {
                    "success": False,
                    "image_path": None,
                    "download_url": None,
                    "message": f"错误：'{series_name}' 数据长度({len(values)})与X轴标签数量({len(x_labels)})不匹配"
                }
            
            ax.plot(
                x_labels, values,
                marker=markers[i % len(markers)],
                color=colors[i % len(colors)],
                label=series_name,
                linewidth=2,
                markersize=8
            )
        
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        
        ax.set_xlabel(x_label, fontsize=12)
        ax.set_ylabel(y_label, fontsize=12)
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.7)
        
        if any(len(str(x)) > 5 for x in x_labels):
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # 保存
        if output_path is None:
            import tempfile
            import uuid
            output_path = os.path.join(tempfile.gettempdir(), f"chart_{uuid.uuid4().hex[:8]}.png")
        
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        
        download_url = register_file_download(output_path)
        
        result = {
            "success": True,
            "image_path": output_path,
            "download_url": download_url,
            "message": f"折线图生成成功，包含 {len(y_data)} 条数据线",
            "series": list(y_data.keys()),
            "data_points": len(x_labels)
        }
        
        if return_base64:
            with open(output_path, 'rb') as f:
                result["base64_image"] = base64.b64encode(f.read()).decode('utf-8')
        
        return result
        
    except ImportError:
        return {
            "success": False,
            "image_path": None,
            "download_url": None,
            "message": "错误：请先安装 matplotlib (pip install matplotlib)"
        }
    except Exception as e:
        return {
            "success": False,
            "image_path": None,
            "download_url": None,
            "message": f"错误：{str(e)}"
        }


# 测试代码
if __name__ == "__main__":
    result = md_data_to_line_chart.invoke({
        'x_labels': ['1月', '2月', '3月', '4月', '5月', '6月'],
        'y_data': {
            '销售额': [100, 150, 200, 180, 220, 250],
            '利润': [20, 35, 50, 40, 60, 75],
            '成本': [80, 115, 150, 140, 160, 175]
        },
        'title': '2024年上半年销售趋势',
        'x_label': '月份',
        'y_label': '金额(万元)'
    })
    print(result)
    # if result['success']:
    print(f"图表已保存到: {result['image_path']}")