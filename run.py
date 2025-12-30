"""
启动脚本 - 启动 FastAPI 后端和前端服务

使用方法:
    python run.py api              - 仅启动 API 后端
    python run.py web              - 启动 Web 前端（默认 React）
    python run.py web --react      - 启动 React 前端
    python run.py web --streamlit  - 启动 Streamlit 前端
    python run.py all              - 同时启动 API + React 前端
    python run.py all --streamlit  - 同时启动 API + Streamlit 前端
    python run.py                  - 显示帮助信息
"""
import subprocess
import sys
import os
import time
import threading
import http.server
import socketserver
import functools

# 默认前端类型
DEFAULT_FRONTEND = "react"


def run_api():
    """启动 FastAPI 后端"""
    print("🚀 启动 FastAPI 后端服务...")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])


def run_streamlit():
    """启动 Streamlit 前端"""
    print("🌐 启动 Streamlit 前端服务...")
    subprocess.run([
        sys.executable, "-m", "streamlit",
        "run", "web/app.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ])


class ReactProxyHandler(http.server.SimpleHTTPRequestHandler):
    """React 前端的代理处理器，将 /api 请求转发到后端"""
    
    def __init__(self, *args, directory=None, **kwargs):
        self.react_dir = directory
        super().__init__(*args, directory=directory, **kwargs)
    
    def do_GET(self):
        if self.path.startswith('/api'):
            self.proxy_to_backend()
        else:
            # 返回 app.html
            if self.path == '/' or not os.path.exists(os.path.join(self.react_dir, self.path.lstrip('/'))):
                self.path = '/app.html'
            super().do_GET()
    
    def do_POST(self):
        if self.path.startswith('/api'):
            self.proxy_to_backend()
        else:
            self.send_error(404)
    
    def do_DELETE(self):
        if self.path.startswith('/api'):
            self.proxy_to_backend()
        else:
            self.send_error(404)
    
    def do_PUT(self):
        if self.path.startswith('/api'):
            self.proxy_to_backend()
        else:
            self.send_error(404)
    
    def proxy_to_backend(self):
        """将请求代理到后端 API"""
        import urllib.request
        import urllib.error
        
        backend_url = f"http://localhost:8000{self.path}"
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # 构建请求
            req = urllib.request.Request(
                backend_url,
                data=body,
                method=self.command
            )
            
            # 复制请求头
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'content-length']:
                    req.add_header(header, value)
            
            if body:
                req.add_header('Content-Type', self.headers.get('Content-Type', 'application/json'))
            
            # 发送请求
            with urllib.request.urlopen(req, timeout=30) as response:
                # 发送响应
                self.send_response(response.status)
                for header, value in response.getheaders():
                    if header.lower() not in ['transfer-encoding', 'connection']:
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.read())
                
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, f"Backend Error: {str(e)}")
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        if '/api' in args[0]:
            print(f"  [API] {args[0]}")


def run_react(port=3000):
    """启动 React 前端（使用内置 HTTP 服务器）"""
    print(f"🌐 启动 React 前端服务 (端口 {port})...")
    
    react_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web-react')
    
    handler = functools.partial(ReactProxyHandler, directory=react_dir)
    
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"   React 前端已启动: http://localhost:{port}")
        httpd.serve_forever()


def run_web(frontend_type=DEFAULT_FRONTEND):
    """启动前端服务"""
    if frontend_type == "streamlit":
        run_streamlit()
    else:
        run_react()


def run_all(frontend_type=DEFAULT_FRONTEND):
    """同时启动 API 和前端服务"""
    web_port = 3000 if frontend_type == "react" else 8501
    web_url = f"http://localhost:{web_port}"
    
    print("=" * 50)
    print("🚀 LangChain 工具平台启动中...")
    print("=" * 50)
    print()
    print("📡 API 服务: http://localhost:8000")
    print("📖 API 文档: http://localhost:8000/docs")
    print(f"🌐 Web 界面: {web_url} ({frontend_type.upper()})")
    print("🔧 MCP 服务: http://localhost:8000/api/mcp")
    print()
    print("=" * 50)
    print("按 Ctrl+C 停止所有服务")
    print("=" * 50)
    print()

    # 启动 API 服务（在新线程中）
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # 等待 API 启动
    time.sleep(3)

    # 启动前端服务（在新线程中）
    if frontend_type == "streamlit":
        web_thread = threading.Thread(target=run_streamlit, daemon=True)
    else:
        web_thread = threading.Thread(target=run_react, daemon=True)
    web_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 正在停止服务...")
        sys.exit(0)


def show_help():
    """显示帮助信息"""
    print("=" * 50)
    print("LangChain 工具平台 - 启动脚本")
    print("=" * 50)
    print()
    print("使用方法:")
    print("  python run.py api              - 仅启动 API 后端")
    print("  python run.py web              - 启动前端（默认 React）")
    print("  python run.py web --react      - 启动 React 前端")
    print("  python run.py web --streamlit  - 启动 Streamlit 前端")
    print("  python run.py all              - 同时启动 API + 前端（默认 React）")
    print("  python run.py all --streamlit  - 同时启动 API + Streamlit 前端")
    print()
    print("服务地址:")
    print("  API 服务: http://localhost:8000")
    print("  API 文档: http://localhost:8000/docs")
    print("  React 前端: http://localhost:3000")
    print("  Streamlit 前端: http://localhost:8501")
    print("  MCP 服务: http://localhost:8000/api/mcp")
    print()
    print("首次运行前请确保:")
    print("  1. PostgreSQL 已启动")
    print("  2. 已创建数据库: CREATE DATABASE tools_platform;")
    print("  3. 已安装依赖: pip install -r requirements.txt")
    print()


def get_frontend_type(args):
    """从命令行参数获取前端类型"""
    if "--streamlit" in args:
        return "streamlit"
    elif "--react" in args:
        return "react"
    return DEFAULT_FRONTEND


def main():
    # 切换到项目目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    frontend_type = get_frontend_type(sys.argv)

    if command == "api":
        run_api()
    elif command == "web":
        run_web(frontend_type)
    elif command == "all":
        run_all(frontend_type)
    else:
        print(f"❌ 未知命令: {command}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
