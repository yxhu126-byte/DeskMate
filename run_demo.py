"""
DeskMate V1 Demo 启动脚本

用法:
    python run_demo.py          # 启动后端服务
    python run_demo.py --help   # 查看帮助

前端使用方式:
    方式 1: 直接在浏览器中打开 frontend/index.html
    方式 2: 使用 VS Code Live Server 或其他 HTTP 服务器
    方式 3: cd frontend && python -m http.server 3000
"""
import sys
import os
import subprocess


def main():
    print("=" * 60)
    print("  🖥️  DeskMate v1.0.0-demo")
    print("  网页端 AI 多模态伴随助手")
    print("=" * 60)
    print()
    print("启动步骤:")
    print()
    print("  1. 安装后端依赖:")
    print("     cd backend")
    print("     pip install -r requirements.txt")
    print()
    print("  2. 配置 AI API Key (可选):")
    print("     编辑 backend/.env 文件")
    print("     - 不配置: 使用演示模式（模拟回答）")
    print("     - 配置 ANTHROPIC_API_KEY: 使用 Claude")
    print("     - 配置 OPENAI_API_KEY: 使用 GPT-4o")
    print()
    print("  3. 启动后端服务:")
    print("     cd backend")
    print("     python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("  4. 打开前端:")
    print("     方式 A: 浏览器直接打开 frontend/index.html")
    print("     方式 B: cd frontend && python -m http.server 3000")
    print("             然后访问 http://localhost:3000")
    print()
    print("  5. API 文档:")
    print("     http://localhost:8000/docs")
    print()
    print("=" * 60)

    # 检查是否要自动启动后端
    if "--start" in sys.argv:
        print("正在启动后端服务...")
        backend_dir = os.path.join(os.path.dirname(__file__), "backend")
        os.chdir(backend_dir)
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
        ])


if __name__ == "__main__":
    main()
