"""
构建 Windows 可执行文件
运行: python build_exe.py
"""
import os
import shutil
import subprocess
import site
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist", "StockAnalyzer")


def find_talib_dlls():
    """查找 TA-Lib DLL 文件"""
    dlls = []
    # 检查 Python 包目录
    for p in site.getsitepackages():
        talib_dir = os.path.join(p, "talib")
        if os.path.isdir(talib_dir):
            for f in os.listdir(talib_dir):
                if f.endswith(".dll") or f.endswith(".pyd"):
                    dlls.append(os.path.join(talib_dir, f))
    # 检查 PATH 和系统目录
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isdir(p):
            for f in os.listdir(p):
                if f.lower().startswith("ta_lib") and f.endswith(".dll"):
                    dlls.append(os.path.join(p, f))
    return dlls


def build():
    print("=" * 50)
    print("  Building Stock Analyzer executable...")
    print("=" * 50)
    print()

    # 清理旧构建
    for d in ["build", "dist"]:
        p = os.path.join(BASE_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    # 查找 TA-Lib DLL
    talib_dlls = find_talib_dlls()
    if talib_dlls:
        print(f"Found TA-Lib DLLs: {talib_dlls}")
    else:
        print("Warning: No TA-Lib DLLs found, may need manual copy")

    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "StockAnalyzer",
        "--onedir",            # 目录模式，兼容性更好
        "--console",           # 显示控制台窗口（方便查看日志）
        "--add-data", f"config.yaml{os.pathsep}.",
        "--add-data", f"src{os.pathsep}src",
        "--add-data", f"utils{os.pathsep}utils",
        "--add-data", f"dashboard.html{os.pathsep}.",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "sqlalchemy.sql.default_comparator",
        "--hidden-import", "yaml",
        "--collect-all", "talib",
        "--collect-all", "akshare",
        "--collect-all", "pandas",
        "--collect-all", "numpy",
        "--collect-all", "sqlalchemy",
        "--collect-all", "fastapi",
        "--collect-all", "uvicorn",
        "--collect-all", "jinja2",
        "--collect-all", "apscheduler",
        "launcher.py",
    ]

    # 添加 TA-Lib DLL
    for dll in talib_dlls:
        cmd.extend(["--add-binary", f"{dll}{os.pathsep}."])

    print("Running PyInstaller...")
    print(f"Command: {' '.join(cmd[:6])} ...")
    print()

    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"Build failed with code {result.returncode}")
        sys.exit(1)

    # 复制额外文件
    exe_name = "StockAnalyzer.exe"
    src_exe = os.path.join(BASE_DIR, "dist", exe_name)
    if os.path.isfile(src_exe):
        print(f"\nBuild successful: {src_exe}")
        print(f"Size: {os.path.getsize(src_exe) / 1024 / 1024:.1f} MB")
    else:
        print("\nBuild may have failed - exe not found at expected path")


if __name__ == "__main__":
    build()
