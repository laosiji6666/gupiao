@echo off
chcp 65001 >nul
title 📊 股票分析工具

cd /d "%~dp0"

echo ╔══════════════════════════════════════╗
echo ║      📊 股票分析系统启动中...         ║
echo ╚══════════════════════════════════════╝
echo.

:: 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装
    pause
    exit /b 1
)

:: 检查依赖
echo 🔍 检查依赖...
python -c "import akshare" 2>nul
if %errorlevel% neq 0 (
    echo 📦 安装依赖中...
    pip install -r requirements.txt
)

:: 运行数据分析
echo 📈 正在获取股票数据并分析...
start /B /MIN python main.py

:: 启动 Web 服务
echo 🌐 启动 Web 界面...
start /B python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080

:: 等待服务启动
timeout /t 3 /nobreak >nul

:: 打开浏览器
echo ✅ 正在打开浏览器...
start http://localhost:8080

echo.
echo 🔔 按任意键关闭本窗口（Web服务仍在后台运行）
echo.
pause >nul
