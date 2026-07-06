@echo off
cd /d "%~dp0"

title Stock Analyzer

echo ========================================
echo   Stock Analyzer - Starting...
echo ========================================
echo.

:: Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python first.
    pause
    exit /b 1
)

:: Check dependencies
echo [INFO] Checking dependencies...
python -c "import akshare" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

:: Run data analysis
echo [INFO] Fetching stock data and analyzing...
start /B /MIN python main.py

:: Start web server
echo [INFO] Starting web server...
start /B python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080

:: Wait for server
timeout /t 3 /nobreak >nul

:: Open browser
echo [INFO] Opening browser...
start http://localhost:8080/dashboard

echo.
echo ========================================
echo   Web server is running at:
echo   http://localhost:8080/dashboard
echo   Close this window to stop.
echo ========================================
echo.
pause >nul
